"""
ESP32 sensor telemetry evaluator (distinct from ``core.hardware_monitor.HardwareMonitor``).

Maps JSON telemetry to tamper conditions and invokes secure logging without vision debounce.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from hardware.telemetry_store import TelemetryStore

logger = logging.getLogger("posevision.hw.telemetry")

TamperFn = Callable[[str, Dict[str, Any]], None]


@dataclass
class TelemetryThresholds:
    temp_max_c: float = 55.0
    distance_min_mm: float = 50.0
    distance_max_mm: float = 8000.0
    light_trigger_above: Optional[float] = None
    orientation_delta_deg: float = 35.0


class Esp32TelemetryTamperBridge(threading.Thread):
    """
    Polls :class:`TelemetryStore` and raises tamper when firmware reports tamper or
    thresholds are exceeded (host-side redundancy).
    """

    def __init__(
        self,
        store: TelemetryStore,
        thresholds: TelemetryThresholds,
        on_tamper: TamperFn,
        *,
        poll_interval_s: float = 0.15,
        latch: bool = True,
        name: str = "esp32-telemetry-tamper",
    ) -> None:
        super().__init__(name=name, daemon=True)
        self._store = store
        self._thresholds = thresholds
        self._on_tamper = on_tamper
        self._poll_interval_s = poll_interval_s
        self._latch = latch
        self._stop = threading.Event()
        self._fired = False
        self._last_heading: Optional[float] = None

    def stop(self) -> None:
        self._stop.set()

    def reset_latch(self) -> None:
        self._fired = False
        self._last_heading = None

    def run(self) -> None:
        while not self._stop.is_set():
            snap = self._store.snapshot()
            if snap.get("_connected"):
                reason = self._evaluate(snap)
                if reason and not (self._latch and self._fired):
                    self._fired = True
                    try:
                        self._on_tamper(reason, snap)
                    except Exception:
                        logger.exception("Tamper callback failed")
            time.sleep(self._poll_interval_s)

    def _evaluate(self, s: Dict[str, Any]) -> Optional[str]:
        if bool(s.get("tamper")):
            return "esp32_flag"

        try:
            t = float(s.get("temperature", 0.0))
            if t >= self._thresholds.temp_max_c:
                return "temperature"
        except (TypeError, ValueError):
            pass

        try:
            d = float(s.get("distance", -1.0))
            if d >= 0:
                if d < self._thresholds.distance_min_mm:
                    return "proximity"
                if d > self._thresholds.distance_max_mm:
                    return "distance_anomaly"
        except (TypeError, ValueError):
            pass

        light = s.get("light")
        if light is not None and self._thresholds.light_trigger_above is not None:
            try:
                if float(light) >= float(self._thresholds.light_trigger_above):
                    return "light"
            except (TypeError, ValueError):
                pass

        ori = s.get("orientation")
        if ori is not None:
            try:
                h = float(ori)
                if self._last_heading is not None:
                    if abs(h - self._last_heading) >= self._thresholds.orientation_delta_deg:
                        self._last_heading = h
                        return "orientation_jolt"
                self._last_heading = h
            except (TypeError, ValueError):
                pass

        return None
