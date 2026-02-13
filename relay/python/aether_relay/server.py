"""Relay server entrypoint."""

from __future__ import annotations

import argparse
import asyncio
import signal
from pathlib import Path

from .core import RelayCore, RelayConfig
from .gossip import GossipConfig, GossipMesh
from .gateways import HttpGateway, serve_nostr
from .limits import RateLimiter
from .storage import InMemoryEventStore, RocksDBEventStore, SQLiteEventStore
from .quic_transport import serve_quic
from .websocket_transport import serve_websocket


def _find_project_root() -> Path:
    """Find the project root by looking for AETHER.md or PRD.md (project root markers)."""
    current = Path(__file__).resolve().parent
    # Go up from aether_relay/ to relay/python/ to project root
    while current.parent != current:
        # Look for project root markers (AETHER.md or PRD.md) which are only in project root
        if (current / "AETHER.md").exists() or (current / "PRD.md").exists():
            return current
        # Also check for certs/ directory as a marker
        if (current / "certs").exists() and (current / "README.md").exists():
            return current
        current = current.parent
    # Fallback: go up from relay/python/aether_relay to project root (3 levels up)
    return Path(__file__).resolve().parent.parent.parent.parent


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

    # Resolve storage path relative to project root if relative
    storage_path = args.storage_path
    if not Path(storage_path).is_absolute():
        project_root = _find_project_root()
        storage_path = str(project_root / storage_path)

    store = _build_store(
        args.storage,
        storage_path,
        retention_ns=args.retention_ns,
    )

    core = RelayCore(
        store,
        config=RelayConfig(
            max_size=args.max_size,
            pow_difficulty=args.pow_difficulty,
            rate_limiter=limiter,
            gossip_publish=gossip_mesh.publish if gossip_mesh else None,
        ),
    )

    if gossip_mesh:
        await gossip_mesh.start(lambda data: core.publish("gossip", _decode_gossip(data), _noop_send))

    quic_server = None
    if Path(args.quic_cert).exists() and Path(args.quic_key).exists():
        quic_server = await serve_quic(
            host=args.quic_host,
            port=args.quic_port,
            cert_path=args.quic_cert,
            key_path=args.quic_key,
            core=core,
        )
    else:
        print(f"Warning: QUIC certificates not found ({args.quic_cert}, {args.quic_key}), skipping QUIC server")

    ws_server = await serve_websocket(host=args.ws_host, port=args.ws_port, core=core)
    nostr_server = None
    http_server = None
    http_ws_server = None
    gateways = {item.strip() for item in args.gateway.split(",") if item.strip()}
    if "nostr" in gateways:
        nostr_server = await serve_nostr(host=args.ws_host, port=args.nostr_port, core=core)
    if "http" in gateways:
        http_gateway = HttpGateway(core)
        http_server, http_ws_server = await http_gateway.start(
            host=args.ws_host,
            http_port=args.http_port,
            ws_port=args.http_ws_port,
        )

    stop = asyncio.Event()

    def _handle_stop(*_: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_stop)

    await stop.wait()
    ws_server.close()
    await ws_server.wait_closed()
    if nostr_server:
        nostr_server.close()
        await nostr_server.wait_closed()
    if http_ws_server:
        http_ws_server.close()
        await http_ws_server.wait_closed()
    if http_server:
        http_server.close()
        await http_server.wait_closed()
    if quic_server:
        quic_server.close()
        if hasattr(quic_server, "wait_closed"):
            await quic_server.wait_closed()


def main() -> None:
    project_root = _find_project_root()
    parser = argparse.ArgumentParser(description="Aether relay server")
    parser.add_argument("--quic-host", default="0.0.0.0")
    parser.add_argument("--quic-port", type=int, default=4433)
    parser.add_argument(
        "--quic-cert",
        type=str,
        default=str(project_root / "certs" / "localhost.pem"),
    )
    parser.add_argument(
        "--quic-key",
        type=str,
        default=str(project_root / "certs" / "localhost-key.pem"),
    )
    parser.add_argument("--ws-host", default="0.0.0.0")
    parser.add_argument("--ws-port", type=int, default=8080)
    parser.add_argument("--retention-ns", type=int, default=None)
    parser.add_argument("--max-size", type=int, default=None)
    parser.add_argument("--pow-difficulty", type=int, default=None)
    parser.add_argument("--rate-limit-capacity", type=int, default=None)
    parser.add_argument("--rate-limit-per-sec", type=float, default=None)
    parser.add_argument("--storage", choices=("sqlite", "memory", "rocksdb"), default="sqlite")
    parser.add_argument(
        "--storage-path",
        type=str,
        default=str(project_root / "data" / "relay.db"),
    )

    parser.add_argument("--gossip-topic", type=str, default=None)
    parser.add_argument("--gossip-peer", action="append", dest="gossip_peers")
    parser.add_argument("--gateway", type=str, default="none")
    parser.add_argument("--nostr-port", type=int, default=7447)
    parser.add_argument("--http-port", type=int, default=8081)
    parser.add_argument("--http-ws-port", type=int, default=8082)

    args = parser.parse_args()
    asyncio.run(_run(args))


async def _noop_send(_conn_id: str, _message: dict[str, object]) -> None:
    return None


def _decode_gossip(data: bytes) -> dict[str, object]:
    import json

    return json.loads(data.decode("utf-8"))


def _build_store(storage: str, storage_path: str, *, retention_ns: int | None) -> object:
    if storage == "memory":
        return InMemoryEventStore(retention_ns=retention_ns)
    if storage == "rocksdb":
        return RocksDBEventStore(path=storage_path, retention_ns=retention_ns)
    return SQLiteEventStore(path=storage_path, retention_ns=retention_ns)


if __name__ == "__main__":
    main()
