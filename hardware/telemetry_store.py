"""Thread-safe store for last ESP32 sensor JSON telemetry."""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional


class TelemetryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last: Dict[str, Any] = {}
        self._connected = False
        self._last_error: Optional[str] = None

    def update(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._last = dict(payload)
            self._connected = True
            self._last_error = None

    def mark_error(self, msg: str) -> None:
        with self._lock:
            self._last_error = msg

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            out = dict(self._last)
            out["_connected"] = self._connected
            out["_last_error"] = self._last_error
            return out

    def reset(self) -> None:
        with self._lock:
            self._last.clear()
            self._connected = False
            self._last_error = None
