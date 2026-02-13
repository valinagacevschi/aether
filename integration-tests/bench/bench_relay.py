import argparse
import asyncio
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python"))

from aether import Client
from aether.crypto import compute_event_id, generate_keypair, sign


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:9000")
    parser.add_argument("--count", type=int, default=100)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    client = Client()
    await client.connect([args.url])

    private_key, pubkey = generate_keypair()
    latencies = []
    for idx in range(args.count):
        created_at = idx + 1
        content = f"bench-{idx}".encode("utf-8")
        event_id = compute_event_id(
            pubkey=pubkey,
            created_at=created_at,
            kind=1,
            tags=[],
            content=content,
        )
        sig = sign(event_id, private_key)
        event = {
            "event_id": event_id,
            "pubkey": pubkey,
            "kind": 1,
            "created_at": created_at,
            "tags": [],
            "content": content.decode("utf-8"),
            "sig": sig,
        }
        start = time.perf_counter()
        await client.publish(event)
        latencies.append(time.perf_counter() - start)

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    p99 = latencies[int(len(latencies) * 0.99) - 1]
    print(f"published {args.count} events")
    print(f"p50={p50 * 1000:.2f}ms p95={p95 * 1000:.2f}ms p99={p99 * 1000:.2f}ms")


if __name__ == "__main__":
    asyncio.run(main())
