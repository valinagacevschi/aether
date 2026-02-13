from __future__ import annotations

import asyncio
import json
import socket

import websockets

from aether_relay.core import RelayConfig, RelayCore
from aether_relay.crypto import compute_event_id, generate_keypair, sign
from aether_relay.gateways.nostr_ws import serve_nostr
from aether_relay.storage import InMemoryEventStore


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _event(*, private_key: bytes, pubkey: bytes, kind: int = 1) -> dict[str, object]:
    event_id = compute_event_id(pubkey=pubkey, created_at=1, kind=kind, tags=[], content=b"hello")
    return {
        "id": event_id.hex(),
        "pubkey": pubkey.hex(),
        "kind": kind,
        "created_at": 1,
        "tags": [],
        "content": "hello",
        "sig": sign(event_id, private_key).hex(),
    }


def test_nostr_event_flow() -> None:
    async def run() -> None:
        core = RelayCore(InMemoryEventStore(), config=RelayConfig(now_ns=lambda: 1))
        port = _free_port()
        server = await serve_nostr(host="127.0.0.1", port=port, core=core)
        try:
            private_key, pubkey = generate_keypair()
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                await ws.send(json.dumps(["REQ", "sub-1", {"kinds": [1]}]))
                eose = json.loads(await ws.recv())
                assert eose[0] == "EOSE"

                await ws.send(json.dumps(["EVENT", _event(private_key=private_key, pubkey=pubkey)]))
                ok = json.loads(await ws.recv())
                assert ok[0] == "OK"
                assert ok[2] is True

                evt = json.loads(await ws.recv())
                assert evt[0] == "EVENT"
                assert evt[1] == "sub-1"
                assert evt[2]["content"] == "hello"
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())
