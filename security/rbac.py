"""Role-Based Access Control engine: roles -> allowed / restricted zones.

Backs ``data/roles.json``. The effective decision for a person combines the
*user* policy (their personal ``allowed_zones``) with the *role* policy here:

    authorized(zone) == zone in effective_allowed_zones(user, role)
                        and zone not in role.restricted_zones

``"*"`` in a role's ``allowed_zones`` grants every zone (used by Admin).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

WILDCARD = "*"


@dataclass(frozen=True)
class RolePolicy:
    name: str
    allowed_zones: List[str] = field(default_factory=list)
    restricted_zones: List[str] = field(default_factory=list)
    description: str = ""

    @property
    def grants_all(self) -> bool:
        return WILDCARD in self.allowed_zones


# Safe built-in defaults so the engine works even if roles.json is missing.
_DEFAULT_ROLES: Dict[str, Dict[str, Any]] = {
    "Admin": {"allowed_zones": ["*"], "restricted_zones": []},
    "Guard": {"allowed_zones": ["ZoneA", "ZoneB", "ZoneC"], "restricted_zones": []},
    "Engineer": {"allowed_zones": ["ZoneA", "ZoneB"], "restricted_zones": ["ZoneC"]},
    "Worker": {"allowed_zones": ["ZoneA"], "restricted_zones": ["ZoneB", "ZoneC"]},
    "Visitor": {"allowed_zones": [], "restricted_zones": ["ZoneA", "ZoneB", "ZoneC"]},
}


class RBACEngine:
    """Loads role policies and answers zone authorization questions."""

    def __init__(self, roles: Dict[str, RolePolicy]) -> None:
        self._roles = roles

    @classmethod
    def from_file(cls, roles_path: Path) -> "RBACEngine":
        data: Dict[str, Dict[str, Any]] = dict(_DEFAULT_ROLES)
        p = Path(roles_path)
        if p.is_file():
            try:
                loaded = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, json.JSONDecodeError):
                pass
        roles: Dict[str, RolePolicy] = {}
        for name, spec in data.items():
            spec = spec or {}
            roles[str(name)] = RolePolicy(
                name=str(name),
                allowed_zones=[str(z) for z in (spec.get("allowed_zones") or [])],
                restricted_zones=[str(z) for z in (spec.get("restricted_zones") or [])],
                description=str(spec.get("description", "")),
            )
        return cls(roles)

    def get_role(self, role: str) -> Optional[RolePolicy]:
        return self._roles.get(str(role))

    def roles(self) -> Dict[str, RolePolicy]:
        return dict(self._roles)

    def effective_allowed_zones(self, role: str, user_allowed: List[str]) -> Set[str]:
        """Zones a person may enter given their role + personal allowance.

        Personal ``allowed_zones`` take precedence; if empty we fall back to the
        role's ``allowed_zones``. Role ``restricted_zones`` always subtract.
        ``"*"`` (personal or role) expands to "any zone".
        """
        policy = self.get_role(role)
        personal = set(user_allowed or [])
        if WILDCARD in personal or (policy is not None and policy.grants_all):
            return {WILDCARD}

        allowed = personal if personal else (set(policy.allowed_zones) if policy else set())
        if policy is not None:
            allowed -= set(policy.restricted_zones)
        return allowed

    def is_allowed(self, role: str, user_allowed: List[str], zone: str) -> bool:
        policy = self.get_role(role)
        if policy is not None and zone in set(policy.restricted_zones):
            return False
        allowed = self.effective_allowed_zones(role, user_allowed)
        return WILDCARD in allowed or zone in allowed
