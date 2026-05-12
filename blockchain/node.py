from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from blockchain.block import Block


@dataclass
class Node:
    node_id: str
    host: str
    port: int
    trusted: bool = True
    peers: Dict[str, "Node"] = field(default_factory=dict)
    local_chain: List[Block] = field(default_factory=list)

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

    def discover_peer(self, peer: "Node") -> None:
        if peer.node_id != self.node_id:
            self.peers[peer.node_id] = peer

    def broadcast_block(self, block: Block) -> None:
        for peer in self.peers.values():
            peer.receive_block(block)

    def receive_block(self, block: Block) -> None:
        self.local_chain.append(Block.from_dict(block.to_dict()))

    def sync_chain(self, chain: List[Block]) -> None:
        self.local_chain = [Block.from_dict(b.to_dict()) for b in chain]

    def status(self) -> Dict[str, object]:
        return {
            "node_id": self.node_id,
            "address": self.address,
            "trusted": self.trusted,
            "peer_count": len(self.peers),
            "local_height": len(self.local_chain),
        }
