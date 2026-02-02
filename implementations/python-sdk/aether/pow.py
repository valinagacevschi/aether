"""Proof-of-work helpers for Aether events."""

from __future__ import annotations

from blake3 import blake3


def leading_zero_bits(data: bytes) -> int:
    count = 0
    for byte in data:
        if byte == 0:
            count += 8
            continue
        for bit in range(7, -1, -1):
            if byte & (1 << bit):
                return count
            count += 1
    return count


def meets_difficulty(event_id: bytes, difficulty: int) -> bool:
    if difficulty <= 0:
        return True
    return leading_zero_bits(event_id) >= difficulty


def compute_pow_nonce(
    *,
    pubkey: bytes,
    created_at: int,
    kind: int,
    tags: bytes,
    content: bytes,
    difficulty: int,
) -> tuple[int, bytes]:
    nonce = 0
    while True:
        payload = pubkey + created_at.to_bytes(8, "big") + kind.to_bytes(2, "big") + tags + content + nonce.to_bytes(8, "big")
        event_id = blake3(payload).digest()
        if meets_difficulty(event_id, difficulty):
            return nonce, event_id
        nonce += 1
