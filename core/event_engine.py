"""High-level security events with frame-based debouncing."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Tuple


class HighLevelEvent(str, Enum):
    NO_HELMET = "NO_HELMET"
    NO_VEST = "NO_VEST"
    INTRUSION = "INTRUSION"
    FALL_DETECTED = "FALL_DETECTED"
    TAMPER_DETECTED = "TAMPER_DETECTED"


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
        self._last_frame: Dict[Tuple[str, int], int] = {}
        self._events: Deque[DebouncedEvent] = deque(maxlen=2000)

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
                (HighLevelEvent.INTRUSION, intrusion),
                (HighLevelEvent.FALL_DETECTED, posture == "Lying"),
            ]

            for kind, condition in checks:
                if not condition:
                    continue
                key = (kind.value, pid)
                last = self._last_frame.get(key, -self.debounce_frames * 2)
                if frame_index - last < self.debounce_frames:
                    continue
                self._last_frame[key] = frame_index
                de = DebouncedEvent(kind=kind, person_id=pid, payload=dict(ev))
                emitted.append(de)
                self._events.append(de)

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
