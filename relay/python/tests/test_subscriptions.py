from __future__ import annotations

import asyncio

from aether_relay.filters import normalize_filter
from aether_relay.subscriptions import SubscriptionManager


def _event(*, kind: int, pubkey: bytes, created_at: int, tags: list[list[str]] | None = None) -> dict[str, object]:
    return {
        "event_id": b"\x00" * 32,
        "pubkey": pubkey,
        "kind": kind,
        "created_at": created_at,
        "tags": tags or [],
        "content": "",
        "sig": b"\x00" * 64,
    }


def test_add_and_remove_subscriptions() -> None:
    manager = SubscriptionManager()
    flt = normalize_filter({"kinds": [1]})
    manager.add("conn-1", "sub-1", [flt])
    assert manager.matches(_event(kind=1, pubkey=b"\x01" * 32, created_at=1))

    manager.remove("conn-1", "sub-1")
    assert manager.matches(_event(kind=1, pubkey=b"\x01" * 32, created_at=1)) == []


def test_dispatch_uses_asyncio_tasks() -> None:
    manager = SubscriptionManager()
    flt = normalize_filter({"kinds": [1]})
    manager.add("conn-1", "sub-1", [flt])
    event = _event(kind=1, pubkey=b"\x01" * 32, created_at=1)
    sent: list[tuple[str, str]] = []

    async def send(conn_id: str, sub_id: str, _event: dict[str, object]) -> None:
        sent.append((conn_id, sub_id))

    async def run() -> None:
        tasks = manager.dispatch(event, send)
        assert tasks
        await asyncio.gather(*tasks)

    asyncio.run(run())
    assert sent == [("conn-1", "sub-1")]
