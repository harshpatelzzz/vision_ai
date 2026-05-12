from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def generate_rsa_keypair(private_key_path: Path, public_key_path: Path) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    public_key_path.parent.mkdir(parents=True, exist_ok=True)
    private_key_path.write_bytes(private_bytes)
    public_key_path.write_bytes(public_bytes)


def _load_private_key(private_key_path: Path):
    return serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)


def _load_public_key(public_key_path: Path):
    return serialization.load_pem_public_key(public_key_path.read_bytes())


def sign_block(block_hash: str, private_key_path: Path) -> str:
    private_key = _load_private_key(private_key_path)
    signature = private_key.sign(
        block_hash.encode("utf-8"),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def verify_signature(block_hash: str, signature: str, public_key_path: Path) -> bool:
    try:
        public_key = _load_public_key(public_key_path)
        raw_sig = base64.b64decode(signature.encode("utf-8"))
        public_key.verify(
            raw_sig,
            block_hash.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False
