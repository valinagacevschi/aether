import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python"))

from aether import Client
from aether.crypto import compute_event_id, generate_keypair, sign


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:9000")
    parser.add_argument("--kind", type=int, default=1)
    parser.add_argument("--content", default="hello")
    parser.add_argument("--created-at", type=int, default=1)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    client = Client()
    await client.connect([args.url])

    private_key, pubkey = generate_keypair()
    content = args.content.encode("utf-8")
    event_id = compute_event_id(
        pubkey=pubkey,
        created_at=args.created_at,
        kind=args.kind,
        tags=[],
        content=content,
    )
    sig = sign(event_id, private_key)
    event = {
        "event_id": event_id,
        "pubkey": pubkey,
        "kind": args.kind,
        "created_at": args.created_at,
        "tags": [],
        "content": content.decode("utf-8"),
        "sig": sig,
    }
    await client.publish(event)


if __name__ == "__main__":
    asyncio.run(main())
