from __future__ import annotations

import asyncio

from aether_relay.core import RelayCore, RelayConfig
from aether_relay.crypto import compute_event_id, generate_keypair, sign
from aether_relay.handlers import handle_message
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


def test_handle_subscribe_and_publish() -> None:
    store = InMemoryEventStore()
    core = RelayCore(store, config=RelayConfig(now_ns=lambda: 1))
    private_key, pubkey = generate_keypair()
    event = _event(pubkey=pubkey, kind=1, created_at=1, private_key=private_key)
    sent: list[dict[str, object]] = []

    async def send(conn_id: str, message: dict[str, object]) -> None:
        sent.append({"conn": conn_id, "message": message})

    async def run() -> None:
        await handle_message(
            core,
            "conn-1",
            {"type": "subscribe", "sub_id": "sub-1", "filters": [{"kinds": [1]}]},
            send,
        )
        await handle_message(
            core,
            "conn-1",
            {"type": "publish", "event": event},
            send,
        )

    asyncio.run(run())
    assert any(item["message"]["type"] == "event" for item in sent)
