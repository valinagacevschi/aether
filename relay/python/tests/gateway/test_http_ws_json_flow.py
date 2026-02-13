from __future__ import annotations

import asyncio
import json
import socket

import websockets

from aether_relay.core import RelayConfig, RelayCore
from aether_relay.crypto import compute_event_id, generate_keypair, sign
from aether_relay.gateways.http import HttpGateway
from aether_relay.storage import InMemoryEventStore


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_http_ws_json_flow() -> None:
    async def run() -> None:
        core = RelayCore(InMemoryEventStore(), config=RelayConfig(now_ns=lambda: 1))
        gateway = HttpGateway(core)
        http_port = _free_port()
        ws_port = _free_port()
        http_server, ws_server = await gateway.start(host="127.0.0.1", http_port=http_port, ws_port=ws_port)
        try:
            private_key, pubkey = generate_keypair()
            event_id = compute_event_id(pubkey=pubkey, created_at=1, kind=1, tags=[], content=b"hello")
            event = {
                "event_id": event_id.hex(),
                "pubkey": pubkey.hex(),
                "kind": 1,
                "created_at": 1,
                "tags": [],
                "content": "hello",
                "sig": sign(event_id, private_key).hex(),
            }
            async with websockets.connect(f"ws://127.0.0.1:{ws_port}/v1/ws") as ws:
                await ws.send(json.dumps({"type": "subscribe", "sub_id": "sub-1", "filters": [{"kinds": [1]}]}))
                await ws.recv()  # subscribed
                await ws.send(json.dumps({"type": "publish", "event": event}))
                await ws.recv()  # ack
                evt = json.loads(await ws.recv())
                assert evt["type"] == "event"
                assert evt["sub_id"] == "sub-1"
                assert evt["event"]["content"] == "hello"
        finally:
            ws_server.close()
            await ws_server.wait_closed()
            http_server.close()
            await http_server.wait_closed()

    asyncio.run(run())
