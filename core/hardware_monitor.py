"""Hardware tamper detection: GPIO (Raspberry Pi / Jetson), Serial (ESP32), and simulation modes."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("posevision.hardware")

TamperCallback = Callable[[], None]

_GPIO_AVAILABLE = False
_SERIAL_AVAILABLE = False

try:
    import RPi.GPIO as GPIO  # type: ignore[import-untyped]
    _GPIO_AVAILABLE = True
except ImportError:
    GPIO = None

try:
    import serial  # type: ignore[import-untyped]
    _SERIAL_AVAILABLE = True
except ImportError:
    serial = None


class HardwareMonitor:
    """
    Monitor hardware tamper signals from a microcontroller (ESP32/STM32).

    Supports three back-ends:
      * **gpio**  – rising-edge interrupt on a configurable pin (RPi.GPIO)
      * **serial** – listens for ``TAMPER`` line on USB-serial (pyserial)
      * **simulation** – keyboard trigger (press ``T``) for testing without hardware
    """

    def __init__(
        self,
        mode: str = "gpio",
        gpio_pin: int = 17,
        serial_port: str = "/dev/ttyUSB0",
        baudrate: int = 115200,
    ) -> None:
        if mode not in ("gpio", "serial", "simulation"):
            raise ValueError(f"Unsupported mode: {mode!r}. Use 'gpio', 'serial', or 'simulation'.")

        self._mode = mode
        self._gpio_pin = gpio_pin
        self._serial_port = serial_port
        self._baudrate = baudrate

        self._tamper_detected = threading.Event()
        self._callbacks: List[TamperCallback] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_tamper_time: Optional[str] = None

    @property
    def mode(self) -> str:
        return self._mode

    def start(self) -> None:
        """Begin listening for tamper signals (non-blocking, spawns daemon thread)."""
        if self._running:
            logger.warning("HardwareMonitor already running")
            return

        self._running = True

        if self._mode == "gpio":
            self._start_gpio()
        elif self._mode == "serial":
            self._start_serial()
        elif self._mode == "simulation":
            self._start_simulation()

        logger.info("HardwareMonitor started in %s mode", self._mode)

    def stop(self) -> None:
        """Gracefully shut down the monitor thread and release resources."""
        self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if self._mode == "gpio" and _GPIO_AVAILABLE and GPIO is not None:
            try:
                GPIO.cleanup(self._gpio_pin)
            except Exception:
                pass
        logger.info("HardwareMonitor stopped")

    def is_tamper_detected(self) -> bool:
        """Return True if a tamper signal has been received (latching)."""
        return self._tamper_detected.is_set()

    def register_callback(self, callback_fn: TamperCallback) -> None:
        """Register a function to invoke when tamper is first detected."""
        with self._lock:
            self._callbacks.append(callback_fn)

    def get_status(self) -> Dict[str, Any]:
        """Snapshot for API consumption."""
        return {
            "tamper_detected": self._tamper_detected.is_set(),
            "mode": self._mode,
            "last_tamper_time": self._last_tamper_time,
            "monitor_running": self._running,
        }

    def trigger_tamper(self) -> None:
        """
        Programmatic tamper trigger (used by simulation mode and unit tests).

        Safe to call from any thread; callbacks fire at most once.
        """
        if self._tamper_detected.is_set():
            return
        self._tamper_detected.set()
        self._last_tamper_time = datetime.now(timezone.utc).isoformat()
        logger.critical("TAMPER DETECTED [mode=%s]", self._mode)
        with self._lock:
            for cb in self._callbacks:
                try:
                    cb()
                except Exception:
                    logger.exception("Tamper callback raised an exception")

    # ── GPIO back-end ────────────────────────────────────────────────

    def _start_gpio(self) -> None:
        if not _GPIO_AVAILABLE or GPIO is None:
            logger.warning("RPi.GPIO unavailable — falling back to serial mode")
            self._mode = "serial"
            self._start_serial()
            return

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.add_event_detect(
            self._gpio_pin,
            GPIO.RISING,
            callback=self._gpio_callback,
            bouncetime=300,
        )
        logger.info("GPIO interrupt registered on BCM pin %d", self._gpio_pin)

    def _gpio_callback(self, channel: int) -> None:
        logger.info("GPIO rising edge on channel %d", channel)
        self.trigger_tamper()

    # ── Serial back-end ──────────────────────────────────────────────

    def _start_serial(self) -> None:
        if not _SERIAL_AVAILABLE or serial is None:
            logger.error("pyserial unavailable — cannot start serial monitor")
            return

        self._thread = threading.Thread(
            target=self._serial_loop,
            name="hw-serial-monitor",
            daemon=True,
        )
        self._thread.start()

    def _serial_loop(self) -> None:
        ser: Optional[Any] = None
        while self._running and not self._tamper_detected.is_set():
            try:
                if ser is None:
                    ser = serial.Serial(
                        self._serial_port,
                        self._baudrate,
                        timeout=1.0,
                    )
                    logger.info("Serial port %s opened", self._serial_port)

                line = ser.readline().decode("utf-8", errors="replace").strip()
                if "TAMPER" in line.upper():
                    self.trigger_tamper()
            except serial.SerialException:
                logger.warning("Serial connection lost — retrying in 2 s")
                ser = None
                time.sleep(2.0)
            except Exception:
                logger.exception("Unexpected error in serial monitor")
                time.sleep(1.0)

        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass

    # ── Simulation back-end ──────────────────────────────────────────

    def _start_simulation(self) -> None:
        self._thread = threading.Thread(
            target=self._simulation_loop,
            name="hw-sim-monitor",
            daemon=True,
        )
        self._thread.start()

    def _simulation_loop(self) -> None:
        """Poll stdin for the ``T`` key to simulate a tamper event."""
        logger.info("Simulation mode: press 'T' + Enter in the console to trigger tamper")
        while self._running and not self._tamper_detected.is_set():
            try:
                import sys
                if sys.stdin is None or sys.stdin.closed:
                    time.sleep(0.5)
                    continue
                import select
                if hasattr(select, "select"):
                    ready, _, _ = select.select([sys.stdin], [], [], 0.5)
                    if ready:
                        ch = sys.stdin.readline().strip().upper()
                        if ch == "T":
                            self.trigger_tamper()
                else:
                    time.sleep(0.5)
            except Exception:
                time.sleep(0.5)
