"""Tests for the live tracking + detection-building path (no camera/YOLO needed).

Proves the dashboard-facing guarantees:
  * heavily-overlapping detections of one person -> ONE tracked card
  * a real second person -> a second card with a distinct persistent ID
  * a person leaving -> card removed after the timeout
  * RFID enriches an existing track; it never creates a new one
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.tracker import PersonTracker, TrackingConfig
from core.live_service import LiveVisionService


def _det(bbox, conf=0.9, helmet=True, vest=True, posture="Standing", intrusion=False, kpts=6):
    return {
        "bbox": list(bbox),
        "confidence": conf,
        "num_visible_keypoints": kpts,
        "posture": posture,
        "ppe": {"helmet": helmet, "vest": vest},
        "intrusion": intrusion,
    }


@pytest.fixture()
def cfg():
    return TrackingConfig(
        person_confidence=0.4,
        minimum_bbox_area=100,
        minimum_visible_keypoints=0,
        person_matching_iou=0.3,
        merge_iou=0.6,
        track_timeout_frames=3,
        min_hits=1,
    )


def test_one_person_one_track(cfg):
    tr = PersonTracker(cfg)
    # same person, two overlapping detections in one frame
    active = tr.update([_det([100, 100, 200, 400]), _det([104, 103, 205, 402], conf=0.7)], 0)
    assert len(active) == 1
    pid = active[0].track_id
    # next frame, slight move -> same id
    active = tr.update([_det([108, 106, 208, 406])], 1)
    assert len(active) == 1 and active[0].track_id == pid


def test_two_real_persons(cfg):
    tr = PersonTracker(cfg)
    active = tr.update([_det([100, 100, 200, 400]), _det([500, 100, 600, 400])], 0)
    assert len(active) == 2
    assert {t.track_id for t in active} == {1, 2}


def test_person_leaves_track_removed(cfg):
    tr = PersonTracker(cfg)
    tr.update([_det([100, 100, 200, 400])], 0)
    assert len(tr.active_tracks()) == 1
    # no detections for > timeout frames
    for f in range(1, 6):
        tr.update([], f)
    assert len(tr.active_tracks()) == 0


def test_service_builds_real_detection_json():
    """LiveVisionService produces card JSON straight from tracks (no mock people)."""
    svc = LiveVisionService(config={"tracking": {"track_buffer": 1}}, project_root=ROOT, vpap=None)
    svc._tracker = PersonTracker(TrackingConfig(minimum_bbox_area=100, minimum_visible_keypoints=0, min_hits=1))
    svc._zone_manager = None
    svc._access_control = None
    svc._reader = None
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    tracks = svc._tracker.update([_det([100, 100, 200, 400]), _det([103, 102, 204, 402], conf=0.7)], 0)
    svc._enrich_with_rfid(tracks)
    svc._encode_and_store(frame, tracks, 640, 480)
    payload = svc.detections_payload()

    assert payload["simulated"] is False
    assert len(payload["detections"]) == 1  # one person, not two
    d = payload["detections"][0]
    assert d["id"] == d["person_id"]
    assert d["name"] is None  # no RFID -> Unknown (frontend shows "Unknown")
    assert d["rfid"] is None
    # normalized bbox within [0,1]
    assert all(0.0 <= v <= 1.0 for v in d["bbox"])


def test_rfid_enriches_not_creates():
    """A scan attaches a profile to an existing track without adding a card."""

    class _User:
        name = "Site Engineer"
        role = "Engineer"
        allowed_zones = ["ZoneA"]

    class _DB:
        def get_user(self, uid):
            return _User() if uid == "I9:J0:K1:L2" else None

    class _RBAC:
        def is_allowed(self, role, zones, zone):
            return zone in zones

    class _Zones:
        default_zone = "ZoneA"

    class _AC:
        user_db = _DB()
        rbac = _RBAC()
        zones = _Zones()

    class _Reader:
        def read_uid(self):
            return "I9:J0:K1:L2"

    svc = LiveVisionService(config={}, project_root=ROOT, vpap=None)
    svc._tracker = PersonTracker(TrackingConfig(minimum_bbox_area=100, minimum_visible_keypoints=0, min_hits=1))
    svc._access_control = _AC()
    svc._reader = _Reader()

    class _ZM:
        default_zone = "ZoneA"

        def zone_for_bbox(self, bbox):
            return "ZoneA"

    svc._zone_manager = _ZM()

    tracks = svc._tracker.update([_det([100, 100, 200, 400], intrusion=True)], 0)
    svc._enrich_with_rfid(tracks)
    assert len(tracks) == 1  # still one person
    t = tracks[0]
    assert t.name == "Site Engineer" and t.role == "Engineer"
    assert t.uid == "I9:J0:K1:L2"
    assert t.authorized is True
