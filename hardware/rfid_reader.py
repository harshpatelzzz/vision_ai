"""RFID reader daemon: MFRC522-on-ESP32 over Serial / WiFi-HTTP, with simulation.

The ESP32 firmware (``hardware/esp32/rfid_access_control.ino``) emits one JSON
object per scan, e.g.::

    {"type":"rfid","uid":"A1:B2:C3:D4","rssi":-42,"reader":"gate-1"}

:class:`RfidReader` runs a background thread that:
  * scans continuously (serial line read or HTTP poll),
  * de-duplicates rapid repeat reads of the same tag (``dedup_seconds``),
  * caches recent scans and exposes the latest UID within a correlation window,
  * survives disconnects with automatic reconnect/backoff.

It mirrors the structure of :class:`hardware.sensor_daemon.SensorDaemon` so the
two hardware stacks behave consistently.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Deque, Dict, List, Optional

from security.user_database import normalize_uid

logger = logging.getLogger("posevision.rfid_reader")


@dataclass(frozen=True)
class Scan:
    uid: str
    timestamp: str
    monotonic: float
    raw: Dict[str, Any]


class RfidReader(threading.Thread):
    """Continuous RFID UID reader with dedup, caching and reconnect."""

    def __init__(
        self,
        *,
        mode: str = "simulation",
        serial_port: Optional[str] = None,
        baudrate: int = 115200,
        http_poll_url: Optional[str] = None,
        poll_interval_s: float = 0.3,
        dedup_seconds: float = 1.5,
        correlation_window_seconds: float = 5.0,
        simulation_uids: Optional[List[str]] = None,
        simulation_interval_s: float = 4.0,
        cache_size: int = 200,
        on_scan: Optional[Callable[[Scan], None]] = None,
        name: str = "rfid-reader",
    ) -> None:
        super().__init__(name=name, daemon=True)
        self.mode = (mode or "simulation").lower()
        self._serial_port = serial_port
        self._baudrate = int(baudrate)
        self._http_poll_url = http_poll_url
        self._poll_interval_s = max(0.05, float(poll_interval_s))
        self._dedup_seconds = max(0.0, float(dedup_seconds))
        self._window_s = max(0.0, float(correlation_window_seconds))
        self._sim_uids = [normalize_uid(u) for u in (simulation_uids or [])]
        self._sim_interval_s = max(0.5, float(simulation_interval_s))
        self._on_scan = on_scan

        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._scans: Deque[Scan] = deque(maxlen=int(cache_size))
        self._last_uid_seen: Dict[str, float] = {}
        self._latest: Optional[Scan] = None
        self._connected = False
        self._last_error: Optional[str] = None
        self._ser = None

    # ----- lifecycle ------------------------------------------------------
    def start_reader(self) -> "RfidReader":
        """Start continuous scanning (alias for ``Thread.start``)."""
        if not self.is_alive():
            self.start()
        return self

    def set_on_scan(self, callback: Optional[Callable[[Scan], None]]) -> None:
        """Register/replace the per-scan callback (used for gate access evaluation)."""
        self._on_scan = callback

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            if self.mode == "serial" and self._serial_port:
                self._run_serial()
            elif self.mode in ("http", "wifi") and self._http_poll_url:
                self._run_http_poll()
            else:
                self._run_simulation()
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("RFID reader crashed: %s", exc)
            self._last_error = str(exc)

    # ----- public query API ----------------------------------------------
    def ingest(self, uid: str, raw: Optional[Dict[str, Any]] = None) -> Optional[Scan]:
        """Record a scan; returns the :class:`Scan` or ``None`` if deduped."""
        uid_n = normalize_uid(uid)
        if not uid_n:
            return None
        now = time.monotonic()
        with self._lock:
            last = self._last_uid_seen.get(uid_n)
            if last is not None and (now - last) < self._dedup_seconds:
                self._last_uid_seen[uid_n] = now
                return None
            self._last_uid_seen[uid_n] = now
            scan = Scan(
                uid=uid_n,
                timestamp=datetime.now(timezone.utc).isoformat(),
                monotonic=now,
                raw=dict(raw or {}),
            )
            self._scans.append(scan)
            self._latest = scan
            self._connected = True
            self._last_error = None
        if self._on_scan is not None:
            try:
                self._on_scan(scan)
            except Exception:
                logger.debug("on_scan callback failed", exc_info=True)
        logger.info("RFID scan uid=%s reader=%s", uid_n, (raw or {}).get("reader", "?"))
        return scan

    def read_uid(self, within_seconds: Optional[float] = None) -> Optional[str]:
        """Most recent UID seen within the correlation window (or ``None``)."""
        window = self._window_s if within_seconds is None else float(within_seconds)
        now = time.monotonic()
        with self._lock:
            if self._latest is None:
                return None
            if window > 0 and (now - self._latest.monotonic) > window:
                return None
            return self._latest.uid

    def last_scan(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if self._latest is None:
                return None
            s = self._latest
            return {"uid": s.uid, "timestamp": s.timestamp, "raw": s.raw}

    def recent_scans(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._scans)
        items = items[-limit:] if limit else items
        return [{"uid": s.uid, "timestamp": s.timestamp, "raw": s.raw} for s in items]

    def verify_uid(self, uid: str, user_db: Any = None) -> bool:
        """True if ``uid`` exists in the supplied user database."""
        if user_db is None:
            return False
        return bool(user_db.has_user(uid))

    def get_user(self, uid: str, user_db: Any = None) -> Optional[Any]:
        """Look up the :class:`~security.user_database.User` for ``uid``."""
        if user_db is None:
            return None
        return user_db.get_user(uid)

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "mode": self.mode,
                "connected": self._connected,
                "running": self.is_alive(),
                "last_error": self._last_error,
                "scans_cached": len(self._scans),
                "last_scan": (
                    {"uid": self._latest.uid, "timestamp": self._latest.timestamp}
                    if self._latest
                    else None
                ),
            }

    # ----- backends -------------------------------------------------------
    def _parse_and_ingest(self, raw_line: str) -> None:
        raw_line = raw_line.strip()
        if not raw_line or not raw_line.startswith("{"):
            return
        try:
            obj = json.loads(raw_line)
        except json.JSONDecodeError:
            self._last_error = "json decode"
            return
        if not isinstance(obj, dict):
            return
        uid = obj.get("uid") or obj.get("UID") or obj.get("tag")
        if uid:
            self.ingest(str(uid), obj)

    def _run_serial(self) -> None:
        try:
            import serial  # type: ignore[import-untyped]
        except ImportError:
            logger.error("pyserial not installed — cannot read RFID over serial")
            self._last_error = "pyserial missing"
            return

        while not self._stop.is_set():
            try:
                if self._ser is None:
                    self._ser = serial.Serial(self._serial_port, self._baudrate, timeout=1.0)
                    self._connected = True
                    logger.info("RFID serial open %s @ %s", self._serial_port, self._baudrate)
                raw = self._ser.readline().decode("utf-8", errors="replace")
                if raw:
                    self._parse_and_ingest(raw)
            except Exception as exc:
                self._connected = False
                self._last_error = str(exc)
                logger.warning("RFID serial error: %s — reconnecting", exc)
                try:
                    if self._ser is not None:
                        self._ser.close()
                except Exception:
                    pass
                self._ser = None
                self._stop.wait(2.0)

        try:
            if self._ser is not None:
                self._ser.close()
        except Exception:
            pass

    def _run_http_poll(self) -> None:
        import urllib.request

        while not self._stop.is_set():
            try:
                req = urllib.request.Request(
                    self._http_poll_url,
                    headers={"User-Agent": "PoseVision-RfidReader/1.0"},
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                self._connected = True
                data = json.loads(body)
                # Accept either a single object or {"scans":[...]} batch.
                if isinstance(data, dict) and "uid" in data:
                    self.ingest(str(data["uid"]), data)
                elif isinstance(data, dict) and isinstance(data.get("scans"), list):
                    for item in data["scans"]:
                        if isinstance(item, dict) and item.get("uid"):
                            self.ingest(str(item["uid"]), item)
            except Exception as exc:
                self._connected = False
                self._last_error = str(exc)
                logger.debug("RFID HTTP poll failed: %s", exc)
            self._stop.wait(self._poll_interval_s)

    def _run_simulation(self) -> None:
        """Cycle through ``simulation_uids`` so the stack is testable with no HW."""
        if not self._sim_uids:
            self._sim_uids = ["A1:B2:C3:D4", "E5:F6:G7:H8", "ZZ:ZZ:ZZ:ZZ"]
        logger.info("RFID reader in SIMULATION mode (%d tags)", len(self._sim_uids))
        idx = 0
        while not self._stop.is_set():
            uid = self._sim_uids[idx % len(self._sim_uids)]
            self.ingest(uid, {"reader": "sim", "simulated": True})
            idx += 1
            self._stop.wait(self._sim_interval_s)


# --------------------------------------------------------------------------
# Module-level singleton helpers (spec-named convenience API).
# --------------------------------------------------------------------------
_default_reader: Optional[RfidReader] = None
_default_user_db: Any = None


def start_reader(reader: Optional[RfidReader] = None, user_db: Any = None) -> RfidReader:
    """Start (or reuse) a process-wide default reader and return it."""
    global _default_reader, _default_user_db
    if user_db is not None:
        _default_user_db = user_db
    if reader is not None:
        _default_reader = reader
    if _default_reader is None:
        _default_reader = RfidReader()
    return _default_reader.start_reader()


def read_uid(within_seconds: Optional[float] = None) -> Optional[str]:
    return _default_reader.read_uid(within_seconds) if _default_reader else None


def verify_uid(uid: str) -> bool:
    if _default_reader is None:
        return False
    return _default_reader.verify_uid(uid, _default_user_db)


def get_user(uid: str) -> Optional[Any]:
    if _default_reader is None:
        return None
    return _default_reader.get_user(uid, _default_user_db)
