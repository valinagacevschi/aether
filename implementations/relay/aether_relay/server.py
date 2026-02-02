"""Relay server entrypoint."""

from __future__ import annotations

import argparse
import asyncio
import signal
from pathlib import Path

from .core import RelayCore, RelayConfig
from .gossip import GossipConfig, GossipMesh
from .limits import RateLimiter
from .storage import InMemoryEventStore
from .quic_transport import serve_quic
from .websocket_transport import serve_websocket


async def _run(args: argparse.Namespace) -> None:
    limiter = None
    if args.rate_limit_capacity is not None and args.rate_limit_per_sec is not None:
        limiter = RateLimiter(
            capacity=args.rate_limit_capacity,
            refill_per_second=args.rate_limit_per_sec,
        )
    gossip_mesh = None
    if args.gossip_topic:
        gossip_mesh = GossipMesh(
            config=GossipConfig(topic=args.gossip_topic, peers=args.gossip_peers or []),
        )

    core = RelayCore(
        InMemoryEventStore(retention_ns=args.retention_ns),
        config=RelayConfig(
            max_size=args.max_size,
            pow_difficulty=args.pow_difficulty,
            rate_limiter=limiter,
            gossip_publish=gossip_mesh.publish if gossip_mesh else None,
        ),
    )

    if gossip_mesh:
        await gossip_mesh.start(lambda data: core.publish("gossip", _decode_gossip(data), _noop_send))

    quic_server = await serve_quic(
        host=args.quic_host,
        port=args.quic_port,
        cert_path=args.quic_cert,
        key_path=args.quic_key,
        core=core,
    )
    ws_server = await serve_websocket(host=args.ws_host, port=args.ws_port, core=core)

    stop = asyncio.Event()

    def _handle_stop(*_: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_stop)

    await stop.wait()
    ws_server.close()
    await ws_server.wait_closed()
    quic_server.close()
    await quic_server.wait_closed()


def main() -> None:
    parser = argparse.ArgumentParser(description="Aether relay server")
    parser.add_argument("--quic-host", default="0.0.0.0")
    parser.add_argument("--quic-port", type=int, default=4433)
    parser.add_argument("--quic-cert", type=str, default=str(Path("certs/localhost.pem")))
    parser.add_argument("--quic-key", type=str, default=str(Path("certs/localhost-key.pem")))
    parser.add_argument("--ws-host", default="0.0.0.0")
    parser.add_argument("--ws-port", type=int, default=8080)
    parser.add_argument("--retention-ns", type=int, default=None)
    parser.add_argument("--max-size", type=int, default=None)
    parser.add_argument("--pow-difficulty", type=int, default=None)
    parser.add_argument("--rate-limit-capacity", type=int, default=None)
    parser.add_argument("--rate-limit-per-sec", type=float, default=None)

    parser.add_argument("--gossip-topic", type=str, default=None)
    parser.add_argument("--gossip-peer", action="append", dest="gossip_peers")

    args = parser.parse_args()
    asyncio.run(_run(args))


async def _noop_send(_conn_id: str, _message: dict[str, object]) -> None:
    return None


def _decode_gossip(data: bytes) -> dict[str, object]:
    import json

    return json.loads(data.decode("utf-8"))


if __name__ == "__main__":
    main()
