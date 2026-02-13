"""Minimal Noise-like upgrade using X25519 + HKDF + ChaCha20-Poly1305.

NOTE: This is a lightweight, interoperable encryption layer and not a
full Noise XX implementation. It is intended to provide confidentiality
with a clear upgrade path to a full Noise framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)


def generate_keypair() -> tuple[bytes, bytes]:
    private_key = X25519PrivateKey.generate()
    public_key = private_key.public_key()
    return (
        private_key.private_bytes_raw(),
        public_key.public_bytes_raw(),
    )


def derive_shared_key(private_key: bytes, peer_public_key: bytes) -> bytes:
    priv = X25519PrivateKey.from_private_bytes(private_key)
    pub = X25519PublicKey.from_public_bytes(peer_public_key)
    shared = priv.exchange(pub)
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"aether-noise",
    )
    return hkdf.derive(shared)


@dataclass
class NoiseSession:
    key: bytes
    send_counter: int = 0

    def encrypt(self, plaintext: bytes) -> bytes:
        nonce = self._nonce(self.send_counter)
        self.send_counter += 1
        cipher = ChaCha20Poly1305(self.key)
        ciphertext = cipher.encrypt(nonce, plaintext, None)
        return self._counter_prefix(self.send_counter - 1) + ciphertext

    def decrypt(self, payload: bytes) -> bytes:
        if len(payload) < 8:
            raise ValueError("noise payload too short")
        counter = int.from_bytes(payload[:8], "big")
        nonce = self._nonce(counter)
        cipher = ChaCha20Poly1305(self.key)
        return cipher.decrypt(nonce, payload[8:], None)

    @staticmethod
    def _nonce(counter: int) -> bytes:
        return b"\x00\x00\x00\x00" + counter.to_bytes(8, "big")

    @staticmethod
    def _counter_prefix(counter: int) -> bytes:
        return counter.to_bytes(8, "big")

