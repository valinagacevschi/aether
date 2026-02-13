from __future__ import annotations

import pytest

from aether_relay.limits import RateLimiter, compute_event_size, enforce_max_size


def _event(*, content: bytes) -> dict[str, object]:
    return {
        "event_id": b"\x00" * 32,
        "pubkey": b"\x01" * 32,
        "kind": 1,
        "created_at": 10,
        "tags": [],
        "content": content,
        "sig": b"\x02" * 64,
    }


def test_rate_limiter_allows_until_capacity() -> None:
    limiter = RateLimiter(capacity=2, refill_per_second=0.0, now_ns=lambda: 0)
    pubkey = b"\x03" * 32
    assert limiter.allow(pubkey) is True
    assert limiter.allow(pubkey) is True
    assert limiter.allow(pubkey) is False


def test_compute_event_size_and_max_size() -> None:
    event = _event(content=b"hello")
    size = compute_event_size(event)
    assert size > 0
    enforce_max_size(event, max_bytes=size)
    with pytest.raises(ValueError, match="maximum size"):
        enforce_max_size(event, max_bytes=size - 1)
