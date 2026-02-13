"""Core relay logic: validation, storage, subscriptions, and routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Mapping

from .limits import RateLimiter
from .subscriptions import SubscriptionManager
from .validation import validate_event

SendFn = Callable[[str, Mapping[str, object]], Awaitable[None]]
GossipFn = Callable[[bytes], Awaitable[None]]


@dataclass
class RelayConfig:
    max_size: int | None = None
    pow_difficulty: int | None = None
    rate_limiter: RateLimiter | None = None
    now_ns: Callable[[], int] | None = None
    gossip_publish: GossipFn | None = None


class RelayCore:
    def __init__(self, store: object, *, config: RelayConfig | None = None) -> None:
        self._store = store
        self._config = config or RelayConfig()
        self._subscriptions = SubscriptionManager()

    def subscribe(self, connection_id: str, subscription_id: str, filters: list[object]) -> None:
        from .filters import normalize_filter

        normalized = [normalize_filter(raw) for raw in filters]
        self._subscriptions.add(connection_id, subscription_id, normalized)

    def unsubscribe(self, connection_id: str, subscription_id: str) -> None:
        self._subscriptions.remove(connection_id, subscription_id)

    def clear(self, connection_id: str) -> None:
        self._subscriptions.clear(connection_id)

    async def publish(self, connection_id: str, event: Mapping[str, object], send: SendFn) -> None:
        validate_event(
            event,
            rate_limiter=self._config.rate_limiter,
            max_size=self._config.max_size,
            pow_difficulty=self._config.pow_difficulty,
            now_ns=self._config.now_ns() if self._config.now_ns else None,
        )

        stored = getattr(self._store, "insert")(event)
        if stored is not False:
            tasks = self._subscriptions.dispatch(
                event,
                lambda conn_id, sub_id, evt: send(conn_id, {"type": "event", "sub_id": sub_id, "event": evt}),
            )
            if tasks:
                await _gather_tasks(tasks)
        if self._config.gossip_publish is not None and connection_id != "gossip":
            await self._config.gossip_publish(_serialize_event(event))


async def _gather_tasks(tasks: list[object]) -> None:
    import asyncio

    await asyncio.gather(*tasks)


def _serialize_event(event: Mapping[str, object]) -> bytes:
    import json

    return json.dumps(event, separators=(",", ":"), sort_keys=True, default=_json_default).encode("utf-8")


def _json_default(value: object) -> str:
    if isinstance(value, bytes):
        return value.hex()
    raise TypeError("unsupported type")
