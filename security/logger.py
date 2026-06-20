"""VPAP: tamper-evident JSON log chain using SHA-256, with optional secure debounced logging."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    from blockchain.blockchain import Blockchain
except Exception:  # pragma: no cover
    Blockchain = None  # type: ignore[assignment]

GENESIS_PREV_HASH = "0" * 64


def _canonical_json(obj: Any) -> str:
    """Deterministic JSON for hashing (compact, sorted keys)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


# Public alias for chain verification and external tools.
canonical_json = _canonical_json


class VPAPLogger:
    """
    Append-only log where each record chains ``current_hash = SHA256(prev_hash + canonical_json(event))``.

    Records are stored as JSON Lines (one JSON object per line).
    """

    def __init__(self, log_path: Path) -> None:
        self.log_path = Path(log_path)
        self._prev_hash: str = self._load_tail_hash()

    def _load_tail_hash(self) -> str:
        if not self.log_path.is_file():
            return GENESIS_PREV_HASH
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                return str(rec.get("current_hash", GENESIS_PREV_HASH))
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            pass
        return GENESIS_PREV_HASH

    @property
    def prev_hash(self) -> str:
        return self._prev_hash

    def append(self, event: Dict[str, Any]) -> Dict[str, str]:
        """
        Append one event. Returns the full record including hashes.

        ``event`` must be JSON-serializable.
        """
        canonical = _canonical_json(event)
        combined = (self._prev_hash + canonical).encode("utf-8")
        current_hash = hashlib.sha256(combined).hexdigest()
        record = {
            "prev_hash": self._prev_hash,
            "current_hash": current_hash,
            "event": event,
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        self._prev_hash = current_hash
        return record

    def verify_chain(self, max_records: Optional[int] = None) -> bool:
        """
        Verify integrity of the log file (recompute hashes from genesis).

        Returns False if any line is corrupt or the chain breaks.
        """
        if not self.log_path.is_file():
            return True
        expected_prev = GENESIS_PREV_HASH
        count = 0
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    if rec.get("prev_hash") != expected_prev:
                        return False
                    ev = rec["event"]
                    canonical = _canonical_json(ev)
                    combined = (expected_prev + canonical).encode("utf-8")
                    calc = hashlib.sha256(combined).hexdigest()
                    if calc != rec.get("current_hash"):
                        return False
                    expected_prev = str(rec.get("current_hash", ""))
                    count += 1
                    if max_records is not None and count >= max_records:
                        break
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            return False
        return True


def normalize_event_record(
    *,
    alert_type: str,
    person_id: int,
    observation: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Standardize an event to the project schema (timestamp, person_id, bbox, ppe, posture, intrusion).

    ``alert_type`` is included for debouncing and audit (e.g. NO_HELMET).
    """
    ppe = observation.get("ppe") or {}
    bbox = observation.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        bbox = [0.0, 0.0, 0.0, 0.0]
    rec: Dict[str, Any] = {
        "timestamp": str(observation.get("timestamp", "")),
        "person_id": int(person_id),
        "bbox": [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])],
        "ppe": {
            "helmet": bool(ppe.get("helmet", False)),
            "vest": bool(ppe.get("vest", False)),
        },
        "posture": str(observation.get("posture", "Unknown")),
        "intrusion": bool(observation.get("intrusion", False)),
        "alert_type": str(alert_type),
    }
    if "telemetry" in observation:
        rec["telemetry"] = observation.get("telemetry")
    if observation.get("tamper_reason") is not None:
        rec["tamper_reason"] = observation.get("tamper_reason")
    # Preserve the RFID/RBAC authorization block (uid, name, role, zone,
    # authorized, decision, ...) so it is hash-chained and committed to the
    # blockchain/Merkle/IPFS sidecar alongside the alert.
    if isinstance(observation.get("access"), dict):
        rec["access"] = dict(observation["access"])
    return rec


class SecureLogger:
    """
    Hash-chained VPAP logging with time-based debounce on (person_id, alert_type).

    Reduces log spam while preserving tamper-evident structure.
    """

    def __init__(self, log_path: Path, debounce_seconds: float = 2.0) -> None:
        self._vpap = VPAPLogger(log_path)
        self._debounce_seconds = max(0.0, float(debounce_seconds))
        self._last_emit: Dict[Tuple[int, str], float] = {}
        self._blockchain = (
            Blockchain(ledger_path=self._vpap.log_path.parent / "blockchain_ledger.json")
            if Blockchain is not None
            else None
        )

    @property
    def log_path(self) -> Path:
        return self._vpap.log_path

    @property
    def prev_hash(self) -> str:
        return self._vpap.prev_hash

    def _debounce_key(self, event: Dict[str, Any]) -> Tuple[int, str]:
        pid = int(event.get("person_id", -1))
        et = str(event.get("alert_type", "EVENT"))
        return (pid, et)

    def log_event(self, event: Dict[str, Any], *, force: bool = False) -> Optional[Dict[str, str]]:
        """
        Append ``event`` if not suppressed by debounce.

        Returns the VPAP record dict, or None if skipped due to cooldown.
        """
        if not force and self._debounce_seconds > 0:
            key = self._debounce_key(event)
            now = time.monotonic()
            last = self._last_emit.get(key)
            if last is not None and (now - last) < self._debounce_seconds:
                return None
            self._last_emit[key] = now

        record = self._vpap.append(event)
        if self._blockchain is not None:
            try:
                self._blockchain.add_block(event)
            except Exception:
                # Preserve existing secure logging behavior even if blockchain sidecar is unavailable.
                pass
        return record

    def append(self, event: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Same as :meth:`log_event` without ``force`` (may return ``None`` if debounced)."""
        return self.log_event(event, force=False)

    def append_forced(self, event: Dict[str, Any]) -> Dict[str, str]:
        """Always append (e.g. tamper or operator events)."""
        out = self.log_event(event, force=True)
        assert out is not None
        return out

    def verify_chain(self, max_records: Optional[int] = None) -> bool:
        return self._vpap.verify_chain(max_records=max_records)

    @property
    def blockchain(self) -> Any:
        if self._blockchain is None:
            raise RuntimeError("blockchain backend unavailable")
        return self._blockchain

    def blockchain_summary(self) -> Dict[str, Any]:
        if self._blockchain is None:
            raise RuntimeError("blockchain backend unavailable")
        return self._blockchain.export_chain_json()

    def verify_blockchain(self) -> Dict[str, Any]:
        if self._blockchain is None:
            raise RuntimeError("blockchain backend unavailable")
        ok, corrupt_idx, reason = self._blockchain.validate_chain()
        return {
            "status": "valid" if ok else "tampered",
            "corrupt_block_index": corrupt_idx,
            "reason": reason,
        }

    def get_block(self, index: int) -> Optional[Dict[str, Any]]:
        if self._blockchain is None:
            raise RuntimeError("blockchain backend unavailable")
        return self._blockchain.get_block(index)

    def latest_merkle_root(self) -> str:
        if self._blockchain is None:
            raise RuntimeError("blockchain backend unavailable")
        return self._blockchain.latest_merkle_root()

    def node_status(self) -> Dict[str, Any]:
        if self._blockchain is None:
            raise RuntimeError("blockchain backend unavailable")
        return {"nodes": self._blockchain.nodes_status()}

    def get_ipfs_metadata(self, cid: str) -> Dict[str, Any]:
        if self._blockchain is None:
            raise RuntimeError("blockchain backend unavailable")
        return self._blockchain.ipfs_get(cid)

    def simulate_tamper(self) -> Dict[str, Any]:
        if self._blockchain is None:
            raise RuntimeError("blockchain backend unavailable")
        return self._blockchain.simulate_tamper()
