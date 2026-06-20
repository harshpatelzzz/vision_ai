"""Tests for the RFID + RBAC access-control layer.

Run with:  pytest tests/test_rfid_access.py -v
No hardware required (RFID reader exercised via ``ingest`` + simulation).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.event_engine import EventEngine, HighLevelEvent
from hardware.rfid_reader import RfidReader
from security.access_control import AccessControl, AccessDecision, build_access_control_from_config
from security.rbac import RBACEngine
from security.user_database import UserDatabase, normalize_uid
from security.zone_manager import ZoneManager, build_zone_manager_from_config


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
@pytest.fixture()
def roles_file(tmp_path: Path) -> Path:
    data = {
        "Admin": {"allowed_zones": ["*"], "restricted_zones": []},
        "Guard": {"allowed_zones": ["ZoneA", "ZoneB", "ZoneC"], "restricted_zones": []},
        "Engineer": {"allowed_zones": ["ZoneA", "ZoneB"], "restricted_zones": ["ZoneC"]},
        "Worker": {"allowed_zones": ["ZoneA"], "restricted_zones": ["ZoneB", "ZoneC"]},
        "Visitor": {"allowed_zones": [], "restricted_zones": ["ZoneA", "ZoneB", "ZoneC"]},
    }
    p = tmp_path / "roles.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture()
def users_file(tmp_path: Path) -> Path:
    data = {
        "A1:B2:C3:D4": {"name": "Security Guard", "role": "Guard", "allowed_zones": ["ZoneA", "ZoneB", "ZoneC"]},
        "E5:F6:G7:H8": {"name": "Worker 1", "role": "Worker", "allowed_zones": ["ZoneA"]},
        "I9:J0:K1:L2": {"name": "Engineer 1", "role": "Engineer", "allowed_zones": ["ZoneA", "ZoneB"]},
    }
    p = tmp_path / "authorized_users.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture()
def access(users_file: Path, roles_file: Path) -> AccessControl:
    user_db = UserDatabase(users_file)
    rbac = RBACEngine.from_file(roles_file)
    zones = ZoneManager(
        zones=[],  # rely on default_zone resolution; explicit zone passed in tests
        default_zone="ZoneA",
    )
    return AccessControl(user_db, rbac, zones, max_consecutive_failures=3)


# --------------------------------------------------------------------------
# UID normalization
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("a1:b2:c3:d4", "A1:B2:C3:D4"),
        ("A1-B2-C3-D4", "A1:B2:C3:D4"),
        ("A1 B2 C3 D4", "A1:B2:C3:D4"),
        ("A1B2C3D4", "A1:B2:C3:D4"),
        ("  a1:b2 ", "A1:B2"),
    ],
)
def test_normalize_uid(raw: str, expected: str) -> None:
    assert normalize_uid(raw) == expected


# --------------------------------------------------------------------------
# RBAC
# --------------------------------------------------------------------------
def test_rbac_worker_restricted(roles_file: Path) -> None:
    rbac = RBACEngine.from_file(roles_file)
    assert rbac.is_allowed("Worker", ["ZoneA"], "ZoneA") is True
    assert rbac.is_allowed("Worker", ["ZoneA"], "ZoneB") is False


def test_rbac_admin_wildcard(roles_file: Path) -> None:
    rbac = RBACEngine.from_file(roles_file)
    assert rbac.is_allowed("Admin", [], "ZoneC") is True


def test_rbac_role_restriction_overrides_personal(roles_file: Path) -> None:
    rbac = RBACEngine.from_file(roles_file)
    # Engineer personally lists ZoneC but the role restricts it.
    assert rbac.is_allowed("Engineer", ["ZoneA", "ZoneB", "ZoneC"], "ZoneC") is False


# --------------------------------------------------------------------------
# AccessControl decisions
# --------------------------------------------------------------------------
def test_authorized_access(access: AccessControl) -> None:
    res = access.evaluate("A1:B2:C3:D4", "ZoneB")
    assert res.decision is AccessDecision.AUTHORIZED
    assert res.event_type == "AUTHORIZED_ACCESS"
    assert res.authorized is True


def test_zone_violation(access: AccessControl) -> None:
    res = access.evaluate("E5:F6:G7:H8", "ZoneB")  # Worker -> only ZoneA
    assert res.decision is AccessDecision.UNAUTHORIZED
    assert res.event_type == "ZONE_VIOLATION"
    assert res.authorized is False


def test_unknown_tag(access: AccessControl) -> None:
    res = access.evaluate("ZZ:ZZ:ZZ:ZZ", "ZoneA")
    assert res.decision is AccessDecision.UNKNOWN_TAG
    assert res.event_type == "UNKNOWN_RFID"


def test_anonymous_intrusion(access: AccessControl) -> None:
    res = access.evaluate(None, "ZoneA")
    assert res.event_type == "UNAUTHORIZED_INTRUSION"
    assert res.authorized is False


def test_access_denied_after_repeated_failures(access: AccessControl) -> None:
    alerts = []
    access._on_security_alert = lambda t, d: alerts.append((t, d))
    for _ in range(3):
        access.evaluate("ZZ:ZZ:ZZ:ZZ", "ZoneA")
    assert alerts and alerts[-1][0] == "ACCESS_DENIED"
    assert alerts[-1][1]["consecutive_failures"] >= 3


def test_resolve_intrusion_payload(access: AccessControl) -> None:
    access._uid_provider = lambda: "E5:F6:G7:H8"
    event = {"person_id": 0, "bbox": [110, 110, 200, 360], "intrusion": True}
    decision = access.resolve_intrusion(event)
    assert decision is not None
    assert decision["event_type"] == "AUTHORIZED_ACCESS"  # Worker in ZoneA (default)
    assert decision["payload"]["access"]["uid"] == "E5:F6:G7:H8"
    assert decision["payload"]["access"]["authorized"] is True


# --------------------------------------------------------------------------
# Zone manager
# --------------------------------------------------------------------------
def test_zone_manager_from_config() -> None:
    cfg = {
        "zones": {
            "default_zone": "ZoneA",
            "definitions": {
                "ZoneA": {"polygon": [[0, 0], [100, 0], [100, 100], [0, 100]]},
                "ZoneB": {"polygon": [[100, 0], [200, 0], [200, 100], [100, 100]]},
            },
        }
    }
    zm = build_zone_manager_from_config(cfg)
    assert zm.zone_for_point((50, 50)) == "ZoneA"
    assert zm.zone_for_point((150, 50)) == "ZoneB"
    assert zm.zone_for_bbox([120, 20, 180, 80]) == "ZoneB"


def test_zone_manager_legacy_tripwire_fallback() -> None:
    cfg = {"tripwire": {"polygon": [[0, 0], [10, 0], [10, 10], [0, 10]]}}
    zm = build_zone_manager_from_config(cfg)
    assert zm.zone_for_point((5, 5)) == "ZoneA"


# --------------------------------------------------------------------------
# RFID reader
# --------------------------------------------------------------------------
def test_reader_dedup() -> None:
    reader = RfidReader(mode="simulation", dedup_seconds=10.0, correlation_window_seconds=60.0)
    first = reader.ingest("A1:B2:C3:D4")
    second = reader.ingest("A1:B2:C3:D4")  # within dedup window -> suppressed
    assert first is not None
    assert second is None
    assert reader.read_uid() == "A1:B2:C3:D4"


def test_reader_correlation_window_expiry() -> None:
    reader = RfidReader(mode="simulation", dedup_seconds=0.0, correlation_window_seconds=0.01)
    reader.ingest("A1:B2:C3:D4")
    time.sleep(0.05)
    assert reader.read_uid() is None  # too old to correlate


def test_reader_verify_and_get_user(users_file: Path) -> None:
    reader = RfidReader(mode="simulation")
    db = UserDatabase(users_file)
    assert reader.verify_uid("a1:b2:c3:d4", db) is True
    assert reader.verify_uid("ZZ:ZZ:ZZ:ZZ", db) is False
    user = reader.get_user("E5:F6:G7:H8", db)
    assert user is not None and user.role == "Worker"


# --------------------------------------------------------------------------
# EventEngine integration (the key non-breaking guarantee)
# --------------------------------------------------------------------------
def test_event_engine_without_resolver_is_unchanged() -> None:
    engine = EventEngine(debounce_frames=1)
    events = [{"person_id": 0, "ppe": {"helmet": True, "vest": True}, "posture": "Standing", "intrusion": True}]
    emitted = engine.process_frame(0, events)
    kinds = {e.kind for e in emitted}
    assert HighLevelEvent.INTRUSION in kinds


def test_event_engine_with_resolver_refines_intrusion(access: AccessControl) -> None:
    access._uid_provider = lambda: "E5:F6:G7:H8"  # Worker
    engine = EventEngine(debounce_frames=1)
    engine.set_access_resolver(access.resolve_intrusion)

    # Worker in ZoneA (default) -> AUTHORIZED_ACCESS, not INTRUSION.
    events = [{"person_id": 0, "bbox": [10, 10, 50, 90], "ppe": {"helmet": True, "vest": True}, "posture": "Standing", "intrusion": True}]
    emitted = engine.process_frame(0, events)
    kinds = {e.kind for e in emitted}
    assert HighLevelEvent.AUTHORIZED_ACCESS in kinds
    assert HighLevelEvent.INTRUSION not in kinds


def test_event_engine_resolver_unknown_tag(access: AccessControl) -> None:
    access._uid_provider = lambda: "ZZ:ZZ:ZZ:ZZ"
    engine = EventEngine(debounce_frames=1)
    engine.set_access_resolver(access.resolve_intrusion)
    events = [{"person_id": 1, "bbox": [10, 10, 50, 90], "ppe": {"helmet": True, "vest": True}, "posture": "Standing", "intrusion": True}]
    emitted = engine.process_frame(0, events)
    kinds = {e.kind for e in emitted}
    assert HighLevelEvent.UNKNOWN_RFID in kinds


# --------------------------------------------------------------------------
# user database CRUD + config builder
# --------------------------------------------------------------------------
def test_user_db_crud(tmp_path: Path) -> None:
    db = UserDatabase(tmp_path / "u.json")
    db.add_user("aa:bb:cc:dd", "Tester", "Engineer", ["ZoneA"])
    assert db.has_user("AA:BB:CC:DD")
    # persisted + reload
    db2 = UserDatabase(tmp_path / "u.json")
    assert db2.get_user("aa:bb:cc:dd").name == "Tester"
    assert db2.remove_user("aa:bb:cc:dd") is True
    assert db2.has_user("aa:bb:cc:dd") is False


def test_invalid_role_rejected(tmp_path: Path) -> None:
    db = UserDatabase(tmp_path / "u.json")
    with pytest.raises(ValueError):
        db.add_user("aa:bb", "X", "Superuser", ["ZoneA"])


def test_build_access_control_from_config(users_file: Path, roles_file: Path) -> None:
    # Absolute paths: Path(root) / abs_path resolves to abs_path (pathlib semantics).
    cfg = {
        "rfid": {"users_db": str(users_file), "roles_db": str(roles_file)},
        "zones": {"default_zone": "ZoneA"},
    }
    ac = build_access_control_from_config(cfg, ROOT)
    assert ac.get_user_role("A1:B2:C3:D4") == "Guard"
