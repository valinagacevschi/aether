"""Client stubs for the Aether Python SDK."""

from __future__ import annotations

from typing import Any


class Client:
    """Aether client stub with async I/O signatures."""

    async def connect(self, url: str) -> None:
        """Connect to a relay endpoint."""
        raise NotImplementedError("connect is not implemented")

    async def publish(self, event: dict[str, Any]) -> None:
        """Publish an event to the relay."""
        raise NotImplementedError("publish is not implemented")
