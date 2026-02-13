import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python"))

from aether import Client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:9000")
    parser.add_argument("--kind", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=5.0)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    client = Client()
    await client.connect([args.url])

    received = asyncio.Event()

    def on_event(_event: dict) -> None:
        received.set()

    client.on_event(on_event)
    await client.subscribe("sub-1", {"kinds": [args.kind]})

    try:
        await asyncio.wait_for(received.wait(), timeout=args.timeout)
    except asyncio.TimeoutError:
        raise SystemExit("timed out waiting for event")


if __name__ == "__main__":
    asyncio.run(main())
