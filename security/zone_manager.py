"""Zone manager: map tripwire polygons to named restricted zones (ZoneA/B/C).

The intrusion pipeline already produces a person ``bbox``; :class:`ZoneManager`
resolves the enclosing zone for that person so :mod:`security.access_control`
can evaluate RFID authorization against the *specific* zone entered.

Backward compatibility: when no explicit ``zones`` config is present the single
legacy ``tripwire.polygon`` is mapped to ``default_zone`` (ZoneA), so existing
deployments keep working unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.geometry import point_inside_polygon

Polygon = List[List[float]]


@dataclass(frozen=True)
class Zone:
    """A named restricted zone defined by a pixel-space polygon."""

    name: str
    polygon: Polygon


@dataclass
class ZoneManager:
    """
    Resolve which named zone a point/bbox falls into.

    Zones are tested in declaration order; the first polygon containing the
    point wins. Points outside every polygon return ``default_zone`` when
    ``fallback_to_default`` is set, otherwise ``None``.
    """

    zones: List[Zone] = field(default_factory=list)
    default_zone: str = "ZoneA"
    fallback_to_default: bool = True

    def zone_names(self) -> List[str]:
        names = [z.name for z in self.zones]
        if self.default_zone and self.default_zone not in names:
            names.append(self.default_zone)
        return names

    def zone_for_point(self, point: Tuple[float, float]) -> Optional[str]:
        for zone in self.zones:
            if len(zone.polygon) >= 3 and point_inside_polygon(point, zone.polygon):
                return zone.name
        return self.default_zone if self.fallback_to_default else None

    def zone_for_bbox(self, bbox: Sequence[float]) -> Optional[str]:
        if not bbox or len(bbox) < 4:
            return self.default_zone if self.fallback_to_default else None
        cx = (float(bbox[0]) + float(bbox[2])) / 2.0
        cy = (float(bbox[1]) + float(bbox[3])) / 2.0
        return self.zone_for_point((cx, cy))

    def polygon_for_zone(self, name: str) -> Optional[Polygon]:
        for zone in self.zones:
            if zone.name == name:
                return zone.polygon
        return None


def build_zone_manager_from_config(config: Dict[str, Any]) -> ZoneManager:
    """
    Construct a :class:`ZoneManager` from a loaded ``config.yaml`` dict.

    Supports::

        zones:
          default_zone: "ZoneA"
          fallback_to_default: true
          definitions:
            ZoneA: { polygon: [[x,y], ...] }
            ZoneB: { polygon: [[x,y], ...] }

    Falls back to the legacy single ``tripwire.polygon`` mapped to ``default_zone``.
    """
    zones_cfg = config.get("zones") or {}
    default_zone = str(zones_cfg.get("default_zone", "ZoneA"))
    fallback = bool(zones_cfg.get("fallback_to_default", True))

    definitions = zones_cfg.get("definitions") or {}
    zones: List[Zone] = []
    for name, spec in definitions.items():
        spec = spec or {}
        polygon = [[float(x), float(y)] for x, y in (spec.get("polygon") or [])]
        if len(polygon) >= 3:
            zones.append(Zone(name=str(name), polygon=polygon))

    if not zones:
        tw = config.get("tripwire") or {}
        poly = [[float(x), float(y)] for x, y in (tw.get("polygon") or [])]
        if len(poly) >= 3:
            zones.append(Zone(name=default_zone, polygon=poly))

    return ZoneManager(zones=zones, default_zone=default_zone, fallback_to_default=fallback)
