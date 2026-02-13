from __future__ import annotations

import asyncio

from aether_relay.core import RelayCore, RelayConfig
from aether_relay.crypto import compute_event_id, generate_keypair, sign
from aether_relay.limits import RateLimiter
from aether_relay.storage import InMemoryEventStore


def _event(*, pubkey: bytes, kind: int, created_at: int, private_key: bytes) -> dict[str, object]:
    event_id = compute_event_id(
        pubkey=pubkey,
        created_at=created_at,
        kind=kind,
        tags=[],
        content=b"",
    )
    return {
        "event_id": event_id,
        "pubkey": pubkey,
        "kind": kind,
        "created_at": created_at,
        "tags": [],
        "content": "",
        "sig": sign(event_id, private_key),
    }


def test_publish_routes_to_subscribers() -> None:
    store = InMemoryEventStore()
    core = RelayCore(store, config=RelayConfig(now_ns=lambda: 1))
    core.subscribe("conn-1", "sub-1", [{"kinds": [1]}])
    private_key, pubkey = generate_keypair()
    event = _event(pubkey=pubkey, kind=1, created_at=1, private_key=private_key)
    sent: list[dict[str, object]] = []

    async def send(conn_id: str, message: dict[str, object]) -> None:
        sent.append({"conn_id": conn_id, "message": message})

    asyncio.run(core.publish("conn-1", event, send))
    assert sent
    assert sent[0]["message"]["type"] == "event"


def test_publish_applies_rate_limit() -> None:
    store = InMemoryEventStore()
    limiter = RateLimiter(capacity=0, refill_per_second=0.0, now_ns=lambda: 0)
    core = RelayCore(store, config=RelayConfig(rate_limiter=limiter, now_ns=lambda: 1))
    private_key, pubkey = generate_keypair()
    event = _event(pubkey=pubkey, kind=1, created_at=1, private_key=private_key)

    async def send(_conn_id: str, _message: dict[str, object]) -> None:
        return None

    try:
        asyncio.run(core.publish("conn-1", event, send))
    except ValueError as exc:
        assert "rate limit" in str(exc)
    else:
        raise AssertionError("expected rate limit error")


def test_publish_forwards_to_gossip() -> None:
    store = InMemoryEventStore()
    forwarded: list[bytes] = []

    async def publish(data: bytes) -> None:
        forwarded.append(data)

    core = RelayCore(store, config=RelayConfig(now_ns=lambda: 1, gossip_publish=publish))
    private_key, pubkey = generate_keypair()
    event = _event(pubkey=pubkey, kind=1, created_at=1, private_key=private_key)

    async def send(_conn_id: str, _message: dict[str, object]) -> None:
        return None

    asyncio.run(core.publish("conn-1", event, send))
    assert forwarded
