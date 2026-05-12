"""Robust OpenCV capture for HTTP/MJPEG streams (e.g. ESP32-CAM :81/stream)."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional, Tuple

import cv2

logger = logging.getLogger("posevision.stream")


class RobustHttpStreamCapture:
    """
    Duck-typed subset of ``cv2.VideoCapture`` for MJPEG URLs with reconnect,
    bounded latency (small buffer), and read retries after failures.
    """

    def __init__(
        self,
        url: str,
        *,
        reconnect_delay_s: float = 2.0,
        open_timeout_ms: int = 8000,
        read_retries: int = 5,
        buffer_size: int = 1,
    ) -> None:
        self._url = url
        self._reconnect_delay_s = max(0.1, reconnect_delay_s)
        self._open_timeout_ms = max(500, open_timeout_ms)
        self._read_retries = max(1, read_retries)
        self._buffer_size = max(1, buffer_size)
        self._cap: Optional[cv2.VideoCapture] = None
        self._last_good_read = time.monotonic()
        self._open_capture()

    @property
    def url(self) -> str:
        return self._url

    def _release_cap(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def _open_capture(self) -> bool:
        self._release_cap()
        cap = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            logger.warning("Failed to open stream %s", self._url)
            return False
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, self._buffer_size)
        except Exception:
            pass
        ot = getattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC", None)
        if ot is not None:
            try:
                cap.set(ot, float(self._open_timeout_ms))
            except Exception:
                pass
        self._cap = cap
        logger.info("Opened MJPEG stream %s", self._url)
        return True

    def isOpened(self) -> bool:
        return self._cap is not None and bool(self._cap.isOpened())

    def get(self, prop: int) -> float:
        if self._cap is None:
            return 0.0
        try:
            return float(self._cap.get(prop))
        except Exception:
            return 0.0

    def read(self) -> Tuple[bool, Optional[Any]]:
        for attempt in range(self._read_retries):
            if self._cap is None or not self._cap.isOpened():
                time.sleep(self._reconnect_delay_s)
                if not self._open_capture():
                    continue

            ret, frame = self._cap.read()
            if ret and frame is not None:
                self._last_good_read = time.monotonic()
                return True, frame

            logger.warning("Bad frame from stream (attempt %s/%s)", attempt + 1, self._read_retries)
            self._release_cap()
            time.sleep(min(1.0, 0.2 * (attempt + 1)))

        return False, None

    def release(self) -> None:
        self._release_cap()

    def stale_seconds(self) -> float:
        return time.monotonic() - self._last_good_read
