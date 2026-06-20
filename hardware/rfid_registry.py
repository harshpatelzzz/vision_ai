"""Process-wide hooks so FastAPI can reach the live RFID reader / access control.

Mirrors :mod:`hardware.registry` (telemetry) to avoid circular imports between
the capture loop and the API server. The pipeline registers the running
instances; the API reads them. When nothing is registered (API running
standalone), :func:`get_or_build_access_control` builds a file-backed
:class:`~security.access_control.AccessControl` so user CRUD still works.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Optional

_LOCK = threading.Lock()
_READER: Optional[Any] = None
_ACCESS_CONTROL: Optional[Any] = None


def register_rfid(reader: Optional[Any] = None, access_control: Optional[Any] = None) -> None:
    global _READER, _ACCESS_CONTROL
    with _LOCK:
        if reader is not None:
            _READER = reader
        if access_control is not None:
            _ACCESS_CONTROL = access_control


def get_rfid_reader() -> Optional[Any]:
    return _READER


def get_access_control() -> Optional[Any]:
    return _ACCESS_CONTROL


def clear_registration() -> None:
    global _READER, _ACCESS_CONTROL
    with _LOCK:
        _READER = None
        _ACCESS_CONTROL = None


def get_or_build_access_control(project_root: Path, config: Optional[dict] = None) -> Any:
    """Return the live AccessControl, or build a file-backed one on demand."""
    global _ACCESS_CONTROL
    with _LOCK:
        if _ACCESS_CONTROL is not None:
            return _ACCESS_CONTROL
    # Build lazily without a live reader (uid_provider stays None -> anonymous).
    from security.access_control import build_access_control_from_config

    cfg = config or {}
    ac = build_access_control_from_config(cfg, Path(project_root))
    with _LOCK:
        if _ACCESS_CONTROL is None:
            _ACCESS_CONTROL = ac
        return _ACCESS_CONTROL
