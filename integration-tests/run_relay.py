import argparse
import asyncio
import signal
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "relay" / "python"))

from aether_relay.core import RelayCore, RelayConfig
from aether_relay.storage import InMemoryEventStore
from aether_relay.websocket_transport import serve_websocket


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run relay for integration tests")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    core = RelayCore(InMemoryEventStore(), config=RelayConfig())
    server = await serve_websocket(host=args.host, port=args.port, core=core)

    stop = asyncio.Event()

    def handle_stop(*_args: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_stop)

    await stop.wait()
    server.close()
    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
