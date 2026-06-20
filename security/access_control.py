"""Access control / intrusion decision engine.

Combines :class:`~security.user_database.UserDatabase`,
:class:`~security.rbac.RBACEngine` and :class:`~security.zone_manager.ZoneManager`
to turn a raw tripwire intrusion into an *authorization decision*:

    AUTHORIZED   -> AUTHORIZED_ACCESS
    UNKNOWN_TAG  -> UNKNOWN_RFID
    UNAUTHORIZED -> ZONE_VIOLATION       (known person, forbidden zone)
                 -> UNAUTHORIZED_INTRUSION (no RFID presented / anonymous)

Repeated failures for the same tag raise an ACCESS_DENIED security alert.

This module is intentionally decoupled from the camera pipeline: it exposes a
plain ``resolve_intrusion(event) -> decision`` callable that
:class:`core.event_engine.EventEngine` consumes through its access-resolver hook,
so existing modules do not need to know about RFID.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional

from security.rbac import RBACEngine
from security.user_database import UserDatabase, normalize_uid
from security.zone_manager import ZoneManager


class AccessDecision(str, Enum):
    """Result of an access evaluation (per spec)."""

    AUTHORIZED = "AUTHORIZED"
    UNAUTHORIZED = "UNAUTHORIZED"
    UNKNOWN_TAG = "UNKNOWN_TAG"


# Map a decision (plus context) to the high-level event-type *name*. We use the
# string name rather than importing the enum to avoid any import ordering issues;
# core.event_engine defines matching members.
EVENT_AUTHORIZED_ACCESS = "AUTHORIZED_ACCESS"
EVENT_UNAUTHORIZED_INTRUSION = "UNAUTHORIZED_INTRUSION"
EVENT_UNKNOWN_RFID = "UNKNOWN_RFID"
EVENT_ZONE_VIOLATION = "ZONE_VIOLATION"
EVENT_ACCESS_DENIED = "ACCESS_DENIED"


@dataclass
class AccessResult:
    """Structured outcome of a single access evaluation."""

    decision: AccessDecision
    event_type: str
    authorized: bool
    zone: Optional[str]
    uid: Optional[str]
    name: Optional[str]
    role: Optional[str]
    reason: str
    timestamp: str

    def as_access_block(self) -> Dict[str, Any]:
        return {
            "uid": self.uid,
            "name": self.name,
            "role": self.role,
            "zone": self.zone,
            "authorized": self.authorized,
            "decision": self.decision.value,
            "event_type": self.event_type,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AccessControl:
    """RFID + RBAC authorization layer over the tripwire intrusion detector."""

    def __init__(
        self,
        user_db: UserDatabase,
        rbac: RBACEngine,
        zone_manager: ZoneManager,
        *,
        uid_provider: Optional[Callable[[], Optional[str]]] = None,
        max_consecutive_failures: int = 3,
        access_log_limit: int = 1000,
        on_security_alert: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> None:
        self.user_db = user_db
        self.rbac = rbac
        self.zones = zone_manager
        self._uid_provider = uid_provider
        self._max_failures = max(1, int(max_consecutive_failures))
        self._on_security_alert = on_security_alert
        self._lock = threading.Lock()
        self._access_log: Deque[Dict[str, Any]] = deque(maxlen=access_log_limit)
        self._fail_counts: Dict[str, int] = {}

    # ----- spec-named primitives -----------------------------------------
    def get_user_role(self, uid: str) -> Optional[str]:
        user = self.user_db.get_user(uid)
        return user.role if user else None

    def is_authorized(self, uid: str, zone: str) -> bool:
        """True only when the tag is known *and* permitted in ``zone``."""
        user = self.user_db.get_user(uid)
        if user is None:
            return False
        return self.rbac.is_allowed(user.role, user.allowed_zones, zone)

    def validate_access(self, uid: Optional[str], zone: str) -> AccessDecision:
        """Return AUTHORIZED / UNAUTHORIZED / UNKNOWN_TAG for a tag+zone."""
        if not uid:
            return AccessDecision.UNAUTHORIZED
        user = self.user_db.get_user(uid)
        if user is None:
            return AccessDecision.UNKNOWN_TAG
        if self.rbac.is_allowed(user.role, user.allowed_zones, zone):
            return AccessDecision.AUTHORIZED
        return AccessDecision.UNAUTHORIZED

    # ----- full evaluation -----------------------------------------------
    def evaluate(self, uid: Optional[str], zone: str) -> AccessResult:
        """Evaluate access and return a rich :class:`AccessResult` (records log)."""
        uid_n = normalize_uid(uid) if uid else None
        user = self.user_db.get_user(uid_n) if uid_n else None
        decision = self.validate_access(uid_n, zone)

        if decision is AccessDecision.AUTHORIZED:
            event_type, authorized, reason = EVENT_AUTHORIZED_ACCESS, True, "role_and_zone_ok"
        elif decision is AccessDecision.UNKNOWN_TAG:
            event_type, authorized, reason = EVENT_UNKNOWN_RFID, False, "uid_not_registered"
        elif uid_n is None:
            event_type, authorized, reason = (
                EVENT_UNAUTHORIZED_INTRUSION,
                False,
                "no_rfid_presented",
            )
        else:
            event_type, authorized, reason = EVENT_ZONE_VIOLATION, False, "zone_not_permitted"

        result = AccessResult(
            decision=decision,
            event_type=event_type,
            authorized=authorized,
            zone=zone,
            uid=uid_n,
            name=user.name if user else None,
            role=user.role if user else None,
            reason=reason,
            timestamp=_now_iso(),
        )
        self._record(result)
        return result

    def _record(self, result: AccessResult) -> None:
        with self._lock:
            self._access_log.append(result.as_access_block())
            key = result.uid or "<anonymous>"
            if result.authorized:
                self._fail_counts.pop(key, None)
            else:
                self._fail_counts[key] = self._fail_counts.get(key, 0) + 1
                if self._fail_counts[key] >= self._max_failures and self._on_security_alert:
                    detail = {
                        **result.as_access_block(),
                        "consecutive_failures": self._fail_counts[key],
                        "event_type": EVENT_ACCESS_DENIED,
                    }
                    # Fire outside the lock would be safer, but the callback is
                    # expected to be lightweight (log/append).
                    try:
                        self._on_security_alert(EVENT_ACCESS_DENIED, detail)
                    except Exception:
                        pass

    # ----- event-engine resolver hook ------------------------------------
    def resolve_intrusion(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Turn a tripwire intrusion event into an authorization decision.

        Returns a dict ``{"event_type": <name>, "payload": <event + access>}``
        consumed by :class:`core.event_engine.EventEngine`. Returns ``None`` to
        defer to legacy ``INTRUSION`` behavior (defensive fallback only).
        """
        bbox = event.get("bbox") or [0.0, 0.0, 0.0, 0.0]
        zone = self.zones.zone_for_bbox(bbox) or self.zones.default_zone
        uid = self._uid_provider() if self._uid_provider is not None else None

        result = self.evaluate(uid, zone)
        payload = dict(event)
        payload["access"] = result.as_access_block()
        payload["intrusion"] = True
        return {"event_type": result.event_type, "payload": payload}

    # ----- introspection (used by API) -----------------------------------
    def recent_access_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._access_log)
        return items[-limit:] if limit else items

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._access_log)
            granted = sum(1 for e in self._access_log if e.get("authorized"))
            return {
                "users_registered": self.user_db.count(),
                "zones": self.zones.zone_names(),
                "roles": list(self.rbac.roles().keys()),
                "access_events": total,
                "granted": granted,
                "denied": total - granted,
                "active_failure_tracks": dict(self._fail_counts),
            }


def build_access_control_from_config(
    config: Dict[str, Any],
    project_root: Path,
    *,
    uid_provider: Optional[Callable[[], Optional[str]]] = None,
    on_security_alert: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> AccessControl:
    """Assemble an :class:`AccessControl` from a loaded ``config.yaml`` dict."""
    from security.zone_manager import build_zone_manager_from_config

    rfid_cfg = config.get("rfid") or {}
    root = Path(project_root)
    users_path = root / str(rfid_cfg.get("users_db", "data/authorized_users.json"))
    roles_path = root / str(rfid_cfg.get("roles_db", "data/roles.json"))

    user_db = UserDatabase(users_path)
    rbac = RBACEngine.from_file(roles_path)
    zones = build_zone_manager_from_config(config)

    return AccessControl(
        user_db,
        rbac,
        zones,
        uid_provider=uid_provider,
        max_consecutive_failures=int(rfid_cfg.get("max_consecutive_failures", 3)),
        on_security_alert=on_security_alert,
    )
