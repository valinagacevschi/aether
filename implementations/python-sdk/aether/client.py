"""Client stubs for the Aether Python SDK."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

import websockets

from .filters import EventFilter, match_event, normalize_filter


@dataclass
class ConnectionState:
    url: str
    websocket: websockets.WebSocketClientProtocol | None
    subscriptions: dict[str, EventFilter]
    reconnect_attempts: int = 0


class Client:
    """Aether client stub with async I/O signatures."""

    def __init__(self, *, max_connections: int = 3) -> None:
        self._max_connections = max_connections
        self._connections: dict[str, ConnectionState] = {}
        self._session_tickets: dict[str, bytes] = {}
        self._event_callbacks: list[Callable[[dict[str, Any]], None]] = []

    async def connect(self, urls: Iterable[str]) -> None:
        """Connect to relay endpoints."""

        for url in list(urls)[: self._max_connections]:
            state = ConnectionState(url=url, websocket=None, subscriptions={})
            self._connections[url] = state
            await self._connect_one(state)

    async def publish(self, event: dict[str, Any]) -> dict[str, bool]:
        """Publish an event to all connected relays."""

        results: dict[str, bool] = {}
        for url, state in self._connections.items():
            if state.websocket is None:
                results[url] = False
                continue
            try:
                await state.websocket.send(_encode_message({"type": "publish", "event": event}))
                results[url] = True
            except Exception:
                results[url] = False
        return results

    async def subscribe(self, subscription_id: str, raw_filter: dict[str, object]) -> None:
        """Subscribe using filter settings."""

        flt = normalize_filter(raw_filter)
        for state in self._connections.values():
            if state.websocket is None:
                continue
            state.subscriptions[subscription_id] = flt
            await state.websocket.send(
                _encode_message(
                    {
                        "type": "subscribe",
                        "sub_id": subscription_id,
                        "filters": [raw_filter],
                    }
                )
            )

    async def unsubscribe(self, subscription_id: str) -> None:
        for state in self._connections.values():
            if state.websocket is None:
                continue
            state.subscriptions.pop(subscription_id, None)
            await state.websocket.send(
                _encode_message({"type": "unsubscribe", "sub_id": subscription_id})
            )

    def on_event(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._event_callbacks.append(callback)

    async def _connect_one(self, state: ConnectionState) -> None:
        session_ticket = self._session_tickets.get(state.url)
        websocket = await websockets.connect(
            state.url,
            extra_headers={"x-session-ticket": session_ticket.hex()} if session_ticket else None,
        )
        state.websocket = websocket

        asyncio.create_task(self._listen(state))

    async def _listen(self, state: ConnectionState) -> None:
        assert state.websocket is not None
        while True:
            try:
                raw = await state.websocket.recv()
                await self._handle_message(state, raw)
            except Exception:
                await self._schedule_reconnect(state)
                return

    async def _handle_message(self, state: ConnectionState, raw: str) -> None:
        import json

        message = json.loads(raw)
        if not isinstance(message, dict):
            return
        if message.get("type") == "event":
            event = message.get("event")
            if isinstance(event, dict):
                for flt in state.subscriptions.values():
                    if match_event(event, flt):
                        for callback in self._event_callbacks:
                            callback(event)
                        return

    async def _schedule_reconnect(self, state: ConnectionState) -> None:
        state.reconnect_attempts += 1
        delay = min(60.0, 2 ** state.reconnect_attempts)
        await asyncio.sleep(delay)
        await self._connect_one(state)


def _encode_message(payload: dict[str, object]) -> str:
    import json

    return json.dumps(payload, separators=(",", ":"))
