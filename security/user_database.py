"""Thread-safe, file-backed authorized-personnel database (RFID UID -> profile).

Backs ``data/authorized_users.json``. Reads are cached in memory; writes are
atomic (temp file + replace) so a crash mid-write never corrupts the database.
Used by :mod:`security.access_control`, the RFID registration API, and tests.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

VALID_ROLES = ("Admin", "Guard", "Engineer", "Worker", "Visitor")


def normalize_uid(uid: str) -> str:
    """Canonicalize a tag UID to uppercase colon-separated form.

    Accepts ``a1:b2:c3:d4``, ``A1-B2-C3-D4``, ``A1 B2 C3 D4`` or ``A1B2C3D4``.
    """
    if uid is None:
        return ""
    s = str(uid).strip().upper()
    for sep in ("-", " ", "_"):
        s = s.replace(sep, ":")
    if ":" not in s and len(s) % 2 == 0 and len(s) > 2:
        s = ":".join(s[i : i + 2] for i in range(0, len(s), 2))
    parts = [p for p in s.split(":") if p != ""]
    return ":".join(parts)


@dataclass(frozen=True)
class User:
    """A registered person bound to an RFID tag."""

    uid: str
    name: str
    role: str
    allowed_zones: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "role": self.role, "allowed_zones": list(self.allowed_zones)}


class UserDatabase:
    """In-memory cache over a JSON file with atomic persistence."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self._users: Dict[str, Dict[str, Any]] = {}
        self.reload()

    # ----- load / persist -------------------------------------------------
    def reload(self) -> None:
        with self._lock:
            if not self.db_path.is_file():
                self._users = {}
                return
            try:
                raw = json.loads(self.db_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self._users = {}
                return
            if not isinstance(raw, dict):
                self._users = {}
                return
            self._users = {normalize_uid(k): dict(v) for k, v in raw.items() if isinstance(v, dict)}

    def _persist_locked(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.db_path.with_suffix(self.db_path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._users, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.db_path)

    # ----- queries --------------------------------------------------------
    def get_user(self, uid: str) -> Optional[User]:
        key = normalize_uid(uid)
        with self._lock:
            rec = self._users.get(key)
            if rec is None:
                return None
            return User(
                uid=key,
                name=str(rec.get("name", "Unknown")),
                role=str(rec.get("role", "Visitor")),
                allowed_zones=[str(z) for z in (rec.get("allowed_zones") or [])],
            )

    def has_user(self, uid: str) -> bool:
        with self._lock:
            return normalize_uid(uid) in self._users

    def all_users(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {k: dict(v) for k, v in self._users.items()}

    def count(self) -> int:
        with self._lock:
            return len(self._users)

    # ----- mutations ------------------------------------------------------
    def add_user(
        self,
        uid: str,
        name: str,
        role: str,
        allowed_zones: List[str],
        *,
        overwrite: bool = True,
    ) -> User:
        key = normalize_uid(uid)
        if not key:
            raise ValueError("uid is required")
        if not name:
            raise ValueError("name is required")
        if role not in VALID_ROLES:
            raise ValueError(f"role must be one of {VALID_ROLES}, got {role!r}")
        with self._lock:
            if key in self._users and not overwrite:
                raise ValueError(f"uid {key} already registered")
            self._users[key] = {
                "name": str(name),
                "role": str(role),
                "allowed_zones": [str(z) for z in (allowed_zones or [])],
            }
            self._persist_locked()
        return User(key, str(name), str(role), [str(z) for z in (allowed_zones or [])])

    def remove_user(self, uid: str) -> bool:
        key = normalize_uid(uid)
        with self._lock:
            if key not in self._users:
                return False
            del self._users[key]
            self._persist_locked()
        return True
