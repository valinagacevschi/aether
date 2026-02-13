from __future__ import annotations

import asyncio
import http.client
import json
import socket

from aether_relay.core import RelayConfig, RelayCore
from aether_relay.crypto import compute_event_id, generate_keypair, sign
from aether_relay.gateways.http import HttpGateway
from aether_relay.storage import InMemoryEventStore


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _event(*, private_key: bytes, pubkey: bytes, kind: int = 1) -> dict[str, object]:
    event_id = compute_event_id(pubkey=pubkey, created_at=1, kind=kind, tags=[], content=b"hello")
    return {
        "event_id": event_id.hex(),
        "pubkey": pubkey.hex(),
        "kind": kind,
        "created_at": 1,
        "tags": [],
        "content": "hello",
        "sig": sign(event_id, private_key).hex(),
    }


def test_http_publish_stream_flow() -> None:
    async def run() -> None:
        core = RelayCore(InMemoryEventStore(), config=RelayConfig(now_ns=lambda: 1))
        gateway = HttpGateway(core)
        http_port = _free_port()
        ws_port = _free_port()
        http_server, ws_server = await gateway.start(host="127.0.0.1", http_port=http_port, ws_port=ws_port)

        try:
            private_key, pubkey = generate_keypair()
            conn = http.client.HTTPConnection("127.0.0.1", http_port, timeout=5)
            conn.request(
                "POST",
                "/v1/subscriptions",
                body=json.dumps({"filters": {"kinds": [1]}}),
                headers={"Content-Type": "application/json"},
            )
            resp = conn.getresponse()
            sub_payload = json.loads(resp.read().decode("utf-8"))
            assert resp.status == 200
            sub_id = sub_payload["subscription_id"]
            conn.close()

            reader, writer = await asyncio.open_connection("127.0.0.1", http_port)
            writer.write(
                (
                    f"GET /v1/stream?subscription_id={sub_id} HTTP/1.1\r\n"
                    "Host: 127.0.0.1\r\n"
                    "Accept: text/event-stream\r\n"
                    "Connection: keep-alive\r\n\r\n"
                ).encode("utf-8")
            )
            await writer.drain()

            conn = http.client.HTTPConnection("127.0.0.1", http_port, timeout=5)
            conn.request(
                "POST",
                "/v1/events",
                body=json.dumps({"event": _event(private_key=private_key, pubkey=pubkey)}),
                headers={"Content-Type": "application/json"},
            )
            publish_resp = conn.getresponse()
            publish_payload = json.loads(publish_resp.read().decode("utf-8"))
            assert publish_resp.status == 200
            assert publish_payload["accepted"] is True
            conn.close()

            data = await asyncio.wait_for(reader.readuntil(b"\n\n"), timeout=5)
            assert b"event: event" in data
            assert b"\"content\":\"hello\"" in data
            writer.close()
            await writer.wait_closed()
        finally:
            ws_server.close()
            await ws_server.wait_closed()
            http_server.close()
            await http_server.wait_closed()

    asyncio.run(run())
