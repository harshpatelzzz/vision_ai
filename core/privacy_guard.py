"""Strict privacy enforcement: frames stay in memory; no silent disk persistence for imagery."""

from __future__ import annotations

import gc
import logging
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np

_LOG = logging.getLogger("posevision.privacy")

# Extensions treated as raw frame / video artifact writes (blocked unless export allowed).
_FRAME_MEDIA_EXTENSIONS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".tif",
        ".tiff",
        ".webp",
        ".mp4",
        ".avi",
        ".mkv",
        ".mov",
        ".m4v",
    }
)


class PrivacyGuard:
    """
    Enforces memory-only frame handling and blocks accidental persistence of pixel data.

    Metadata (JSON events) may still be written via the logging layer; this guard focuses
    on **frames** and **encoded video/image files**.
    """

    def __init__(
        self,
        project_root: Path,
        *,
        allow_video_export: bool = False,
    ) -> None:
        self._project_root = Path(project_root).resolve()
        self._allow_video_export = bool(allow_video_export)

    @property
    def allow_video_export(self) -> bool:
        return self._allow_video_export

    def validate_no_disk_write(self, path: Union[str, Path]) -> bool:
        """
        Return True if writing ``path`` is allowed under current policy.

        If ``allow_video_export`` is False and the path looks like a frame/video file,
        logs a warning and returns False.
        """
        p = Path(path)
        suf = p.suffix.lower()
        if suf in _FRAME_MEDIA_EXTENSIONS and not self._allow_video_export:
            _LOG.warning(
                "Privacy policy blocks disk write of frame/video artifact: %s "
                "(set privacy.allow_video_export to opt in)",
                p,
            )
            return False
        return True

    def clear_temp_buffers(self, volatile_store: Optional[Any] = None) -> None:
        """
        Clear in-memory frame ring buffers (volatile store).

        Safe to call every frame for strict minimum retention.
        """
        if volatile_store is not None and hasattr(volatile_store, "clear"):
            volatile_store.clear()

    def enforce_memory_only(self, volatile_store: Optional[Any] = None) -> None:
        """
        Apply strict memory-only policy: wipe volatile frame buffers and suggest GC.

        Intended to run once per processed frame after downstream code has copied any
        display payload it needs.
        """
        self.clear_temp_buffers(volatile_store)
        gc.collect()

    def safe_frame_view(self, frame: "np.ndarray") -> "np.ndarray":
        """
        Return a contiguous in-memory array for inference or display (never touches disk).
        """
        if frame is None or frame.size == 0:
            return frame
        return np.ascontiguousarray(frame)

    def assert_export_allowed(self, path: Optional[Union[str, Path]]) -> bool:
        """
        Return whether annotated video export to ``path`` is permitted.

        Combines policy flag with ``validate_no_disk_write``.
        """
        if path is None:
            return True
        if not self._allow_video_export:
            _LOG.warning(
                "Video export denied by privacy policy (privacy.allow_video_export=false): %s",
                path,
            )
            return False
        return self.validate_no_disk_write(path)
