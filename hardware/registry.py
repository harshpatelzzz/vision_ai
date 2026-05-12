"""Process-wide hooks so FastAPI can read live ESP32 telemetry without circular imports."""

from __future__ import annotations

from typing import Optional

from hardware.telemetry_store import TelemetryStore

_REGISTERED_STORE: Optional[TelemetryStore] = None
_REGISTERED_STREAM_URL: str = ""


def register_live_hardware(
    store: Optional[TelemetryStore] = None,
    *,
    stream_url: str = "",
) -> None:
    global _REGISTERED_STORE, _REGISTERED_STREAM_URL
    if store is not None:
        _REGISTERED_STORE = store
    if stream_url:
        _REGISTERED_STREAM_URL = stream_url


def get_registered_store() -> Optional[TelemetryStore]:
    return _REGISTERED_STORE


def get_registered_stream_url() -> str:
    return _REGISTERED_STREAM_URL


def clear_registration() -> None:
    global _REGISTERED_STORE, _REGISTERED_STREAM_URL
    _REGISTERED_STORE = None
    _REGISTERED_STREAM_URL = ""
