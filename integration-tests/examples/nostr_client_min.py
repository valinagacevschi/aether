"""Minimal NOSTR gateway publish + subscribe check."""

from __future__ import annotations

import asyncio
import json

import websockets

from aether.crypto import compute_event_id, generate_keypair, sign


async def main() -> None:
    private_key, pubkey = generate_keypair()
    event_id = compute_event_id(pubkey=pubkey, created_at=1, kind=1, tags=[], content=b"hello")
    event = {
        "id": event_id.hex(),
        "pubkey": pubkey.hex(),
        "kind": 1,
        "created_at": 1,
        "tags": [],
        "content": "hello",
        "sig": sign(event_id, private_key).hex(),
    }

    async with websockets.connect("ws://127.0.0.1:7447") as ws:
        await ws.send(json.dumps(["REQ", "sub-1", {"kinds": [1]}]))
        print("REQ ->", await ws.recv())

        await ws.send(json.dumps(["EVENT", event]))
        print("OK ->", await ws.recv())
        print("EVENT ->", await ws.recv())


if __name__ == "__main__":
    asyncio.run(main())
