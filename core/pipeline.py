"""Edge vision pipeline: dual YOLO inference, association, tripwire, posture.

Frames may originate from a local webcam, video file, or ESP32-CAM MJPEG
(``scripts/webcam_pipeline.py --source esp32cam``); capture/reconnect lives in
``core.stream_capture`` / ``core.runner`` — inference and PrivacyGuard paths are unchanged.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import yaml
from ultralytics import YOLO

from core.geometry import bbox_center, inside_ratio_xyxy, iou_xyxy, point_inside_polygon
from core.posture import classify_posture
from core.privacy_guard import PrivacyGuard
from core.volatile_memory import VolatileFrameStore

BBox = Tuple[float, float, float, float]


def _clean_label(name: Any) -> str:
    s = str(name).strip()
    return s.rstrip(",").strip()


def _load_label_map(yaml_path: Path) -> Dict[int, str]:
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    raw = data.get("names", {})
    if isinstance(raw, dict):
        return {int(k): _clean_label(v) for k, v in raw.items()}
    return {i: _clean_label(x) for i, x in enumerate(raw)}


@dataclass
class FrameProcessResult:
    """Single frame output: structured events + optional visualization."""

    structured_events: List[Dict[str, Any]]
    annotated_bgr: np.ndarray
    inference_ms: float = 0.0


@dataclass
class EdgeVisionPipeline:
    """
    Run PPE + pose models once per frame, associate gear to persons, tripwire, posture.

    Models are loaded once; each ``process_frame`` call runs a single forward pass
    per model (no redundant inference).
    """

    project_root: Path
    ppe_model_path: Path
    pose_model_path: Path
    ppe_yaml_path: Path
    iou_person_ppe: float = 0.25
    ppe_inside_person_min: float = 0.6
    iou_pose_person: float = 0.3
    conf_threshold: float = 0.25
    posture_angles: Dict[str, float] = field(default_factory=dict)
    tripwire_enabled: bool = True
    tripwire_polygon: List[List[float]] = field(default_factory=list)
    volatile_store: Optional[VolatileFrameStore] = None
    privacy_guard: Optional[PrivacyGuard] = None
    # If > 0, run both YOLO models on a width-limited resize (faster on CPU); boxes mapped back to full frame.
    inference_max_width: int = 0

    _ppe_model: Any = field(init=False, repr=False)
    _pose_model: Any = field(init=False, repr=False)
    _label_map: Dict[int, str] = field(init=False, repr=False)
    _person_cls_id: Optional[int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.ppe_model_path = Path(self.ppe_model_path)
        self.pose_model_path = Path(self.pose_model_path)
        self.ppe_yaml_path = Path(self.ppe_yaml_path)
        self._label_map = _load_label_map(self.ppe_yaml_path)
        self._person_cls_id = next(
            (cid for cid, name in self._label_map.items() if name.lower() == "person"),
            None,
        )
        self._ppe_model = YOLO(str(self.ppe_model_path))
        self._pose_model = YOLO(str(self.pose_model_path))
        if self.volatile_store is None:
            self.volatile_store = VolatileFrameStore(maxlen=2)

    def process_frame(
        self,
        frame_bgr: np.ndarray,
        frame_index: int,
        timestamp_iso: Optional[str] = None,
    ) -> FrameProcessResult:
        """
        Run detection + pose, build structured events per person, draw overlay.

        ``timestamp_iso`` defaults to UTC ISO8601 if omitted.
        """
        t0 = time.perf_counter()
        if timestamp_iso is None:
            timestamp_iso = datetime.now(timezone.utc).isoformat()

        if self.privacy_guard is not None:
            frame_bgr = self.privacy_guard.safe_frame_view(frame_bgr)

        infer_bgr, scale_to_orig = self._letterbox_infer_size(frame_bgr, self.inference_max_width)

        pose_res = self._pose_model(
            infer_bgr,
            verbose=False,
            conf=self.conf_threshold,
        )[0]
        ppe_res = self._ppe_model(
            infer_bgr,
            verbose=False,
            conf=self.conf_threshold,
        )[0]

        inference_ms = (time.perf_counter() - t0) * 1000.0

        annotated = frame_bgr.copy()
        self._draw_tripwire(annotated)

        person_items: List[Tuple[BBox, float]] = [
            (self._scale_xyxy(b, scale_to_orig), conf) for b, conf in self._extract_person_boxes(ppe_res)
        ]
        ppe_items = [
            (self._scale_xyxy(b, scale_to_orig), cid, lab) for b, cid, lab in self._extract_ppe_items(ppe_res)
        ]
        pose_pairs = self._scale_pose_pairs(self._extract_pose_pairs(pose_res), scale_to_orig)

        self._draw_ppe_boxes_from_items(annotated, ppe_items)

        if not person_items and pose_pairs:
            # Fall back to pose person boxes (no PPE-model person); assign a neutral conf.
            person_items = [(pb, 0.5) for pb, _ in pose_pairs]

        persons = [pb for pb, _ in person_items]

        structured: List[Dict[str, Any]] = []

        smin = float(self.posture_angles.get("standing_min_deg", 60))
        smax = float(self.posture_angles.get("standing_max_deg", 100))
        sit_max = float(self.posture_angles.get("sitting_max_deg", 130))

        for pid, (pbox, pconf) in enumerate(person_items):
            assoc = self._associate_ppe(pbox, ppe_items)
            kpts = self._match_pose_keypoints(pbox, pose_pairs)
            if kpts is not None:
                raw_posture = classify_posture(
                    kpts,
                    standing_min_deg=smin,
                    standing_max_deg=smax,
                    sitting_max_deg=sit_max,
                )
                self._draw_pose_skeleton(annotated, kpts, raw_posture, fallback_id=pid)
                visible_kpts = sum(1 for x, y in kpts if x > 0.0 and y > 0.0)
            else:
                raw_posture = "Unknown"
                visible_kpts = 0

            cx, cy = bbox_center(pbox)
            intrusion = False
            if self.tripwire_enabled and len(self.tripwire_polygon) >= 3:
                intrusion = point_inside_polygon((cx, cy), self.tripwire_polygon)

            ev = {
                "timestamp": timestamp_iso,
                "person_id": pid,
                "bbox": [float(pbox[0]), float(pbox[1]), float(pbox[2]), float(pbox[3])],
                "confidence": float(pconf),
                "num_visible_keypoints": int(visible_kpts),
                "ppe": {"helmet": assoc["helmet"], "vest": assoc["vest"]},
                "posture": raw_posture,
                "intrusion": intrusion,
            }
            structured.append(ev)

            self._draw_person_overlay(annotated, pbox, pid, assoc, raw_posture, intrusion)

        self.volatile_store.push(annotated)
        if self.privacy_guard is not None:
            self.privacy_guard.enforce_memory_only(self.volatile_store)

        return FrameProcessResult(
            structured_events=structured,
            annotated_bgr=annotated,
            inference_ms=inference_ms,
        )

    @staticmethod
    def _letterbox_infer_size(bgr: np.ndarray, max_width: int) -> Tuple[np.ndarray, float]:
        """Return (image_for_yolo, multiply_to_map_coords_to_original)."""
        if max_width <= 0:
            return bgr, 1.0
        h, w = bgr.shape[:2]
        if w <= max_width:
            return bgr, 1.0
        nw = int(max_width)
        nh = max(1, int(round(h * (nw / float(w)))))
        small = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_AREA)
        return small, w / float(nw)

    @staticmethod
    def _scale_xyxy(box: BBox, s: float) -> BBox:
        return (box[0] * s, box[1] * s, box[2] * s, box[3] * s)

    @staticmethod
    def _scale_pose_pairs(
        pairs: List[Tuple[BBox, List[List[float]]]],
        s: float,
    ) -> List[Tuple[BBox, List[List[float]]]]:
        out: List[Tuple[BBox, List[List[float]]]] = []
        for pbox, kpts in pairs:
            nk = [[float(x) * s, float(y) * s] for x, y in kpts]
            out.append((EdgeVisionPipeline._scale_xyxy(pbox, s), nk))
        return out

    def _draw_all_ppe_boxes(self, frame: np.ndarray, ppe_res: Any) -> None:
        """Draw every PPE detector box (legacy demo behavior)."""
        if ppe_res.boxes is None or len(ppe_res.boxes) == 0:
            return
        boxes = ppe_res.boxes
        xyxy = boxes.xyxy.cpu().numpy()
        cls = boxes.cls.cpu().numpy().astype(int)
        for i in range(len(xyxy)):
            c = int(cls[i])
            label = self._label_map.get(c, str(c))
            x1, y1, x2, y2 = map(int, xyxy[i])
            low = label.lower()
            if "no-" in low or "no_" in low:
                color = (0, 0, 255)
            else:
                color = (0, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)
            cv2.putText(
                frame,
                label,
                (x1, max(12, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                1,
                cv2.LINE_AA,
            )

    def _draw_ppe_boxes_from_items(self, frame: np.ndarray, items: List[Tuple[BBox, int, str]]) -> None:
        """Draw PPE boxes from already-scaled (full-frame) item list."""
        for box, _cid, label in items:
            x1, y1, x2, y2 = map(int, box)
            low = label.lower()
            if "no-" in low or "no_" in low:
                color = (0, 0, 255)
            else:
                color = (0, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)
            cv2.putText(
                frame,
                label,
                (x1, max(12, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                1,
                cv2.LINE_AA,
            )

    def _draw_tripwire(self, frame: np.ndarray) -> None:
        if not self.tripwire_enabled or len(self.tripwire_polygon) < 3:
            return
        pts = np.array(self.tripwire_polygon, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(frame, [pts], isClosed=True, color=(255, 128, 0), thickness=2)
        cv2.putText(
            frame,
            "TRIPWIRE",
            (pts[0][0][0], max(20, pts[0][0][1] - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 128, 0),
            1,
            cv2.LINE_AA,
        )

    def _extract_person_boxes(self, ppe_res: Any) -> List[Tuple[BBox, float]]:
        """Return person boxes with detection confidence: ``[(bbox, conf), ...]``."""
        out: List[Tuple[BBox, float]] = []
        if ppe_res.boxes is None or len(ppe_res.boxes) == 0:
            return out
        boxes = ppe_res.boxes
        xyxy = boxes.xyxy.cpu().numpy()
        cls = boxes.cls.cpu().numpy().astype(int)
        conf = (
            boxes.conf.cpu().numpy()
            if getattr(boxes, "conf", None) is not None
            else np.ones(len(xyxy), dtype=float)
        )
        for i in range(len(xyxy)):
            c = int(cls[i])
            name = self._label_map.get(c, "").lower()
            is_person = (self._person_cls_id is not None and c == self._person_cls_id) or (
                "person" in name and self._person_cls_id is None
            )
            if is_person:
                out.append((tuple(map(float, xyxy[i])), float(conf[i])))
        # sort top-to-bottom, left-to-right for stable ordering
        out.sort(key=lambda item: (item[0][1], item[0][0]))
        return out

    def _extract_ppe_items(self, ppe_res: Any) -> List[Tuple[BBox, int, str]]:
        items: List[Tuple[BBox, int, str]] = []
        if ppe_res.boxes is None or len(ppe_res.boxes) == 0:
            return items
        boxes = ppe_res.boxes
        xyxy = boxes.xyxy.cpu().numpy()
        cls = boxes.cls.cpu().numpy().astype(int)
        for i in range(len(xyxy)):
            c = int(cls[i])
            label = self._label_map.get(c, str(c))
            if self._person_cls_id is not None and c == self._person_cls_id:
                continue
            if "person" in label.lower() and self._person_cls_id is None:
                continue
            items.append((tuple(map(float, xyxy[i])), c, label))
        return items

    def _extract_pose_pairs(self, pose_res: Any) -> List[Tuple[BBox, List[List[float]]]]:
        pairs: List[Tuple[BBox, List[List[float]]]] = []
        if pose_res.boxes is None or len(pose_res.boxes) == 0:
            return pairs
        if pose_res.keypoints is None:
            return pairs
        boxes = pose_res.boxes.xyxy.cpu().numpy()
        kxy = pose_res.keypoints.xy
        if hasattr(kxy, "cpu"):
            kxy = kxy.cpu().numpy()
        for i in range(len(boxes)):
            kp = kxy[i].tolist()
            pairs.append((tuple(map(float, boxes[i])), kp))
        return pairs

    def _associate_ppe(self, person_box: BBox, items: List[Tuple[BBox, int, str]]) -> Dict[str, bool]:
        helmet_pos = 0.0
        helmet_neg = 0.0
        vest_pos = 0.0
        vest_neg = 0.0

        for box, _cid, label in items:
            # Helmet/vest boxes are much smaller than person boxes; pure IoU can be near 0
            # even when PPE is correctly inside the person region.
            ov_iou = iou_xyxy(person_box, box)
            ov_inside = inside_ratio_xyxy(person_box, box)
            cx = (box[0] + box[2]) / 2.0
            cy = (box[1] + box[3]) / 2.0
            center_inside = (
                person_box[0] <= cx <= person_box[2]
                and person_box[1] <= cy <= person_box[3]
            )
            matched = (
                ov_iou >= self.iou_person_ppe
                or ov_inside >= self.ppe_inside_person_min
                or (center_inside and ov_inside >= 0.2)
            )
            if not matched:
                continue
            score = max(ov_iou, ov_inside)
            low = label.lower()
            if "hardhat" in low or "helmet" in low:
                if "no-" in low or "no_" in low:
                    helmet_neg = max(helmet_neg, score)
                else:
                    helmet_pos = max(helmet_pos, score)
            if "vest" in low:
                if "no-" in low or "no_" in low:
                    vest_neg = max(vest_neg, score)
                else:
                    vest_pos = max(vest_pos, score)

        if helmet_pos == 0.0 and helmet_neg == 0.0:
            helmet = False
        elif helmet_neg > helmet_pos:
            helmet = False
        elif helmet_pos > helmet_neg:
            helmet = True
        else:
            helmet = helmet_pos >= self.iou_person_ppe

        if vest_pos == 0.0 and vest_neg == 0.0:
            vest = False
        elif vest_neg > vest_pos:
            vest = False
        elif vest_pos > vest_neg:
            vest = True
        else:
            vest = vest_pos >= self.iou_person_ppe

        return {"helmet": helmet, "vest": vest}

    def _match_pose_keypoints(
        self,
        person_box: BBox,
        pose_pairs: List[Tuple[BBox, List[List[float]]]],
    ) -> Optional[List[List[float]]]:
        best_iou = 0.0
        best_kp: Optional[List[List[float]]] = None
        for pbox, kpts in pose_pairs:
            ov = iou_xyxy(person_box, pbox)
            if ov > best_iou:
                best_iou = ov
                best_kp = kpts
        if best_iou < self.iou_pose_person or best_kp is None:
            return None
        return best_kp

    def _draw_person_overlay(
        self,
        frame: np.ndarray,
        box: BBox,
        pid: int,
        assoc: Dict[str, bool],
        posture: str,
        intrusion: bool,
    ) -> None:
        x1, y1, x2, y2 = map(int, box)
        color = (0, 200, 0) if assoc["helmet"] and assoc["vest"] else (0, 140, 255)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        h_ok = "H:OK" if assoc["helmet"] else "H:NO"
        v_ok = "V:OK" if assoc["vest"] else "V:NO"
        intr = "INTRUSION" if intrusion else ""
        line1 = f"ID:{pid} {h_ok} {v_ok} | {posture}"
        line2 = intr
        cv2.putText(
            frame,
            line1,
            (x1, max(15, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )
        if line2:
            cv2.putText(
                frame,
                line2,
                (x1, max(30, y1 - 24)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )

    def _draw_pose_skeleton(
        self,
        frame: np.ndarray,
        kpts: List[List[float]],
        posture: str,
        fallback_id: int,
    ) -> None:
        for x, y in kpts:
            cv2.circle(frame, (int(x), int(y)), 3, (0, 255, 120), -1)
        if kpts:
            hx = int((kpts[11][0] + kpts[12][0]) / 2)
            hy = int((kpts[11][1] + kpts[12][1]) / 2) - 10
            cv2.putText(
                frame,
                f"pose:{fallback_id} {posture}",
                (hx, hy),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )


def _resolve_path(project_root: Path, path_str: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else (Path(project_root) / p).resolve()


def build_pipeline_from_config(
    project_root: Path,
    config: Dict[str, Any],
) -> EdgeVisionPipeline:
    """Construct :class:`EdgeVisionPipeline` from a loaded ``config.yaml`` dict."""
    models = config.get("models", {})
    inf = config.get("inference", {})
    posture = config.get("posture", {})
    tw = config.get("tripwire", {})
    priv = config.get("privacy", {})
    allow_export = bool(priv.get("allow_video_export", False))
    privacy_guard = PrivacyGuard(Path(project_root), allow_video_export=allow_export)

    pr = Path(project_root)
    ppe_w = _resolve_path(pr, models.get("ppe_weights", "models/yolov8n-ppe.pt"))
    pose_w = _resolve_path(pr, models.get("pose_weights", "models/yolov8n-pose.pt"))
    ppe_y = _resolve_path(pr, models.get("ppe_class_yaml", "models/ppe.yaml"))

    return EdgeVisionPipeline(
        project_root=pr,
        ppe_model_path=ppe_w,
        pose_model_path=pose_w,
        ppe_yaml_path=ppe_y,
        iou_person_ppe=float(inf.get("iou_person_ppe", 0.25)),
        ppe_inside_person_min=float(inf.get("ppe_inside_person_min", 0.6)),
        iou_pose_person=float(inf.get("iou_pose_person", 0.3)),
        conf_threshold=float(inf.get("conf_threshold", 0.25)),
        posture_angles=dict(posture),
        tripwire_enabled=bool(tw.get("enabled", True)),
        tripwire_polygon=list(tw.get("polygon", [])),
        volatile_store=VolatileFrameStore(maxlen=int(priv.get("volatile_frame_buffer_size", 2))),
        privacy_guard=privacy_guard,
        inference_max_width=int(inf.get("max_inference_width", 640)),
    )
