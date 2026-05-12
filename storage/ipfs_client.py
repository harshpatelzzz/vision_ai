from __future__ import annotations

import base64
import json
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet

try:
    import ipfshttpclient
except Exception:  # pragma: no cover
    ipfshttpclient = None


class IPFSClient:
    """Encrypted metadata-only IPFS storage abstraction."""

    def __init__(self, address: str = "/dns/localhost/tcp/5001/http", key: Optional[bytes] = None) -> None:
        self._fernet = Fernet(key or Fernet.generate_key())
        self._mock_store: Dict[str, str] = {}
        self._counter = 0
        self._client = None
        if ipfshttpclient is not None:
            try:
                self._client = ipfshttpclient.connect(address)
            except Exception:
                self._client = None

    @property
    def encryption_key(self) -> str:
        return self._fernet._signing_key.hex()  # type: ignore[attr-defined]

    def encrypt_event(self, event: Dict[str, Any]) -> str:
        raw = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
        token = self._fernet.encrypt(raw)
        return base64.b64encode(token).decode("utf-8")

    def decrypt_event(self, encoded: str) -> Dict[str, Any]:
        token = base64.b64decode(encoded.encode("utf-8"))
        raw = self._fernet.decrypt(token)
        return json.loads(raw.decode("utf-8"))

    def put_encrypted_metadata(self, event: Dict[str, Any]) -> str:
        encoded = self.encrypt_event(event)
        if self._client is not None:
            payload = json.dumps({"encrypted_event": encoded}, sort_keys=True).encode("utf-8")
            res = self._client.add_bytes(payload)
            return str(res)
        self._counter += 1
        cid = f"mock-cid-{self._counter:08d}"
        self._mock_store[cid] = encoded
        return cid

    def get_encrypted_metadata(self, cid: str) -> Dict[str, Any]:
        if self._client is not None:
            raw = self._client.cat(cid)
            return json.loads(raw.decode("utf-8"))
        if cid not in self._mock_store:
            raise KeyError("CID not found")
        return {"encrypted_event": self._mock_store[cid]}
