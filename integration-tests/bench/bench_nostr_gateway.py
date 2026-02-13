from __future__ import annotations

import argparse
import asyncio
import json
import time
import sys
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python"))

from aether.crypto import compute_event_id, generate_keypair, sign


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:7447")
    parser.add_argument("--count", type=int, default=100)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    private_key, pubkey = generate_keypair()
    latencies: list[float] = []
    async with websockets.connect(args.url) as ws:
        await ws.send(json.dumps(["REQ", "bench", {"kinds": [1]}]))
        await ws.recv()
        for idx in range(args.count):
            event_id = compute_event_id(pubkey=pubkey, created_at=idx + 1, kind=1, tags=[], content=b"bench")
            event = {
                "id": event_id.hex(),
                "pubkey": pubkey.hex(),
                "kind": 1,
                "created_at": idx + 1,
                "tags": [],
                "content": "bench",
                "sig": sign(event_id, private_key).hex(),
            }
            start = time.perf_counter()
            await ws.send(json.dumps(["EVENT", event]))
            await ws.recv()  # OK
            await ws.recv()  # EVENT
            latencies.append(time.perf_counter() - start)

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    p99 = latencies[int(len(latencies) * 0.99) - 1]
    total = sum(latencies)
    print(
        f"nostr events={args.count} total={total:.3f}s ev/s={args.count/total:.1f} "
        f"p50={p50*1000:.2f}ms p95={p95*1000:.2f}ms p99={p99*1000:.2f}ms"
    )


if __name__ == "__main__":
    asyncio.run(main())
