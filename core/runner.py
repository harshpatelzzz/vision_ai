"""Shared capture loop: FPS, events, VPAP, optional video writer, hardware tamper."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

from core.event_engine import EventEngine
from core.pipeline import EdgeVisionPipeline
from security.logger import SecureLogger, VPAPLogger, normalize_event_record

_tamper_log_handler: Optional[logging.FileHandler] = None


def _get_tamper_logger(project_root: Path) -> logging.Logger:
    """Dedicated file logger for tamper events → logs/tamper.log."""
    global _tamper_log_handler
    tlog = logging.getLogger("posevision.tamper")
    if _tamper_log_handler is None:
        log_path = project_root / "logs" / "tamper.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        _tamper_log_handler = logging.FileHandler(str(log_path))
        _tamper_log_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        tlog.addHandler(_tamper_log_handler)
        tlog.setLevel(logging.DEBUG)
    return tlog


def setup_hardware_monitor(
    config: Dict[str, Any],
    project_root: Path,
    event_engine: EventEngine,
    vpap: Optional[Union[VPAPLogger, SecureLogger]],
    pipeline: EdgeVisionPipeline,
    stop_flag: threading.Event,
) -> Optional[Any]:
    """
    Initialize HardwareMonitor from config if ``hardware_security.enabled`` is True.

    Registers a tamper callback that:
      1. Signals the main loop to stop
      2. Emits a TAMPER_DETECTED event via the event engine and VPAP chain
      3. Logs to both console and logs/tamper.log
      4. Runs full zeroization (wipe logs, RAM, optional models, optional shutdown)

    Returns the HardwareMonitor instance (or None when disabled).
    """
    hw_cfg = config.get("hardware_security", {})
    if not hw_cfg.get("enabled", False):
        return None

    from core.hardware_monitor import HardwareMonitor
    from security.zeroization import full_zeroization

    monitor = HardwareMonitor(
        mode=hw_cfg.get("mode", "simulation"),
        gpio_pin=int(hw_cfg.get("gpio_pin", 17)),
        serial_port=str(hw_cfg.get("serial_port", "/dev/ttyUSB0")),
        baudrate=int(hw_cfg.get("baudrate", 115200)),
    )

    zero_cfg = config.get("zeroization", {})
    tlog = _get_tamper_logger(project_root)

    def on_tamper_detected() -> None:
        tlog.critical("TAMPER DETECTED — initiating emergency sequence")

        stop_flag.set()

        tamper_ev = event_engine.emit_tamper_event()
        if vpap is not None:
            pl = tamper_ev.payload if isinstance(tamper_ev.payload, dict) else {"detail": tamper_ev.payload}
            rec_payload = {**pl}
            rec_payload.setdefault("bbox", [0.0, 0.0, 0.0, 0.0])
            rec_payload.setdefault("ppe", {"helmet": False, "vest": False})
            rec_payload.setdefault("posture", "Unknown")
            rec_payload.setdefault("intrusion", False)
            rec = normalize_event_record(
                alert_type=tamper_ev.kind.value,
                person_id=tamper_ev.person_id,
                observation=rec_payload,
            )
            if isinstance(vpap, SecureLogger):
                vpap.append_forced(rec)
            else:
                vpap.append(rec)

        volatile = getattr(pipeline, "volatile_store", None)
        full_zeroization(
            project_root=project_root,
            log_dir=zero_cfg.get("log_dir", "logs/"),
            delete_models=bool(zero_cfg.get("delete_models", False)),
            shutdown_on_tamper=bool(zero_cfg.get("shutdown_on_tamper", False)),
            volatile_store=volatile,
        )

    monitor.register_callback(on_tamper_detected)
    monitor.start()
    return monitor


def setup_esp32_sensor_stack(
    config: Dict[str, Any],
    project_root: Path,
    event_engine: EventEngine,
    vpap: Optional[Union[VPAPLogger, SecureLogger]],
    stop_flag: threading.Event,
) -> Tuple[Optional[Any], Optional[Any], Optional[Any]]:
    """
    Optional ESP32 JSON telemetry → tamper-evident log (no zeroization unless configured).

    Returns ``(telemetry_store, sensor_daemon_thread, tamper_bridge_thread)``.
    """
    cfg = config.get("esp32_telemetry") or {}
    if not cfg.get("enabled", False):
        return None, None, None

    from hardware.hardware_monitor import Esp32TelemetryTamperBridge, TelemetryThresholds
    from hardware.sensor_daemon import SensorDaemon
    from hardware.telemetry_store import TelemetryStore

    store = TelemetryStore()
    thr = cfg.get("thresholds") or {}
    thresholds = TelemetryThresholds(
        temp_max_c=float(thr.get("temp_max_c", 55.0)),
        distance_min_mm=float(thr.get("distance_min_mm", 50.0)),
        distance_max_mm=float(thr.get("distance_max_mm", 8000.0)),
        light_trigger_above=(
            float(thr["light_trigger_above"]) if thr.get("light_trigger_above") is not None else None
        ),
        orientation_delta_deg=float(thr.get("orientation_delta_deg", 35.0)),
    )

    tlog = _get_tamper_logger(project_root)

    def on_sensor_tamper(reason: str, snap: Dict[str, Any]) -> None:
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).isoformat()
        tel = {k: v for k, v in snap.items() if not str(k).startswith("_")}
        observation: Dict[str, Any] = {
            "timestamp": ts,
            "bbox": [0.0, 0.0, 0.0, 0.0],
            "ppe": {"helmet": False, "vest": False},
            "posture": "Unknown",
            "intrusion": False,
            "telemetry": tel,
            "tamper_reason": reason,
        }
        event_engine.emit_tamper_event({**observation, "source": "esp32_sensors"})
        if vpap is not None:
            rec = normalize_event_record(
                alert_type="TAMPER_DETECTED",
                person_id=-1,
                observation=observation,
            )
            vpap.append_forced(rec)
        tlog.critical("ESP32 telemetry tamper [%s]", reason)
        if bool(cfg.get("halt_pipeline_on_tamper", False)):
            stop_flag.set()
        if bool(cfg.get("trigger_zeroization", False)):
            from security.zeroization import full_zeroization

            zero_cfg = config.get("zeroization", {})
            full_zeroization(
                project_root=project_root,
                log_dir=zero_cfg.get("log_dir", "logs/"),
                delete_models=bool(zero_cfg.get("delete_models", False)),
                shutdown_on_tamper=bool(zero_cfg.get("shutdown_on_tamper", False)),
                volatile_store=None,
            )

    daemon: Optional[SensorDaemon] = None
    port = cfg.get("serial_port")
    poll_url = cfg.get("http_poll_url")
    if port or poll_url:
        daemon = SensorDaemon(
            store,
            serial_port=str(port) if port else None,
            baudrate=int(cfg.get("baudrate", 115200)),
            http_poll_url=str(poll_url) if poll_url else None,
            poll_interval_s=float(cfg.get("poll_interval_s", 0.5)),
        )
        daemon.start()

    bridge = Esp32TelemetryTamperBridge(
        store,
        thresholds,
        on_sensor_tamper,
        poll_interval_s=float(cfg.get("eval_interval_s", 0.15)),
        latch=bool(cfg.get("latch_tamper", True)),
    )
    bridge.start()
    return store, daemon, bridge


def build_rfid_runtime(
    config: Dict[str, Any],
    project_root: Path,
    vpap: Optional[Union[VPAPLogger, SecureLogger]],
) -> Optional[Tuple[Any, Any]]:
    """
    Build + start the RFID reader and AccessControl, register them, return both.

    Idempotent: if a reader + access control are already registered (e.g. started
    at API boot), the existing pair is reused so the dashboard, live pipeline and
    API all share one reader. Returns ``(reader, access_control)`` or ``None`` when
    ``rfid.enabled`` is False.

    In every mode each scan is evaluated against the default zone (a "badge tap at
    the gate" — independent of the camera), so the RFID Access page shows live
    grant/deny decisions on its own. The live pipeline additionally re-evaluates
    per detected person via the EventEngine resolver.
    """
    rfid_cfg = config.get("rfid") or {}
    if not rfid_cfg.get("enabled", False):
        return None

    from hardware.rfid_registry import get_access_control, get_rfid_reader, register_rfid

    existing_reader = get_rfid_reader()
    existing_ac = get_access_control()
    if existing_reader is not None and existing_ac is not None:
        return existing_reader, existing_ac

    from hardware.rfid_reader import RfidReader
    from security.access_control import build_access_control_from_config

    tlog = _get_tamper_logger(project_root)

    reader = RfidReader(
        mode=str(rfid_cfg.get("mode", "simulation")),
        serial_port=(str(rfid_cfg["serial_port"]) if rfid_cfg.get("serial_port") else None),
        baudrate=int(rfid_cfg.get("baudrate", 115200)),
        http_poll_url=(str(rfid_cfg["http_poll_url"]) if rfid_cfg.get("http_poll_url") else None),
        poll_interval_s=float(rfid_cfg.get("poll_interval_s", 0.3)),
        dedup_seconds=float(rfid_cfg.get("scan_dedup_seconds", 1.5)),
        correlation_window_seconds=float(rfid_cfg.get("correlation_window_seconds", 5.0)),
        simulation_uids=list(rfid_cfg.get("simulation_uids") or []),
    )

    def on_security_alert(alert_type: str, detail: Dict[str, Any]) -> None:
        tlog.critical("RFID %s %s", alert_type, detail)
        if vpap is None:
            return
        observation: Dict[str, Any] = {
            "timestamp": detail.get("timestamp", ""),
            "bbox": [0.0, 0.0, 0.0, 0.0],
            "ppe": {"helmet": False, "vest": False},
            "posture": "Unknown",
            "intrusion": True,
            "access": detail,
        }
        rec = normalize_event_record(alert_type=alert_type, person_id=-1, observation=observation)
        if isinstance(vpap, SecureLogger):
            vpap.append_forced(rec)
        else:
            vpap.append(rec)

    access_control = build_access_control_from_config(
        config,
        project_root,
        uid_provider=reader.read_uid,
        on_security_alert=on_security_alert,
    )

    # Each badge tap -> an access decision against the default zone (gate reader).
    default_zone = access_control.zones.default_zone

    def on_scan(scan: Any) -> None:
        try:
            access_control.evaluate(scan.uid, default_zone)
        except Exception:
            pass

    reader.set_on_scan(on_scan)
    reader.start_reader()
    register_rfid(reader=reader, access_control=access_control)
    tlog.info("RFID runtime started (mode=%s, gate-zone=%s)", reader.mode, default_zone)
    return reader, access_control


def setup_rfid_stack(
    config: Dict[str, Any],
    project_root: Path,
    event_engine: EventEngine,
    vpap: Optional[Union[VPAPLogger, SecureLogger]],
) -> Optional[Any]:
    """
    Wire the RFID + RBAC authorization layer to ``event_engine`` for the live
    pipeline: builds/reuses the shared reader + AccessControl and installs
    ``access_control.resolve_intrusion`` as the EventEngine access resolver so
    intrusions become AUTHORIZED_ACCESS / ZONE_VIOLATION / UNKNOWN_RFID /
    UNAUTHORIZED_INTRUSION. Returns the reader (or None when disabled).
    """
    runtime = build_rfid_runtime(config, project_root, vpap)
    if runtime is None:
        return None
    reader, access_control = runtime
    event_engine.set_access_resolver(access_control.resolve_intrusion)
    return reader


def run_edge_loop(
    cap: cv2.VideoCapture,
    pipeline: EdgeVisionPipeline,
    event_engine: EventEngine,
    vpap: Optional[Union[VPAPLogger, SecureLogger]],
    *,
    view: bool = True,
    window_name: str = "PoseVision Edge",
    save_video_path: Optional[Path] = None,
    log_debounced: bool = True,
    log_structured: bool = False,
    logger: Optional[logging.Logger] = None,
    config: Optional[Dict[str, Any]] = None,
    project_root: Optional[Path] = None,
    telemetry_store: Optional[Any] = None,
    esp32_daemon: Optional[Any] = None,
    esp32_tamper_bridge: Optional[Any] = None,
    target_fps: Optional[float] = None,
) -> None:
    """
    Read frames until stream ends, user presses ``q``, or tamper is detected.

    When ``config`` contains ``hardware_security.enabled: true``, the hardware
    monitor is started and tamper events trigger pipeline halt + zeroization.
    """
    log = logger or logging.getLogger("posevision")
    stop_flag = threading.Event()

    hw_monitor = None
    rfid_reader = None
    if config is not None and project_root is not None:
        hw_monitor = setup_hardware_monitor(
            config=config,
            project_root=project_root,
            event_engine=event_engine,
            vpap=vpap,
            pipeline=pipeline,
            stop_flag=stop_flag,
        )
        rfid_reader = setup_rfid_stack(
            config=config,
            project_root=project_root,
            event_engine=event_engine,
            vpap=vpap,
        )

    if (
        telemetry_store is None
        and esp32_daemon is None
        and esp32_tamper_bridge is None
        and config is not None
        and project_root is not None
    ):
        ts, dm, br = setup_esp32_sensor_stack(
            config=config,
            project_root=project_root,
            event_engine=event_engine,
            vpap=vpap,
            stop_flag=stop_flag,
        )
        telemetry_store, esp32_daemon, esp32_tamper_bridge = ts, dm, br
        if telemetry_store is not None:
            try:
                from hardware.registry import register_live_hardware

                stream_u = ""
                cam = (config.get("camera") or {}).get("esp32_stream_url") or ""
                stream_u = str(cam)
                register_live_hardware(telemetry_store, stream_url=stream_u)
            except Exception:
                pass

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps_cap = cap.get(cv2.CAP_PROP_FPS) or 30.0

    export_path: Optional[Path] = None
    if save_video_path is not None:
        candidate = Path(save_video_path)
        pg = getattr(pipeline, "privacy_guard", None)
        if pg is None or pg.assert_export_allowed(candidate):
            export_path = candidate

    writer: Optional[cv2.VideoWriter] = None
    writer_pending_path: Optional[Path] = export_path

    frame_index = 0
    t_prev = time.perf_counter()
    fps_smooth = 0.0
    stream_http = hasattr(cap, "url")
    window_ready = False

    try:
        while not stop_flag.is_set():
            t_frame_start = time.perf_counter()
            ret, frame = cap.read()
            if not ret or frame is None:
                if stream_http:
                    log.warning("Stream frame unavailable — retrying")
                    time.sleep(0.05)
                    continue
                break

            fh, fw = frame.shape[0], frame.shape[1]
            if view and not window_ready:
                try:
                    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                    window_ready = True
                except Exception:
                    log.warning("Could not create OpenCV window (headless display?)")
                    window_ready = True

            if view and frame_index == 0:
                hint = frame.copy()
                cv2.putText(
                    hint,
                    "Running AI on first frame (please wait)...",
                    (10, min(40, fh - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 255, 200),
                    2,
                    cv2.LINE_AA,
                )
                cv2.imshow(window_name, hint)
                cv2.waitKey(1)

            if width <= 0 or height <= 0:
                width, height = fw, fh
            if writer is None and writer_pending_path is not None:
                writer_pending_path.parent.mkdir(parents=True, exist_ok=True)
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(
                    str(writer_pending_path),
                    fourcc,
                    float(fps_cap),
                    (fw, fh),
                )
                writer_pending_path = None

            t_now = time.perf_counter()
            dt = t_now - t_prev
            t_prev = t_now
            if dt > 1e-6:
                fps_smooth = 0.9 * fps_smooth + 0.1 * (1.0 / dt)

            result = pipeline.process_frame(frame, frame_index=frame_index)
            deb = event_engine.process_frame(frame_index, result.structured_events)

            if log_structured and result.structured_events:
                for ev in result.structured_events:
                    log.info("frame_event %s", ev)

            for d in deb:
                if log_debounced:
                    log.warning(
                        "ALERT %s person=%s %s",
                        d.kind.value,
                        d.person_id,
                        d.payload,
                    )
                if vpap is not None:
                    payload = normalize_event_record(
                        alert_type=d.kind.value,
                        person_id=d.person_id,
                        observation=d.payload,
                    )
                    if isinstance(vpap, SecureLogger):
                        vpap.log_event(payload)
                    else:
                        vpap.append(payload)

            vis = result.annotated_bgr.copy()
            tel_snap = telemetry_store.snapshot() if telemetry_store is not None else {}
            chain_tip = ""
            if vpap is not None:
                try:
                    chain_tip = str(getattr(vpap, "prev_hash", "") or "")[:16]
                except Exception:
                    chain_tip = ""

            deb_summary = ""
            if deb:
                deb_summary = f"{deb[-1].kind.value}"

            _draw_fps(vis, fps_smooth)
            _draw_edge_hud(
                vis,
                structured_events=result.structured_events,
                telemetry_snapshot=tel_snap,
                blockchain_tip=chain_tip,
                debounced_hint=deb_summary,
            )

            if writer is not None:
                writer.write(vis)

            if view:
                cv2.imshow(window_name, vis)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            frame_index += 1

            if target_fps is not None and target_fps > 0:
                elapsed = time.perf_counter() - t_frame_start
                slot = 1.0 / float(target_fps)
                if elapsed < slot:
                    time.sleep(slot - elapsed)

        if stop_flag.is_set():
            log.critical("Pipeline halted by tamper detection")

    finally:
        if esp32_tamper_bridge is not None:
            try:
                esp32_tamper_bridge.stop()
            except Exception:
                pass
        if esp32_daemon is not None:
            try:
                esp32_daemon.stop()
                esp32_daemon.join(timeout=3.0)
            except Exception:
                pass
        if rfid_reader is not None:
            try:
                rfid_reader.stop()
            except Exception:
                pass
        if hw_monitor is not None:
            hw_monitor.stop()
        if writer is not None:
            writer.release()
        cap.release()
        if view:
            cv2.destroyAllWindows()


def _draw_fps(frame: np.ndarray, fps: float) -> None:
    label = f"FPS: {fps:.1f}"
    cv2.putText(
        frame,
        label,
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )


def _draw_edge_hud(
    frame: np.ndarray,
    *,
    structured_events: List[Dict[str, Any]],
    telemetry_snapshot: Dict[str, Any],
    blockchain_tip: str,
    debounced_hint: str,
) -> None:
    h, w = frame.shape[:2]
    intrusion_any = any(bool(e.get("intrusion")) for e in structured_events)
    ppe_bits: List[str] = []
    for e in structured_events:
        ppe = e.get("ppe") or {}
        pid = int(e.get("person_id", -1))
        hs = "H+" if ppe.get("helmet") else "H-"
        vs = "V+" if ppe.get("vest") else "V-"
        ppe_bits.append(f"P{pid}:{hs}{vs}")
    ppe_line = " ".join(ppe_bits) if ppe_bits else "PPE: —"

    posture_line = ""
    if structured_events:
        posture_line = " | ".join(
            f"P{int(e.get('person_id', -1))}:{e.get('posture', '?')}" for e in structured_events[:4]
        )

    tel_tamper = telemetry_snapshot.get("tamper")
    lines = [
        f"Intrusion: {'YES' if intrusion_any else 'no'} | {ppe_line}",
        posture_line[: max(1, w // 6)],
        f"Blockchain tip: {blockchain_tip or '—'} | Alert: {debounced_hint or '—'}",
        f"Sensors tamper: {tel_tamper} | link {'OK' if telemetry_snapshot.get('_connected') else '—'}",
    ]

    y0 = h - 22 * len(lines) - 8
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        y = y0 + i * 22
        cv2.putText(
            frame,
            line[:180],
            (12, max(40, y)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (220, 240, 255),
            1,
            cv2.LINE_AA,
        )


