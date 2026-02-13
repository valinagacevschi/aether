"""Client implementation for the Aether Python SDK."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Iterable

import websockets

from .filters import EventFilter, match_event, normalize_filter
from .noise import NoiseSession, derive_shared_key, generate_keypair
from .wire import decode_message, encode_message


@dataclass
class ConnectionState:
    url: str
    websocket: websockets.WebSocketClientProtocol | None
    subscriptions: dict[str, EventFilter]
    reconnect_attempts: int = 0
    format: str = "json"
    noise: NoiseSession | None = None
    noise_priv: bytes | None = None


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
                await self._send(state, {"type": "publish", "event": event})
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
            await self._send(
                state,
                {
                    "type": "subscribe",
                    "sub_id": subscription_id,
                    "filters": [raw_filter],
                },
            )

    async def unsubscribe(self, subscription_id: str) -> None:
        for state in self._connections.values():
            if state.websocket is None:
                continue
            state.subscriptions.pop(subscription_id, None)
            await self._send(state, {"type": "unsubscribe", "sub_id": subscription_id})

    def on_event(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._event_callbacks.append(callback)

    async def _connect_one(self, state: ConnectionState) -> None:
        session_ticket = self._session_tickets.get(state.url)
        websocket = await websockets.connect(
            state.url,
            extra_headers={"x-session-ticket": session_ticket.hex()} if session_ticket else None,
        )
        state.websocket = websocket

        noise_priv, noise_pub = generate_keypair()
        state.noise_priv = noise_priv
        hello = {
            "type": "hello",
            "version": 1,
            "formats": ["flatbuffers", "json"],
            "noise": {"required": True, "pubkey": noise_pub.hex()},
        }
        await websocket.send(encode_message(hello, fmt="json").decode("utf-8"))

        raw = await websocket.recv()
        decoded = decode_message(raw, fmt="json" if isinstance(raw, str) else "flatbuffers")
        if decoded.msg_type != "welcome":
            raise ValueError("relay did not respond with welcome")
        fmt = decoded.payload.get("format", "json")
        state.format = fmt if fmt in ("json", "flatbuffers") else "json"
        noise_info = decoded.payload.get("noise")
        if isinstance(noise_info, dict) and noise_info.get("required"):
            pub_hex = noise_info.get("pubkey")
            if not isinstance(pub_hex, str):
                raise ValueError("noise pubkey missing")
            shared = derive_shared_key(state.noise_priv, bytes.fromhex(pub_hex))
            state.noise = NoiseSession(shared)

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

    async def _handle_message(self, state: ConnectionState, raw: str | bytes) -> None:
        decoded = decode_message(raw, fmt=state.format)  # type: ignore[arg-type]
        if state.noise is not None:
            if decoded.msg_type != "noise":
                return
            payload_hex = decoded.payload.get("payload_hex")
            if not isinstance(payload_hex, str):
                return
            inner = state.noise.decrypt(bytes.fromhex(payload_hex))
            decoded = decode_message(inner, fmt=state.format)  # type: ignore[arg-type]

        if decoded.msg_type == "event":
            event = decoded.payload.get("event")
            if isinstance(event, dict):
                for flt in state.subscriptions.values():
                    if match_event(event, flt):
                        for callback in self._event_callbacks:
                            callback(event)
                        return

    async def _send(self, state: ConnectionState, payload: dict[str, object]) -> None:
        assert state.websocket is not None
        data = encode_message(payload, fmt=state.format)  # type: ignore[arg-type]
        if state.noise is not None:
            encrypted = state.noise.encrypt(data)
            data = encode_message({"type": "noise", "payload_hex": encrypted.hex()}, fmt=state.format)
        if state.format == "json":
            await state.websocket.send(data.decode("utf-8"))
        else:
            await state.websocket.send(data)

    async def _schedule_reconnect(self, state: ConnectionState) -> None:
        state.reconnect_attempts += 1
        delay = min(60.0, 2 ** state.reconnect_attempts)
        await asyncio.sleep(delay)
        await self._connect_one(state)
