"""Secure data zeroization: wipe logs, temp frames, models, and trigger emergency shutdown."""

from __future__ import annotations

import logging
import os
import platform
from pathlib import Path
from typing import Optional

logger = logging.getLogger("posevision.zeroization")


def _secure_delete(path: Path) -> bool:
    """
    Best-effort secure deletion: overwrite file contents with zeros before unlinking.

    Returns True if the file was removed, False on failure.
    """
    try:
        if not path.is_file():
            return False
        size = path.stat().st_size
        with open(path, "r+b") as f:
            f.write(b"\x00" * size)
            f.flush()
            os.fsync(f.fileno())
        path.unlink()
        logger.info("Securely deleted: %s", path)
        return True
    except Exception:
        logger.exception("Failed to securely delete %s", path)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def wipe_logs(log_dir: str | Path) -> int:
    """
    Securely delete all log files (VPAP JSONL chains, tamper logs, console logs).

    Returns the number of files removed.
    """
    log_dir = Path(log_dir)
    if not log_dir.is_dir():
        logger.warning("Log directory does not exist: %s", log_dir)
        return 0

    count = 0
    for p in log_dir.iterdir():
        if p.is_file() and p.suffix in (".jsonl", ".log", ".txt"):
            if _secure_delete(p):
                count += 1
    logger.info("Wiped %d log file(s) from %s", count, log_dir)
    return count


def wipe_temp_frames(volatile_store: Optional[object] = None) -> None:
    """
    Clear any in-RAM frame buffers.

    Accepts an optional ``VolatileFrameStore`` instance (or any object with a
    ``clear()`` method).
    """
    if volatile_store is not None and hasattr(volatile_store, "clear"):
        volatile_store.clear()
        logger.info("Volatile frame store cleared")


def wipe_models(model_dir: str | Path, force: bool = False) -> int:
    """
    Delete model weight files (``.pt``, ``.onnx``, ``.engine``).

    Only runs when ``force`` is True (config-controlled), as model deletion is
    destructive and the system cannot recover without re-provisioning.

    Returns the number of files removed.
    """
    if not force:
        logger.info("Model wipe skipped (delete_models=false)")
        return 0

    model_dir = Path(model_dir)
    if not model_dir.is_dir():
        return 0

    count = 0
    for ext in ("*.pt", "*.onnx", "*.engine"):
        for p in model_dir.glob(ext):
            if _secure_delete(p):
                count += 1
    logger.warning("Wiped %d model file(s) from %s", count, model_dir)
    return count


def emergency_shutdown(shutdown_enabled: bool = True) -> None:
    """
    Initiate an immediate OS shutdown.

    Only runs when ``shutdown_enabled`` is True (config ``shutdown_on_tamper``).
    On unsupported platforms the call is logged but skipped.
    """
    if not shutdown_enabled:
        logger.info("System shutdown skipped (shutdown_on_tamper=false)")
        return

    system = platform.system().lower()
    logger.critical("EMERGENCY SHUTDOWN initiated")

    try:
        if system == "linux":
            os.system("sudo shutdown now")
        elif system == "windows":
            os.system("shutdown /s /t 0")
        elif system == "darwin":
            os.system("sudo shutdown -h now")
        else:
            logger.error("Unsupported platform for shutdown: %s", system)
    except Exception:
        logger.exception("Emergency shutdown command failed")


def full_zeroization(
    project_root: str | Path,
    log_dir: str | Path = "logs",
    delete_models: bool = False,
    shutdown_on_tamper: bool = True,
    volatile_store: Optional[object] = None,
) -> None:
    """
    Execute the complete zeroization sequence:

    1. Wipe logs
    2. Clear RAM buffers
    3. Optionally wipe models
    4. Trigger emergency shutdown
    """
    root = Path(project_root)
    log_path = Path(log_dir) if Path(log_dir).is_absolute() else root / log_dir

    logger.critical("=== ZEROIZATION SEQUENCE STARTED ===")

    wipe_logs(log_path)
    wipe_temp_frames(volatile_store)
    wipe_models(root / "models", force=delete_models)

    logger.critical("=== ZEROIZATION COMPLETE — triggering shutdown ===")
    emergency_shutdown(shutdown_enabled=shutdown_on_tamper)
