"""Live vision service for the dashboard.

Owns the camera, runs the existing :class:`EdgeVisionPipeline` (YOLO PPE + pose +
posture + tripwire + PrivacyGuard), applies :class:`PersonTracker` for stable
per-person IDs, optionally enriches tracks with RFID/RBAC, commits one debounced
blockchain event per real person, and publishes:

  * the annotated frame as in-memory JPEG (MJPEG endpoint), and
  * the current confirmed detections (WebSocket ``/ws/live-events``).

Nothing is written to disk — consistent with PrivacyGuard (memory-only frames).
The pipeline / blockchain / RFID modules are reused unchanged; this is an
additive, API-friendly runner that runs in a background thread.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import cv2

from core.event_engine import EventEngine
from core.pipeline import build_pipeline_from_config
from core.tracker import PersonTracker, Track, TrackingConfig
from security.logger import SecureLogger, VPAPLogger, normalize_event_record

logger = logging.getLogger("posevision.live_service")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_for(track: Track) -> str:
    if not track.intrusion:
        return "CLEAR"
    if track.uid is None:
        return "UNAUTHORIZED_INTRUSION"
    if track.decision == "UNKNOWN_TAG":
        return "UNKNOWN_RFID"
    if track.authorized:
        return "AUTHORIZED_ACCESS"
    return "ZONE_VIOLATION"


class LiveVisionService:
    """Singleton-style background camera→AI→broadcast service."""

    def __init__(
        self,
        config: Dict[str, Any],
        project_root: Path,
        vpap: Optional[Union[VPAPLogger, SecureLogger]] = None,
    ) -> None:
        self.config = config
        self.root = Path(project_root)
        self.vpap = vpap
        self.tracking_cfg = TrackingConfig.from_dict(config.get("tracking"))
        live_cfg = config.get("live") or {}
        self.jpeg_quality = int(live_cfg.get("jpeg_quality", 70))
        self.target_fps = float(live_cfg.get("target_fps", 15.0))

        self._lock = threading.Lock()
        self._start_lock = threading.Lock()  # serializes start/stop transitions
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._running = False
        self._source = "webcam"
        self._stream_url: Optional[str] = None
        self._error: Optional[str] = None

        self._latest_jpeg: Optional[bytes] = None
        self._detections: List[Dict[str, Any]] = []
        self._fps = 0.0
        self._latency_ms = 0.0
        self._frame_index = 0
        self._frame_wh = (0, 0)

        # heavy objects built lazily on first start
        self._pipeline: Any = None
        self._tracker: Optional[PersonTracker] = None
        self._event_engine: Optional[EventEngine] = None
        self._access_control: Any = None
        self._reader: Any = None
        self._zone_manager: Any = None

    # ---------------- lifecycle ----------------
    def is_running(self) -> bool:
        return self._running

    def start(self, source: str = "webcam", stream_url: Optional[str] = None) -> Dict[str, Any]:
        # Idempotent + thread-safe. Joins happen OUTSIDE the lock (no lock juggling),
        # so concurrent /live/start calls (e.g. React StrictMode double-mount) and a
        # failed camera open can never wedge or crash the server.
        with self._start_lock:
            with self._lock:
                if self._running and source == self._source and stream_url == self._stream_url:
                    return self.status()
                need_stop = self._running or (self._thread is not None and self._thread.is_alive())
            if need_stop:
                self._stop_worker()
            with self._lock:
                self._source = source
                self._stream_url = stream_url
                self._stop.clear()
                self._error = None
                self._thread = threading.Thread(target=self._run_loop, name="live-vision", daemon=True)
                self._running = True
                self._thread.start()
        logger.info("LiveVisionService started (source=%s)", source)
        return self.status()

    def stop(self) -> Dict[str, Any]:
        with self._start_lock:
            self._stop_worker()
        return self.status()

    def _stop_worker(self) -> None:
        with self._lock:
            th = self._thread
            self._stop.set()
            self._running = False
            self._thread = None
        if th is not None and th.is_alive():
            th.join(timeout=6.0)
        with self._lock:
            if self._tracker is not None:
                self._tracker.reset()
            self._detections = []
            self._latest_jpeg = None

    # ---------------- snapshots for the API ----------------
    def status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "source": self._source,
            "stream_url": self._stream_url,
            "error": self._error,
            "fps": round(self._fps, 1),
            "latency_ms": round(self._latency_ms, 1),
            "frame_index": self._frame_index,
            "active_tracks": len(self._detections),
            "tracking": {
                "person_confidence": self.tracking_cfg.person_confidence,
                "ppe_confidence": float((self.config.get("inference") or {}).get("conf_threshold", 0.25)),
                "pose_confidence": float((self.config.get("inference") or {}).get("conf_threshold", 0.25)),
                "minimum_bbox_area": self.tracking_cfg.minimum_bbox_area,
                "minimum_visible_keypoints": self.tracking_cfg.minimum_visible_keypoints,
                "person_matching_iou": self.tracking_cfg.person_matching_iou,
                "track_timeout": self.tracking_cfg.track_timeout_frames,
                "track_buffer": self.tracking_cfg.min_hits,
            },
        }

    def detections_payload(self) -> Dict[str, Any]:
        with self._lock:
            dets = list(self._detections)
        return {
            "type": "detections",
            "frame_index": self._frame_index,
            "fps": round(self._fps, 1),
            "latency_ms": round(self._latency_ms, 1),
            "source": self._source,
            "running": self._running,
            "simulated": False,
            "detections": dets,
        }

    def latest_jpeg(self) -> Optional[bytes]:
        return self._latest_jpeg

    # ---------------- background loop ----------------
    def _ensure_built(self) -> None:
        if self._pipeline is None:
            self._pipeline = build_pipeline_from_config(self.root, self.config)
        if self._tracker is None:
            self._tracker = PersonTracker(self.tracking_cfg)
        else:
            self._tracker.reset()
        if self._event_engine is None:
            debounce = int((self.config.get("event_engine") or {}).get("debounce_frames", 15))
            self._event_engine = EventEngine(debounce_frames=debounce)
            # Wire RFID/RBAC resolver + reader (reuses existing runner helpers).
            try:
                from core.runner import setup_rfid_stack
                from hardware.rfid_registry import get_access_control, get_rfid_reader

                self._reader = setup_rfid_stack(
                    config=self.config,
                    project_root=self.root,
                    event_engine=self._event_engine,
                    vpap=self.vpap,
                )
                self._access_control = get_access_control()
                if self._reader is None:
                    self._reader = get_rfid_reader()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("RFID stack unavailable: %s", exc)
        if self._zone_manager is None:
            try:
                from security.zone_manager import build_zone_manager_from_config

                self._zone_manager = build_zone_manager_from_config(self.config)
            except Exception:
                self._zone_manager = None

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        if self._source == "esp32":
            url = self._stream_url or (self.config.get("camera") or {}).get("esp32_stream_url")
            if not url:
                self._error = "ESP32 stream URL not configured"
                return None
            try:
                from core.stream_capture import RobustHttpStreamCapture

                cam_cfg = self.config.get("camera") or {}
                return RobustHttpStreamCapture(  # type: ignore[return-value]
                    str(url),
                    reconnect_delay_s=float(cam_cfg.get("esp32_reconnect_delay_s", 2.0)),
                    open_timeout_ms=int(cam_cfg.get("esp32_open_timeout_ms", 8000)),
                    read_retries=int(cam_cfg.get("esp32_read_retries", 5)),
                    buffer_size=int(cam_cfg.get("esp32_buffer_size", 1)),
                )
            except Exception as exc:
                self._error = f"ESP32 open failed: {exc}"
                return None

        # webcam index
        cam_cfg = self.config.get("camera") or {}
        try:
            index = int(self._stream_url) if self._stream_url else int(cam_cfg.get("source", 0))
        except (TypeError, ValueError):
            index = 0
        import sys

        use_dshow = bool(cam_cfg.get("prefer_dshow", True)) and sys.platform == "win32"
        backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if use_dshow else [cv2.CAP_ANY]

        # Retry: the OS may not have released the device from a previous session
        # (rapid Stop/Start, or another app). Back off briefly instead of failing.
        for attempt in range(4):
            if self._stop.is_set():
                return None
            for backend in backends:
                cap = cv2.VideoCapture(index, backend)
                if cap.isOpened():
                    ok, _ = cap.read()
                    if ok:
                        self._error = None
                        return cap
                cap.release()
            self._error = f"Camera {index} busy — retrying ({attempt + 1}/4)"
            logger.warning("camera open attempt %d failed (index=%s)", attempt + 1, index)
            self._stop.wait(1.0)

        self._error = (
            f"Cannot open camera source {index}. It may be in use by another app "
            "or browser tab — close it and press Start again."
        )
        return None

    def _run_loop(self) -> None:
        try:
            self._ensure_built()
        except Exception as exc:
            self._error = f"init failed: {exc}"
            self._running = False
            logger.exception("LiveVisionService init failed")
            return

        cap = self._open_capture()
        if cap is None:
            self._running = False
            return

        assert self._pipeline is not None and self._tracker is not None and self._event_engine is not None
        frame_index = 0
        t_prev = time.perf_counter()
        slot = 1.0 / self.target_fps if self.target_fps > 0 else 0.0

        try:
            while not self._stop.is_set():
                t0 = time.perf_counter()
                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(0.03)
                    continue

                h, w = frame.shape[:2]
                self._frame_wh = (w, h)

                result = self._pipeline.process_frame(frame, frame_index=frame_index)
                tracks = self._tracker.update(result.structured_events, frame_index)
                self._enrich_with_rfid(tracks)

                # blockchain logging keyed on persistent track IDs (one per person)
                self._log_events(frame_index, tracks)

                annotated = self._draw_track_ids(result.annotated_bgr, tracks)
                self._encode_and_store(annotated, tracks, w, h)

                # fps / latency
                now = time.perf_counter()
                dt = now - t_prev
                t_prev = now
                if dt > 1e-6:
                    self._fps = 0.9 * self._fps + 0.1 * (1.0 / dt)
                self._latency_ms = (now - t0) * 1000.0
                self._frame_index = frame_index
                frame_index += 1

                if slot > 0:
                    elapsed = time.perf_counter() - t0
                    if elapsed < slot:
                        time.sleep(slot - elapsed)
        except Exception:
            logger.exception("LiveVisionService loop crashed")
            self._error = "loop crashed"
        finally:
            try:
                cap.release()
            except Exception:
                pass
            self._running = False
            logger.info("LiveVisionService stopped")

    # ---------------- per-frame helpers ----------------
    def _enrich_with_rfid(self, tracks: List[Track]) -> None:
        """Attach zone to every track; attach RFID identity only to the in-zone person.

        RFID NEVER creates a person — it only enriches an existing track.
        """
        for t in tracks:
            if self._zone_manager is not None:
                t.zone = self._zone_manager.zone_for_bbox(list(t.bbox))

        if self._access_control is None or self._reader is None:
            return
        # In simulation mode the reader injects synthetic UIDs on a timer; binding
        # those to a real detected person would mislabel the live card. Identity is
        # only attached from a genuine hardware scan (serial / http reader).
        if getattr(self._reader, "mode", "") == "simulation":
            return
        uid = None
        try:
            uid = self._reader.read_uid()
        except Exception:
            uid = None
        if not uid:
            return

        # Candidate = the in-zone (intrusion) track; if several, the largest (closest).
        candidates = [t for t in tracks if t.intrusion] or tracks
        if not candidates:
            return
        target = max(candidates, key=lambda t: (t.bbox[2] - t.bbox[0]) * (t.bbox[3] - t.bbox[1]))
        try:
            user = self._access_control.user_db.get_user(uid)
            zone = target.zone or self._access_control.zones.default_zone
            target.uid = uid
            if user is not None:
                target.name = user.name
                target.role = user.role
                target.authorized = self._access_control.rbac.is_allowed(user.role, user.allowed_zones, zone)
                target.decision = "AUTHORIZED" if target.authorized else "UNAUTHORIZED"
            else:
                target.name = None
                target.role = None
                target.authorized = False
                target.decision = "UNKNOWN_TAG"
        except Exception:
            logger.debug("RFID enrichment failed", exc_info=True)

    def _log_events(self, frame_index: int, tracks: List[Track]) -> None:
        if self.vpap is None or self._event_engine is None:
            return
        track_events = [
            {
                "timestamp": _now_iso(),
                "person_id": t.track_id,
                "bbox": [float(t.bbox[0]), float(t.bbox[1]), float(t.bbox[2]), float(t.bbox[3])],
                "ppe": {"helmet": t.helmet, "vest": t.vest},
                "posture": t.posture,
                "intrusion": t.intrusion,
                "confidence": t.confidence,
            }
            for t in tracks
        ]
        try:
            deb = self._event_engine.process_frame(frame_index, track_events)
        except Exception:
            return
        for d in deb:
            rec = normalize_event_record(alert_type=d.kind.value, person_id=d.person_id, observation=d.payload)
            try:
                if isinstance(self.vpap, SecureLogger):
                    self.vpap.log_event(rec)
                else:
                    self.vpap.append(rec)
            except Exception:
                pass

    def _draw_track_ids(self, annotated: Any, tracks: List[Track]) -> Any:
        out = annotated  # pipeline already drew boxes; overlay persistent IDs
        for t in tracks:
            x1, y1 = int(t.bbox[0]), int(t.bbox[1])
            color = (45, 227, 160) if (t.authorized or not t.intrusion) else (97, 77, 255)
            label = f"#{t.track_id}"
            if t.name:
                label += f" {t.name}"
            cv2.putText(out, label, (x1 + 2, max(28, y1 + 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)
        # target count badge
        cv2.putText(out, f"TRACKS: {len(tracks)}", (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (34, 211, 238), 2, cv2.LINE_AA)
        return out

    def _encode_and_store(self, annotated: Any, tracks: List[Track], w: int, h: int) -> None:
        ok, buf = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
        jpeg = buf.tobytes() if ok else None

        dets: List[Dict[str, Any]] = []
        for t in tracks:
            nb = [t.bbox[0] / w, t.bbox[1] / h, t.bbox[2] / w, t.bbox[3] / h] if w and h else [0, 0, 0, 0]
            kpts = None
            if t.keypoints:
                kpts = [[float(x) / w, float(y) / h] for x, y in t.keypoints] if w and h else None
            dets.append(
                {
                    "id": t.track_id,
                    "person_id": t.track_id,
                    "bbox": nb,
                    "bbox_px": [float(t.bbox[0]), float(t.bbox[1]), float(t.bbox[2]), float(t.bbox[3])],
                    "confidence": round(float(t.confidence), 3),
                    "helmet": t.helmet,
                    "vest": t.vest,
                    "posture": t.posture,
                    "intrusion": t.intrusion,
                    "zone": t.zone,
                    "uid": t.uid,
                    "name": t.name,
                    "role": t.role,
                    "authorized": bool(t.authorized) if t.authorized is not None else False,
                    "decision": t.decision,
                    "rfid": t.uid,
                    "state": _state_for(t),
                    "num_visible_keypoints": t.num_visible_keypoints,
                    "keypoints": kpts,
                }
            )
        with self._lock:
            self._latest_jpeg = jpeg
            self._detections = dets


# ---- process-wide singleton ----
_SERVICE: Optional[LiveVisionService] = None


def get_live_service(
    config: Optional[Dict[str, Any]] = None,
    project_root: Optional[Path] = None,
    vpap: Optional[Union[VPAPLogger, SecureLogger]] = None,
) -> LiveVisionService:
    global _SERVICE
    if _SERVICE is None:
        if config is None or project_root is None:
            raise RuntimeError("LiveVisionService not initialized")
        _SERVICE = LiveVisionService(config, project_root, vpap=vpap)
    return _SERVICE
