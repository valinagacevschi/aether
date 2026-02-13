from __future__ import annotations

import asyncio
import http.client
import json
import socket

import websockets

from aether_relay.core import RelayConfig, RelayCore
from aether_relay.gateways.http import HttpGateway
from aether_relay.gateways.nostr_ws import serve_nostr
from aether_relay.storage import InMemoryEventStore


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_nostr_invalid_message_notice() -> None:
    async def run() -> None:
        core = RelayCore(InMemoryEventStore(), config=RelayConfig(now_ns=lambda: 1))
        port = _free_port()
        server = await serve_nostr(host="127.0.0.1", port=port, core=core)
        try:
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                await ws.send(json.dumps({"bad": "shape"}))
                notice = json.loads(await ws.recv())
                assert notice[0] == "NOTICE"
                assert "invalid_message" in notice[1]
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())


def test_http_missing_subscription_error() -> None:
    async def run() -> None:
        core = RelayCore(InMemoryEventStore(), config=RelayConfig(now_ns=lambda: 1))
        gateway = HttpGateway(core)
        http_port = _free_port()
        ws_port = _free_port()
        http_server, ws_server = await gateway.start(host="127.0.0.1", http_port=http_port, ws_port=ws_port)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", http_port, timeout=5)
            conn.request("DELETE", "/v1/subscriptions/missing")
            resp = conn.getresponse()
            payload = json.loads(resp.read().decode("utf-8"))
            assert resp.status == 404
            assert payload["error"] == "subscription_not_found"
            conn.close()
        finally:
            ws_server.close()
            await ws_server.wait_closed()
            http_server.close()
            await http_server.wait_closed()

    asyncio.run(run())
