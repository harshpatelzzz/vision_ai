from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Dict


def _canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


@dataclass
class Block:
    index: int
    timestamp: str
    event: Dict[str, Any]
    previous_hash: str
    merkle_root: str
    ipfs_cid: str
    nonce: int
    signature: str = ""
    hash: str = ""

    def calculate_hash(self) -> str:
        payload = {
            "index": self.index,
            "timestamp": self.timestamp,
            "event": self.event,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "ipfs_cid": self.ipfs_cid,
            "nonce": self.nonce,
        }
        return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()

    def seal(self) -> None:
        self.hash = self.calculate_hash()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Block":
        return cls(
            index=int(data.get("index", 0)),
            timestamp=str(data.get("timestamp", "")),
            event=dict(data.get("event", {})),
            previous_hash=str(data.get("previous_hash", "")),
            merkle_root=str(data.get("merkle_root", "")),
            ipfs_cid=str(data.get("ipfs_cid", "")),
            nonce=int(data.get("nonce", 0)),
            signature=str(data.get("signature", "")),
            hash=str(data.get("hash", "")),
        )
