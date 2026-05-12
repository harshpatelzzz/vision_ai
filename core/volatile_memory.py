"""In-RAM frame storage — no persistent image writes (privacy)."""

from __future__ import annotations

from collections import deque
from typing import Deque, Optional

import numpy as np


class VolatileFrameStore:
    """
    Hold recent frames only in volatile memory (simulates tmpfs-style usage).

    Does not write images to disk. Callers must not retain references longer
    than needed for display or one-shot API responses.
    """

    __slots__ = ("_buffer", "_maxlen")

    def __init__(self, maxlen: int = 2) -> None:
        self._maxlen = max(1, maxlen)
        self._buffer: Deque[np.ndarray] = deque(maxlen=self._maxlen)

    def push(self, frame: np.ndarray) -> None:
        """Store a copy of ``frame`` (uint8 BGR)."""
        if frame is None or frame.size == 0:
            return
        self._buffer.append(np.ascontiguousarray(frame))

    @property
    def latest(self) -> Optional[np.ndarray]:
        """Most recent frame, or None."""
        if not self._buffer:
            return None
        return self._buffer[-1]

    def clear(self) -> None:
        self._buffer.clear()
