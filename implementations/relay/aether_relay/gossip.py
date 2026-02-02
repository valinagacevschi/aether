"""Gossipsub mesh integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Iterable, Protocol


class GossipBackend(Protocol):
    async def create_host(self) -> object: ...
    async def create_pubsub(self, host: object) -> object: ...
    async def subscribe(self, pubsub: object, topic: str, handler: Callable[[bytes], Awaitable[None]]) -> None: ...
    async def publish(self, pubsub: object, topic: str, data: bytes) -> None: ...
    async def dial(self, host: object, address: str) -> None: ...


@dataclass
class GossipConfig:
    topic: str
    peers: list[str]


class GossipMesh:
    def __init__(self, *, config: GossipConfig, backend: GossipBackend | None = None) -> None:
        self._config = config
        self._backend = backend or Libp2pBackend()
        self._host: object | None = None
        self._pubsub: object | None = None

    async def start(self, handler: Callable[[bytes], Awaitable[None]]) -> None:
        self._host = await self._backend.create_host()
        self._pubsub = await self._backend.create_pubsub(self._host)
        await self._backend.subscribe(self._pubsub, self._config.topic, handler)
        for peer in self._config.peers:
            await self._backend.dial(self._host, peer)

    async def publish(self, data: bytes) -> None:
        if not self._pubsub:
            raise RuntimeError("gossipsub not started")
        await self._backend.publish(self._pubsub, self._config.topic, data)


class Libp2pBackend:
    async def create_host(self) -> object:
        libp2p = _require_libp2p()
        if not hasattr(libp2p, "new_host"):
            raise RuntimeError("libp2p new_host API not available")
        return await libp2p.new_host()

    async def create_pubsub(self, host: object) -> object:
        libp2p_pubsub = _require_libp2p_pubsub()
        if not hasattr(libp2p_pubsub, "new_pubsub"):
            raise RuntimeError("libp2p pubsub API not available")
        return await libp2p_pubsub.new_pubsub(host)

    async def subscribe(
        self,
        pubsub: object,
        topic: str,
        handler: Callable[[bytes], Awaitable[None]],
    ) -> None:
        await pubsub.subscribe(topic, handler)

    async def publish(self, pubsub: object, topic: str, data: bytes) -> None:
        await pubsub.publish(topic, data)

    async def dial(self, host: object, address: str) -> None:
        await host.connect(address)


def _require_libp2p() -> object:
    import importlib

    try:
        return importlib.import_module("libp2p")
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("py-libp2p is not available") from exc


def _require_libp2p_pubsub() -> object:
    import importlib

    try:
        return importlib.import_module("libp2p.pubsub")
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("py-libp2p pubsub is not available") from exc
