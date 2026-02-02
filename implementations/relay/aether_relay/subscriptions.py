"""Subscription tracking and event routing for the relay."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Iterable, Mapping

from .filters import EventFilter, match_event

SendFn = Callable[[str, str, Mapping[str, object]], Awaitable[None]]


@dataclass(frozen=True)
class Subscription:
    connection_id: str
    subscription_id: str
    filters: tuple[EventFilter, ...]


class SubscriptionManager:
    def __init__(self) -> None:
        self._subscriptions: dict[str, dict[str, Subscription]] = {}

    def add(self, connection_id: str, subscription_id: str, filters: Iterable[EventFilter]) -> None:
        bucket = self._subscriptions.setdefault(connection_id, {})
        bucket[subscription_id] = Subscription(
            connection_id=connection_id,
            subscription_id=subscription_id,
            filters=tuple(filters),
        )

    def remove(self, connection_id: str, subscription_id: str) -> None:
        bucket = self._subscriptions.get(connection_id)
        if not bucket:
            return
        bucket.pop(subscription_id, None)
        if not bucket:
            self._subscriptions.pop(connection_id, None)

    def clear(self, connection_id: str) -> None:
        self._subscriptions.pop(connection_id, None)

    def matches(self, event: Mapping[str, object]) -> list[Subscription]:
        matches: list[Subscription] = []
        for bucket in self._subscriptions.values():
            for subscription in bucket.values():
                if any(match_event(event, flt) for flt in subscription.filters):
                    matches.append(subscription)
        return matches

    def dispatch(self, event: Mapping[str, object], send: SendFn) -> list[asyncio.Task[None]]:
        tasks: list[asyncio.Task[None]] = []
        for subscription in self.matches(event):
            tasks.append(
                asyncio.create_task(
                    send(subscription.connection_id, subscription.subscription_id, event)
                )
            )
        return tasks
