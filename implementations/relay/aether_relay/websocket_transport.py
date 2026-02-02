"""WebSocket transport using websockets."""

from __future__ import annotations

import json
from uuid import uuid4

import websockets
from websockets.server import WebSocketServer, WebSocketServerProtocol

from .core import RelayCore
from .handlers import handle_message


async def _handle_ws(core: RelayCore, websocket: WebSocketServerProtocol) -> None:
    connection_id = f"ws-{uuid4()}"

    async def send(_conn_id: str, payload: dict[str, object]) -> None:
        await websocket.send(json.dumps(payload, separators=(",", ":")))

    async for message in websocket:
        payload = json.loads(message)
        await handle_message(core, connection_id, payload, send)


async def serve_websocket(*, host: str, port: int, core: RelayCore) -> WebSocketServer:
    return await websockets.serve(lambda ws: _handle_ws(core, ws), host, port)
