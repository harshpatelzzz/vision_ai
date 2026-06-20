"""High-level security events with frame-based debouncing."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple


class HighLevelEvent(str, Enum):
    NO_HELMET = "NO_HELMET"
    NO_VEST = "NO_VEST"
    INTRUSION = "INTRUSION"
    FALL_DETECTED = "FALL_DETECTED"
    TAMPER_DETECTED = "TAMPER_DETECTED"
    # RFID / RBAC authorization layer (see security.access_control). These refine
    # a raw INTRUSION once an authorization decision is available.
    AUTHORIZED_ACCESS = "AUTHORIZED_ACCESS"
    UNAUTHORIZED_INTRUSION = "UNAUTHORIZED_INTRUSION"
    UNKNOWN_RFID = "UNKNOWN_RFID"
    ZONE_VIOLATION = "ZONE_VIOLATION"
    ACCESS_DENIED = "ACCESS_DENIED"


# Event-type name -> enum, for resolvers that work in plain strings.
_EVENT_BY_NAME: Dict[str, HighLevelEvent] = {e.value: e for e in HighLevelEvent}


# A resolver receives a per-person intrusion event dict and returns either
# ``None`` (keep legacy INTRUSION) or ``{"event_type": <name>, "payload": <dict>}``.
AccessResolver = Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]


@dataclass(frozen=True)
class DebouncedEvent:
    """Emitted event after debounce filter."""

    kind: HighLevelEvent
    person_id: int
    payload: Dict[str, Any]


class EventEngine:
    """
    Convert per-frame observations into high-level events, debounce duplicates.

    Debouncing is per (event kind, person_id): the same event is not re-emitted
    within ``debounce_frames`` frame ticks while the condition remains true.
    """

    def __init__(self, debounce_frames: int = 15) -> None:
        self.debounce_frames = max(1, debounce_frames)
        self._last_frame: Dict[Tuple[Any, ...], int] = {}
        self._events: Deque[DebouncedEvent] = deque(maxlen=2000)
        self._access_resolver: Optional[AccessResolver] = None

    def set_access_resolver(self, resolver: Optional[AccessResolver]) -> None:
        """Install (or clear) the RFID/RBAC authorization resolver.

        When set, a tripwire ``intrusion`` is routed through the resolver and
        emitted as an authorization event (AUTHORIZED_ACCESS / ZONE_VIOLATION /
        UNKNOWN_RFID / UNAUTHORIZED_INTRUSION) instead of a bare INTRUSION.
        When unset, behavior is exactly as before.
        """
        self._access_resolver = resolver

    def _emit(
        self,
        frame_index: int,
        kind: HighLevelEvent,
        pid: int,
        payload: Dict[str, Any],
        *,
        debounce_key: Optional[Tuple[Any, ...]] = None,
    ) -> Optional[DebouncedEvent]:
        key = debounce_key if debounce_key is not None else (kind.value, pid)
        last = self._last_frame.get(key, -self.debounce_frames * 2)
        if frame_index - last < self.debounce_frames:
            return None
        self._last_frame[key] = frame_index
        de = DebouncedEvent(kind=kind, person_id=pid, payload=payload)
        self._events.append(de)
        return de

    def _emit_intrusion(
        self,
        frame_index: int,
        pid: int,
        ev: Dict[str, Any],
    ) -> Optional[DebouncedEvent]:
        """Emit INTRUSION, or an RFID-authorized refinement when a resolver is set."""
        if self._access_resolver is None:
            return self._emit(frame_index, HighLevelEvent.INTRUSION, pid, dict(ev))

        decision: Optional[Dict[str, Any]] = None
        try:
            decision = self._access_resolver(dict(ev))
        except Exception:
            decision = None
        if not decision:
            return self._emit(frame_index, HighLevelEvent.INTRUSION, pid, dict(ev))

        kind = _EVENT_BY_NAME.get(str(decision.get("event_type", "")))
        if kind is None:
            return self._emit(frame_index, HighLevelEvent.INTRUSION, pid, dict(ev))

        payload = decision.get("payload") or dict(ev)
        access = payload.get("access") or {}
        # Debounce per (event, person, uid, zone) so distinct people/zones/tags
        # are not suppressed by one another.
        dk = (kind.value, pid, str(access.get("uid", "")), str(access.get("zone", "")))
        return self._emit(frame_index, kind, pid, payload, debounce_key=dk)

    def process_frame(
        self,
        frame_index: int,
        structured_events: List[Dict[str, Any]],
    ) -> List[DebouncedEvent]:
        """
        Inspect structured per-person events and emit debounced high-level events.

        ``structured_events`` items match the pipeline schema (timestamp, person_id,
        bbox, ppe, posture, intrusion).
        """
        emitted: List[DebouncedEvent] = []
        for ev in structured_events:
            pid = int(ev.get("person_id", -1))
            ppe = ev.get("ppe") or {}
            intrusion = bool(ev.get("intrusion", False))
            posture = str(ev.get("posture", "Unknown"))

            checks: List[Tuple[HighLevelEvent, bool]] = [
                (HighLevelEvent.NO_HELMET, not bool(ppe.get("helmet", False))),
                (HighLevelEvent.NO_VEST, not bool(ppe.get("vest", False))),
                (HighLevelEvent.FALL_DETECTED, posture == "Lying"),
            ]

            for kind, condition in checks:
                if not condition:
                    continue
                de = self._emit(frame_index, kind, pid, dict(ev))
                if de is not None:
                    emitted.append(de)

            # Intrusion is handled separately so the RFID/RBAC layer can refine it.
            if intrusion:
                de = self._emit_intrusion(frame_index, pid, ev)
                if de is not None:
                    emitted.append(de)

        return emitted

    def emit_tamper_event(self, extra: Optional[Dict[str, Any]] = None) -> DebouncedEvent:
        """Emit an unconditional TAMPER_DETECTED event (bypasses debounce)."""
        from datetime import datetime, timezone

        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "hardware_monitor",
        }
        if extra:
            payload.update(extra)
        ev = DebouncedEvent(
            kind=HighLevelEvent.TAMPER_DETECTED,
            person_id=-1,
            payload=payload,
        )
        self._events.append(ev)
        return ev

    def recent_events(self, limit: int = 100) -> List[DebouncedEvent]:
        """Return up to ``limit`` most recent debounced events (oldest first)."""
        items = list(self._events)
        return items[-limit:] if limit else items
