"""Minimal HTTP gateway publish + SSE stream check."""

from __future__ import annotations

import asyncio
import http.client
import json

from aether.crypto import compute_event_id, generate_keypair, sign


def post_subscription() -> str:
    conn = http.client.HTTPConnection("127.0.0.1", 8081, timeout=5)
    conn.request(
        "POST",
        "/v1/subscriptions",
        body=json.dumps({"filters": {"kinds": [1]}}),
        headers={"Content-Type": "application/json"},
    )
    resp = conn.getresponse()
    payload = json.loads(resp.read().decode("utf-8"))
    conn.close()
    return str(payload["subscription_id"])


def post_event() -> None:
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
    conn = http.client.HTTPConnection("127.0.0.1", 8081, timeout=5)
    conn.request("POST", "/v1/events", body=json.dumps({"event": event}), headers={"Content-Type": "application/json"})
    print("POST /v1/events ->", conn.getresponse().read().decode("utf-8"))
    conn.close()


async def read_sse(sub_id: str) -> None:
    reader, writer = await asyncio.open_connection("127.0.0.1", 8081)
    writer.write(
        (
            f"GET /v1/stream?subscription_id={sub_id} HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\n"
            "Accept: text/event-stream\r\n"
            "Connection: keep-alive\r\n\r\n"
        ).encode("utf-8")
    )
    await writer.drain()
    post_event()
    print("SSE ->", (await reader.readuntil(b"\n\n")).decode("utf-8"))
    writer.close()
    await writer.wait_closed()


async def main() -> None:
    sub_id = post_subscription()
    await read_sse(sub_id)


if __name__ == "__main__":
    asyncio.run(main())
