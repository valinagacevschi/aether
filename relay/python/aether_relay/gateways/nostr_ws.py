"""NOSTR NIP-01 compatible websocket gateway."""

from __future__ import annotations

import json
from typing import Any, Callable, Mapping
from uuid import uuid4

import websockets
from websockets.server import WebSocketServer, WebSocketServerProtocol

from ..core import RelayCore
from .common import (
    ERROR_INVALID_MESSAGE,
    ERROR_VALIDATION_FAILED,
    from_nostr_event,
    nostr_filter_to_aether,
    to_nostr_event,
)


async def serve_nostr(*, host: str, port: int, core: RelayCore) -> WebSocketServer:
    return await websockets.serve(lambda ws: _handle_nostr(core, ws), host, port)


async def _handle_nostr(core: RelayCore, websocket: WebSocketServerProtocol) -> None:
    connection_id = f"nostr-{uuid4()}"

    async def send(conn_id: str, payload: Mapping[str, object]) -> None:
        if conn_id != connection_id:
            return
        msg_type = payload.get("type")
        if msg_type == "event":
            sub_id = payload.get("sub_id")
            event = payload.get("event")
            if isinstance(sub_id, str) and isinstance(event, Mapping):
                await websocket.send(json.dumps(["EVENT", sub_id, to_nostr_event(event)]))

    try:
        async for raw in websocket:
            try:
                message = json.loads(raw)
                if not isinstance(message, list) or not message:
                    await _notice(websocket, f"{ERROR_INVALID_MESSAGE}: expected array message")
                    continue
                command = message[0]
                if command == "EVENT":
                    await _on_event(core, connection_id, message, websocket, send)
                elif command == "REQ":
                    await _on_req(core, connection_id, message, websocket)
                elif command == "CLOSE":
                    await _on_close(core, connection_id, message)
                else:
                    await _notice(websocket, f"{ERROR_INVALID_MESSAGE}: unsupported command")
            except ValueError as exc:
                await _notice(websocket, str(exc))
    finally:
        core.clear(connection_id)


async def _on_event(
    core: RelayCore,
    connection_id: str,
    message: list[object],
    websocket: WebSocketServerProtocol,
    send: Callable[[str, Mapping[str, object]], Any],
) -> None:
    if len(message) != 2 or not isinstance(message[1], Mapping):
        raise ValueError(f"{ERROR_INVALID_MESSAGE}: EVENT payload invalid")
    try:
        event = from_nostr_event(message[1])
        buffered_events: list[Mapping[str, object]] = []

        async def send_buffered(conn_id: str, payload: Mapping[str, object]) -> None:
            if conn_id == connection_id and payload.get("type") == "event":
                buffered_events.append(payload)
                return
            await send(conn_id, payload)

        await core.publish(connection_id, event, send_buffered)
        event_id = str(event.get("event_id", ""))
        await websocket.send(json.dumps(["OK", event_id, True, "accepted"]))
        for payload in buffered_events:
            await send(connection_id, payload)
    except Exception as exc:
        event_id = ""
        if isinstance(message[1], Mapping):
            raw_id = message[1].get("id") or message[1].get("event_id")
            if isinstance(raw_id, str):
                event_id = raw_id
        await websocket.send(json.dumps(["OK", event_id, False, f"{ERROR_VALIDATION_FAILED}: {exc}"]))


async def _on_req(
    core: RelayCore,
    connection_id: str,
    message: list[object],
    websocket: WebSocketServerProtocol,
) -> None:
    if len(message) < 3:
        raise ValueError(f"{ERROR_INVALID_MESSAGE}: REQ requires sub_id and filter")
    sub_id = message[1]
    if not isinstance(sub_id, str):
        raise ValueError(f"{ERROR_INVALID_MESSAGE}: sub_id must be string")
    filters: list[dict[str, object]] = []
    for raw in message[2:]:
        if not isinstance(raw, Mapping):
            raise ValueError(f"{ERROR_INVALID_MESSAGE}: filter must be object")
        filters.append(nostr_filter_to_aether(raw))
    core.subscribe(connection_id, sub_id, filters)
    await websocket.send(json.dumps(["EOSE", sub_id]))


async def _on_close(core: RelayCore, connection_id: str, message: list[object]) -> None:
    if len(message) != 2 or not isinstance(message[1], str):
        raise ValueError(f"{ERROR_INVALID_MESSAGE}: CLOSE requires sub_id")
    core.unsubscribe(connection_id, message[1])


async def _notice(websocket: WebSocketServerProtocol, message: str) -> None:
    await websocket.send(json.dumps(["NOTICE", message]))
