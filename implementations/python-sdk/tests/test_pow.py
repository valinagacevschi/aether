from __future__ import annotations

from aether.pow import compute_pow_nonce, meets_difficulty


def test_compute_pow_nonce_meets_difficulty() -> None:
    pubkey = b"\x01" * 32
    tags = b"\x00\x00"
    nonce, event_id = compute_pow_nonce(
        pubkey=pubkey,
        created_at=1,
        kind=1,
        tags=tags,
        content=b"",
        difficulty=4,
    )
    assert nonce >= 0
    assert meets_difficulty(event_id, 4)
