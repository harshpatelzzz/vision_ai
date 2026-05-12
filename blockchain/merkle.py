from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Sequence


def _hash_leaf(event: Dict[str, Any]) -> str:
    payload = json.dumps(event, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hash_pair(left: str, right: str) -> str:
    return hashlib.sha256((left + right).encode("utf-8")).hexdigest()


def build_merkle_tree(events: Sequence[Dict[str, Any]]) -> List[List[str]]:
    if not events:
        return [["0" * 64]]
    level = [_hash_leaf(ev) for ev in events]
    tree = [level]
    while len(level) > 1:
        nxt: List[str] = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else left
            nxt.append(_hash_pair(left, right))
        tree.append(nxt)
        level = nxt
    return tree


def get_merkle_root(events: Sequence[Dict[str, Any]]) -> str:
    tree = build_merkle_tree(events)
    return tree[-1][0]


def verify_merkle_proof(leaf_hash: str, proof: Sequence[str], merkle_root: str) -> bool:
    current = leaf_hash
    for sibling in proof:
        left, right = sorted([current, sibling])
        current = _hash_pair(left, right)
    return current == merkle_root
