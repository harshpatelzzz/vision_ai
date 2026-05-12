"""Hardware edge adapters: ESP32 telemetry, sensor daemon, tamper bridge."""

from hardware.registry import (
    clear_registration,
    get_registered_store,
    get_registered_stream_url,
    register_live_hardware,
)
from hardware.telemetry_store import TelemetryStore

__all__ = [
    "TelemetryStore",
    "register_live_hardware",
    "get_registered_store",
    "get_registered_stream_url",
    "clear_registration",
]
