"""Lightweight person tracker: one persistent ID per real human.

Fixes duplicate/ghost detections without adding heavyweight deps (ByteTrack /
DeepSORT). Pipeline:

    raw detections
        -> filter   (confidence, bbox area, visible keypoints)
        -> merge    (collapse heavily-overlapping boxes, IoU > merge_iou)
        -> match    (greedy IoU association to existing tracks)
        -> age out  (drop tracks unseen for > max_age frames)

Each surviving :class:`Track` keeps a stable ``track_id`` across frames and
carries the latest PPE / posture / intrusion attributes plus optional RFID
enrichment (attached later by the live service — never created by RFID).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.geometry import bbox_center, iou_xyxy

BBox = Tuple[float, float, float, float]


@dataclass
class TrackingConfig:
    person_confidence: float = 0.45
    minimum_bbox_area: float = 1500.0          # px^2 in full-frame coords
    minimum_visible_keypoints: int = 4
    person_matching_iou: float = 0.3           # match detection -> track
    merge_iou: float = 0.6                     # collapse duplicate detections
    track_timeout_frames: int = 30             # drop track after N missed frames
    min_hits: int = 2                          # frames before a track is reported

    @classmethod
    def from_dict(cls, cfg: Optional[Dict[str, Any]]) -> "TrackingConfig":
        cfg = cfg or {}
        return cls(
            person_confidence=float(cfg.get("person_confidence", 0.45)),
            minimum_bbox_area=float(cfg.get("minimum_bbox_area", 1500.0)),
            minimum_visible_keypoints=int(cfg.get("minimum_visible_keypoints", 4)),
            person_matching_iou=float(cfg.get("person_matching_iou", 0.3)),
            merge_iou=float(cfg.get("merge_iou", 0.6)),
            track_timeout_frames=int(cfg.get("track_timeout", 30)),
            min_hits=int(cfg.get("track_buffer", 2)),
        )


@dataclass
class Track:
    track_id: int
    bbox: BBox
    confidence: float
    helmet: bool = False
    vest: bool = False
    posture: str = "Unknown"
    intrusion: bool = False
    num_visible_keypoints: int = 0
    keypoints: Optional[List[List[float]]] = None
    # bookkeeping
    hits: int = 0
    misses: int = 0
    last_frame: int = 0
    # RFID / RBAC enrichment (attached by the live service, optional)
    uid: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    zone: Optional[str] = None
    authorized: Optional[bool] = None
    decision: Optional[str] = None

    @property
    def centroid(self) -> Tuple[float, float]:
        return bbox_center(self.bbox)


def _area(b: BBox) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def filter_detections(dets: List[Dict[str, Any]], cfg: TrackingConfig) -> List[Dict[str, Any]]:
    """Drop weak / tiny / pose-less detections that produce ghost persons."""
    kept: List[Dict[str, Any]] = []
    for d in dets:
        bbox = d.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        if float(d.get("confidence", 1.0)) < cfg.person_confidence:
            continue
        if _area(tuple(bbox)) < cfg.minimum_bbox_area:
            continue
        # Pose-less boxes are usually false positives (reflections, posters).
        # Only enforce the keypoint floor when the posture pipeline ran.
        vis = int(d.get("num_visible_keypoints", 0))
        if d.get("posture", "Unknown") != "Unknown" and vis < cfg.minimum_visible_keypoints:
            continue
        kept.append(d)
    return kept


def merge_overlapping(dets: List[Dict[str, Any]], merge_iou: float) -> List[Dict[str, Any]]:
    """Collapse detections that overlap heavily — the same person seen twice."""
    merged: List[Dict[str, Any]] = []
    used = [False] * len(dets)
    # process strongest first so the surviving box is the most confident
    order = sorted(range(len(dets)), key=lambda i: -float(dets[i].get("confidence", 0.0)))
    for oi, i in enumerate(order):
        if used[i]:
            continue
        base = dets[i]
        used[i] = True
        for j in order[oi + 1 :]:
            if used[j]:
                continue
            if iou_xyxy(tuple(base["bbox"]), tuple(dets[j]["bbox"])) >= merge_iou:
                used[j] = True  # absorb the duplicate
        merged.append(base)
    return merged


class PersonTracker:
    """Greedy IoU tracker with persistent IDs and timeout-based eviction."""

    def __init__(self, config: Optional[TrackingConfig] = None) -> None:
        self.cfg = config or TrackingConfig()
        self._tracks: Dict[int, Track] = {}
        self._next_id = 1
        self._frame = 0

    def reset(self) -> None:
        self._tracks.clear()
        self._next_id = 1
        self._frame = 0

    @property
    def tracks(self) -> List[Track]:
        return list(self._tracks.values())

    def update(self, raw_detections: List[Dict[str, Any]], frame_index: int) -> List[Track]:
        """Advance the tracker one frame; returns *confirmed* active tracks."""
        self._frame = frame_index
        dets = merge_overlapping(filter_detections(raw_detections, self.cfg), self.cfg.merge_iou)

        track_ids = list(self._tracks.keys())
        # Build IoU candidate pairs (track, det) above threshold.
        pairs: List[Tuple[float, int, int]] = []
        for tid in track_ids:
            tb = self._tracks[tid].bbox
            for di, d in enumerate(dets):
                iou = iou_xyxy(tb, tuple(d["bbox"]))
                if iou >= self.cfg.person_matching_iou:
                    pairs.append((iou, tid, di))
        pairs.sort(reverse=True)

        matched_tracks: set[int] = set()
        matched_dets: set[int] = set()
        for iou, tid, di in pairs:
            if tid in matched_tracks or di in matched_dets:
                continue
            matched_tracks.add(tid)
            matched_dets.add(di)
            self._apply_detection(self._tracks[tid], dets[di])

        # Unmatched detections -> new tracks
        for di, d in enumerate(dets):
            if di in matched_dets:
                continue
            self._spawn_track(d)

        # Unmatched tracks -> age them; evict after timeout
        for tid in track_ids:
            if tid in matched_tracks:
                continue
            tr = self._tracks[tid]
            tr.misses += 1
            if tr.misses > self.cfg.track_timeout_frames:
                del self._tracks[tid]

        return self.active_tracks()

    def active_tracks(self) -> List[Track]:
        """Confirmed tracks (>= min_hits) currently visible (no current miss)."""
        out = [
            t for t in self._tracks.values()
            if t.hits >= self.cfg.min_hits and t.misses == 0
        ]
        out.sort(key=lambda t: t.track_id)
        return out

    # ----- internals -----
    def _apply_detection(self, tr: Track, d: Dict[str, Any]) -> None:
        tr.bbox = tuple(d["bbox"])  # type: ignore[assignment]
        tr.confidence = float(d.get("confidence", tr.confidence))
        ppe = d.get("ppe") or {}
        tr.helmet = bool(ppe.get("helmet", tr.helmet))
        tr.vest = bool(ppe.get("vest", tr.vest))
        tr.posture = str(d.get("posture", tr.posture))
        tr.intrusion = bool(d.get("intrusion", False))
        tr.num_visible_keypoints = int(d.get("num_visible_keypoints", tr.num_visible_keypoints))
        if d.get("keypoints") is not None:
            tr.keypoints = d["keypoints"]
        tr.hits += 1
        tr.misses = 0
        tr.last_frame = self._frame

    def _spawn_track(self, d: Dict[str, Any]) -> Track:
        ppe = d.get("ppe") or {}
        tr = Track(
            track_id=self._next_id,
            bbox=tuple(d["bbox"]),  # type: ignore[arg-type]
            confidence=float(d.get("confidence", 0.0)),
            helmet=bool(ppe.get("helmet", False)),
            vest=bool(ppe.get("vest", False)),
            posture=str(d.get("posture", "Unknown")),
            intrusion=bool(d.get("intrusion", False)),
            num_visible_keypoints=int(d.get("num_visible_keypoints", 0)),
            keypoints=d.get("keypoints"),
            hits=1,
            misses=0,
            last_frame=self._frame,
        )
        self._tracks[self._next_id] = tr
        self._next_id += 1
        return tr
