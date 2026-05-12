from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from blockchain.block import Block
from blockchain.consensus import PoAConsensus
from blockchain.merkle import get_merkle_root
from blockchain.node import Node
from security.signature import generate_rsa_keypair, sign_block, verify_signature
from storage.ipfs_client import IPFSClient


class Blockchain:
    def __init__(
        self,
        *,
        ledger_path: Path,
        validator_node_id: str = "node-a",
        validators: Optional[List[str]] = None,
        private_key_path: Optional[Path] = None,
        public_key_path: Optional[Path] = None,
    ) -> None:
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.validator_node_id = validator_node_id
        self.consensus = PoAConsensus(validators or ["node-a", "node-b", "node-c"])
        self.ipfs = IPFSClient()
        key_dir = self.ledger_path.parent / "keys"
        self.private_key_path = private_key_path or (key_dir / "block_signing_private.pem")
        self.public_key_path = public_key_path or (key_dir / "block_signing_public.pem")
        if not self.private_key_path.exists() or not self.public_key_path.exists():
            generate_rsa_keypair(self.private_key_path, self.public_key_path)

        self.nodes = self._init_nodes()
        self.chain: List[Block] = []
        self._last_merkle_root = "0" * 64
        self._last_validation: Dict[str, Any] = {"status": "valid", "corrupt_index": None}
        self._load_or_bootstrap()

    def _init_nodes(self) -> Dict[str, Node]:
        node_a = Node("node-a", "localhost", 8001, trusted=True)
        node_b = Node("node-b", "localhost", 8002, trusted=True)
        node_c = Node("node-c", "localhost", 8003, trusted=True)
        for src in (node_a, node_b, node_c):
            for dst in (node_a, node_b, node_c):
                if src.node_id != dst.node_id:
                    src.discover_peer(dst)
        return {n.node_id: n for n in (node_a, node_b, node_c)}

    def _load_or_bootstrap(self) -> None:
        if self.ledger_path.is_file():
            try:
                payload = json.loads(self.ledger_path.read_text(encoding="utf-8"))
                self.chain = [Block.from_dict(b) for b in payload.get("chain", [])]
            except Exception:
                self.chain = []
        if not self.chain:
            self.create_genesis_block()
            self._persist()
        else:
            self._last_merkle_root = self.chain[-1].merkle_root
        self._sync_nodes()

    def _persist(self) -> None:
        payload = {"chain": [b.to_dict() for b in self.chain]}
        self.ledger_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _sync_nodes(self) -> None:
        for node in self.nodes.values():
            node.sync_chain(self.chain)

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_genesis_block(self) -> Block:
        genesis = Block(
            index=0,
            timestamp=self._timestamp(),
            event={"type": "GENESIS"},
            previous_hash="0" * 64,
            merkle_root=get_merkle_root([{"type": "GENESIS"}]),
            ipfs_cid="GENESIS",
            nonce=0,
            signature="",
        )
        genesis.seal()
        genesis.signature = sign_block(genesis.hash, self.private_key_path)
        self.chain = [genesis]
        self._last_merkle_root = genesis.merkle_root
        return genesis

    def get_latest_block(self) -> Block:
        return self.chain[-1]

    def add_block(self, event: Dict[str, Any], *, events_batch: Optional[List[Dict[str, Any]]] = None) -> Block:
        if not self.consensus.can_append(self.validator_node_id):
            raise PermissionError("validator not authorized in PoA whitelist")

        batch = events_batch if events_batch else [event]
        merkle_root = get_merkle_root(batch)
        ipfs_cid = self.ipfs.put_encrypted_metadata(event)
        prev = self.get_latest_block()
        block = Block(
            index=prev.index + 1,
            timestamp=self._timestamp(),
            event=event,
            previous_hash=prev.hash,
            merkle_root=merkle_root,
            ipfs_cid=ipfs_cid,
            nonce=0,
        )
        block.seal()
        block.signature = sign_block(block.hash, self.private_key_path)
        self.chain.append(block)
        self._last_merkle_root = merkle_root
        self._persist()
        self._sync_nodes()
        self.nodes[self.validator_node_id].broadcast_block(block)
        return block

    def validate_chain(self) -> Tuple[bool, Optional[int], str]:
        for idx, block in enumerate(self.chain):
            if block.calculate_hash() != block.hash:
                self._last_validation = {"status": "tampered", "corrupt_index": idx, "reason": "block_modified"}
                return False, idx, "block_modified"
            if not verify_signature(block.hash, block.signature, self.public_key_path):
                self._last_validation = {"status": "tampered", "corrupt_index": idx, "reason": "signature_invalid"}
                return False, idx, "signature_invalid"
            if idx > 0 and block.previous_hash != self.chain[idx - 1].hash:
                self._last_validation = {
                    "status": "tampered",
                    "corrupt_index": idx,
                    "reason": "previous_hash_mismatch",
                }
                return False, idx, "previous_hash_mismatch"
            if block.merkle_root != get_merkle_root([block.event]):
                self._last_validation = {"status": "tampered", "corrupt_index": idx, "reason": "merkle_root_mismatch"}
                return False, idx, "merkle_root_mismatch"
        self._last_validation = {"status": "valid", "corrupt_index": None, "reason": "ok"}
        return True, None, "ok"

    def export_chain_json(self) -> Dict[str, Any]:
        return {
            "height": len(self.chain),
            "latest_hash": self.get_latest_block().hash if self.chain else "",
            "latest_merkle_root": self._last_merkle_root,
            "chain": [b.to_dict() for b in self.chain],
            "validation": self._last_validation,
        }

    def get_block(self, index: int) -> Optional[Dict[str, Any]]:
        if 0 <= index < len(self.chain):
            return self.chain[index].to_dict()
        return None

    def latest_merkle_root(self) -> str:
        return self._last_merkle_root

    def nodes_status(self) -> List[Dict[str, Any]]:
        return [n.status() for n in self.nodes.values()]

    def ipfs_get(self, cid: str) -> Dict[str, Any]:
        return self.ipfs.get_encrypted_metadata(cid)

    def simulate_tamper(self) -> Dict[str, Any]:
        if len(self.chain) <= 1:
            raise ValueError("not enough blocks to tamper")
        self.chain[1].event["tampered"] = True
        self._persist()
        ok, idx, reason = self.validate_chain()
        return {"status": "valid" if ok else "tampered", "corrupt_index": idx, "reason": reason}
