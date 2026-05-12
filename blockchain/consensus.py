from __future__ import annotations

from typing import Iterable, Set


class PoAConsensus:
    """Lightweight Proof-of-Authority validator whitelist."""

    def __init__(self, validators: Iterable[str]) -> None:
        self.validators: Set[str] = {str(v) for v in validators}

    def is_validator(self, node_id: str) -> bool:
        return str(node_id) in self.validators

    def can_append(self, node_id: str) -> bool:
        return self.is_validator(node_id)
