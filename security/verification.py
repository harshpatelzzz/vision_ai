"""Offline verification of VPAP / secure JSONL hash chains."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional, Tuple

from security.logger import GENESIS_PREV_HASH, canonical_json


def verify_chain_detail(log_file_path: Path | str) -> Tuple[bool, Optional[int], int]:
    """
    Recompute hashes for each JSONL record and detect tampering.

    Returns ``(valid, corrupt_line_index, checked_entries)``.
    ``corrupt_line_index`` is the 0-based physical line number of the first bad record,
    or ``None`` if the file is missing or empty (treated as valid).
    """
    path = Path(log_file_path)
    if not path.is_file():
        return True, None, 0

    expected_prev = GENESIS_PREV_HASH
    line_index = 0
    checked = 0

    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                stripped = raw_line.strip()
                if not stripped:
                    line_index += 1
                    continue
                try:
                    rec = json.loads(stripped)
                    prev_h = str(rec.get("prev_hash", ""))
                    cur_h = str(rec.get("current_hash", ""))
                    ev: Any = rec.get("event")
                    if prev_h != expected_prev:
                        return False, line_index, checked
                    if ev is None:
                        return False, line_index, checked
                    cj = canonical_json(ev)
                    combined = (expected_prev + cj).encode("utf-8")
                    calc = hashlib.sha256(combined).hexdigest()
                    if calc != cur_h:
                        return False, line_index, checked
                    expected_prev = cur_h
                    checked += 1
                except (json.JSONDecodeError, TypeError, ValueError):
                    return False, line_index, checked
                line_index += 1
    except OSError:
        return False, None, checked

    return True, None, checked


def verify_log_chain(log_file_path: Path | str) -> bool:
    """Return ``True`` if the hash chain is intact (missing file is treated as valid)."""
    ok, _, _ = verify_chain_detail(log_file_path)
    return ok
