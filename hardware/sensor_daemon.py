"""Background reader: Serial or HTTP ingest for ESP32 JSON telemetry lines."""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from hardware.telemetry_store import TelemetryStore

logger = logging.getLogger("posevision.sensor_daemon")


class SensorDaemon(threading.Thread):
    """
    Reads newline-delimited JSON from USB-serial (preferred) or polls an HTTP JSON endpoint.

    Each parsed object is pushed into :class:`TelemetryStore`.
    """

    def __init__(
        self,
        store: TelemetryStore,
        *,
        serial_port: Optional[str] = None,
        baudrate: int = 115200,
        http_poll_url: Optional[str] = None,
        poll_interval_s: float = 0.5,
        name: str = "sensor-daemon",
    ) -> None:
        super().__init__(name=name, daemon=True)
        self._store = store
        self._serial_port = serial_port
        self._baudrate = baudrate
        self._http_poll_url = http_poll_url
        self._poll_interval_s = max(0.1, poll_interval_s)
        self._stop = threading.Event()
        self._ser = None

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        if self._serial_port:
            self._run_serial()
        elif self._http_poll_url:
            self._run_http_poll()
        else:
            logger.warning("SensorDaemon: no serial_port or http_poll_url configured")

    def _run_serial(self) -> None:
        try:
            import serial  # type: ignore[import-untyped]
        except ImportError:
            logger.error("pyserial not installed — cannot read ESP32 telemetry")
            self._store.mark_error("pyserial missing")
            return

        while not self._stop.is_set():
            try:
                if self._ser is None:
                    self._ser = serial.Serial(self._serial_port, self._baudrate, timeout=1.0)
                    logger.info("Telemetry serial open %s @ %s", self._serial_port, self._baudrate)

                raw = self._ser.readline().decode("utf-8", errors="replace").strip()
                if not raw:
                    continue
                if raw.upper().startswith("TAMPER") and "{" not in raw:
                    continue
                if raw.startswith("{"):
                    obj = json.loads(raw)
                    if isinstance(obj, dict):
                        self._store.update(obj)
            except json.JSONDecodeError:
                self._store.mark_error("json decode")
            except Exception as exc:
                logger.warning("Serial telemetry error: %s — reconnecting", exc)
                self._store.mark_error(str(exc))
                try:
                    if self._ser is not None:
                        self._ser.close()
                except Exception:
                    pass
                self._ser = None
                time.sleep(2.0)

        try:
            if self._ser is not None:
                self._ser.close()
        except Exception:
            pass

    def _run_http_poll(self) -> None:
        try:
            import urllib.request
        except ImportError:
            return

        while not self._stop.is_set():
            try:
                req = urllib.request.Request(
                    self._http_poll_url,
                    headers={"User-Agent": "PoseVision-SensorDaemon/1.0"},
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                data = json.loads(body)
                if isinstance(data, dict):
                    self._store.update(data)
            except Exception as exc:
                self._store.mark_error(str(exc))
                logger.debug("HTTP telemetry poll failed: %s", exc)
            time.sleep(self._poll_interval_s)


def validate_stream_url(url: str) -> bool:
    try:
        u = urlparse(url)
        return u.scheme in ("http", "https") and bool(u.netloc)
    except Exception:
        return False
