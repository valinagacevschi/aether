from __future__ import annotations

import asyncio

from aether_relay.gossip import GossipConfig, GossipMesh


class FakeBackend:
    def __init__(self) -> None:
        self.started = False
        self.published: list[bytes] = []
        self.dials: list[str] = []

    async def create_host(self) -> object:
        return object()

    async def create_pubsub(self, _host: object) -> object:
        return object()

    async def subscribe(self, _pubsub: object, _topic: str, _handler) -> None:
        self.started = True

    async def publish(self, _pubsub: object, _topic: str, data: bytes) -> None:
        self.published.append(data)

    async def dial(self, _host: object, address: str) -> None:
        self.dials.append(address)


def test_gossip_mesh_start_and_publish() -> None:
    backend = FakeBackend()
    mesh = GossipMesh(config=GossipConfig(topic="aether", peers=["peer1", "peer2"]), backend=backend)

    async def run() -> None:
        await mesh.start(lambda _data: asyncio.sleep(0))
        await mesh.publish(b"hello")

    asyncio.run(run())
    assert backend.started is True
    assert backend.published == [b"hello"]
    assert backend.dials == ["peer1", "peer2"]
