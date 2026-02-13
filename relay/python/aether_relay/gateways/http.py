"""HTTP gateway: REST, SSE, and WebSocket JSON for relay interoperability."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import websockets
from websockets.server import WebSocketServer, WebSocketServerProtocol

from ..core import RelayCore
from ..handlers import handle_message
from .common import (
    ERROR_INVALID_EVENT,
    ERROR_INVALID_MESSAGE,
    ERROR_SUBSCRIPTION_NOT_FOUND,
    ERROR_VALIDATION_FAILED,
    from_http_event,
    to_http_event,
)


@dataclass
class HttpSubscription:
    connection_id: str
    subscription_id: str
    queue: asyncio.Queue[dict[str, object]]


class HttpGateway:
    def __init__(self, core: RelayCore) -> None:
        self._core = core
        self._subscriptions: dict[str, HttpSubscription] = {}
        self._ws_connections: dict[str, WebSocketServerProtocol] = {}
        self._dropped_messages = 0

    async def start(self, *, host: str, http_port: int, ws_port: int) -> tuple[asyncio.AbstractServer, WebSocketServer]:
        http_server = await asyncio.start_server(self._handle_http_client, host=host, port=http_port)
        ws_server = await websockets.serve(lambda ws: self._handle_ws(ws), host, ws_port)
        return http_server, ws_server

    async def _handle_http_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await reader.readline()
            if not request_line:
                writer.close()
                await writer.wait_closed()
                return
            parts = request_line.decode("utf-8").strip().split(" ")
            if len(parts) != 3:
                await self._write_json(writer, 400, {"error": ERROR_INVALID_MESSAGE, "message": "bad request line"})
                return
            method, target, _ = parts
            headers = await self._read_headers(reader)
            body = b""
            if "content-length" in headers:
                body = await reader.readexactly(int(headers["content-length"]))

            parsed = urlparse(target)
            if method == "GET" and parsed.path == "/healthz":
                await self._write_json(writer, 200, {"status": "ok", "dropped_messages": self._dropped_messages})
                return
            if method == "POST" and parsed.path == "/v1/events":
                await self._handle_post_event(writer, body)
                return
            if method == "POST" and parsed.path == "/v1/subscriptions":
                await self._handle_post_subscription(writer, body)
                return
            if method == "DELETE" and parsed.path.startswith("/v1/subscriptions/"):
                sub_id = parsed.path.split("/")[-1]
                await self._handle_delete_subscription(writer, sub_id)
                return
            if method == "GET" and parsed.path == "/v1/stream":
                query = parse_qs(parsed.query)
                sub_id = query.get("subscription_id", [None])[0]
                if not isinstance(sub_id, str) or not sub_id:
                    await self._write_json(writer, 400, {"error": ERROR_INVALID_MESSAGE, "message": "subscription_id required"})
                    return
                await self._handle_sse_stream(writer, sub_id)
                return
            await self._write_json(writer, 404, {"error": "not_found"})
        except Exception as exc:
            await self._write_json(writer, 500, {"error": "internal", "message": str(exc)})

    async def _handle_post_event(self, writer: asyncio.StreamWriter, body: bytes) -> None:
        try:
            payload = json.loads(body.decode("utf-8") if body else "{}")
            if not isinstance(payload, Mapping):
                raise ValueError(f"{ERROR_INVALID_MESSAGE}: payload must be object")
            event = payload.get("event", payload)
            if not isinstance(event, Mapping):
                raise ValueError(f"{ERROR_INVALID_EVENT}: event must be object")
            normalized = from_http_event(event)
            await self._core.publish("http-api", normalized, self._send)
            await self._write_json(
                writer,
                200,
                {
                    "accepted": True,
                    "event_id": normalized.get("event_id"),
                    "message": "accepted",
                },
            )
        except Exception as exc:
            await self._write_json(
                writer,
                400,
                {"accepted": False, "error": ERROR_VALIDATION_FAILED, "message": str(exc)},
            )

    async def _handle_post_subscription(self, writer: asyncio.StreamWriter, body: bytes) -> None:
        try:
            payload = json.loads(body.decode("utf-8") if body else "{}")
            if not isinstance(payload, Mapping):
                raise ValueError(f"{ERROR_INVALID_MESSAGE}: payload must be object")
            filters = payload.get("filters")
            if isinstance(filters, Mapping):
                filter_list = [dict(filters)]
            elif isinstance(filters, list):
                filter_list = [dict(item) for item in filters if isinstance(item, Mapping)]
            else:
                raise ValueError(f"{ERROR_INVALID_MESSAGE}: filters must be object or list")
            if not filter_list:
                raise ValueError(f"{ERROR_INVALID_MESSAGE}: filters required")
            sub_id = payload.get("subscription_id")
            if not isinstance(sub_id, str) or not sub_id:
                sub_id = f"sub-{uuid4().hex}"
            conn_id = f"http-sse-{sub_id}"
            self._core.subscribe(conn_id, sub_id, filter_list)
            self._subscriptions[sub_id] = HttpSubscription(
                connection_id=conn_id,
                subscription_id=sub_id,
                queue=asyncio.Queue(maxsize=1024),
            )
            await self._write_json(writer, 200, {"subscription_id": sub_id})
        except Exception as exc:
            await self._write_json(writer, 400, {"error": ERROR_INVALID_MESSAGE, "message": str(exc)})

    async def _handle_delete_subscription(self, writer: asyncio.StreamWriter, sub_id: str) -> None:
        sub = self._subscriptions.pop(sub_id, None)
        if sub is None:
            await self._write_json(writer, 404, {"error": ERROR_SUBSCRIPTION_NOT_FOUND})
            return
        self._core.unsubscribe(sub.connection_id, sub.subscription_id)
        await self._write_json(writer, 200, {"deleted": True, "subscription_id": sub_id})

    async def _handle_sse_stream(self, writer: asyncio.StreamWriter, sub_id: str) -> None:
        sub = self._subscriptions.get(sub_id)
        if sub is None:
            await self._write_json(writer, 404, {"error": ERROR_SUBSCRIPTION_NOT_FOUND})
            return
        headers = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/event-stream\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: keep-alive\r\n\r\n"
        )
        writer.write(headers.encode("utf-8"))
        await writer.drain()
        event_counter = 0
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(sub.queue.get(), timeout=15.0)
                    event_counter += 1
                    data = json.dumps(payload, separators=(",", ":"))
                    writer.write(f"id: {event_counter}\nevent: event\ndata: {data}\n\n".encode("utf-8"))
                    await writer.drain()
                except asyncio.TimeoutError:
                    writer.write(b": heartbeat\n\n")
                    await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def _handle_ws(self, websocket: WebSocketServerProtocol) -> None:
        path = getattr(websocket, "path", "/")
        if path != "/v1/ws":
            await websocket.close(code=1008, reason="path not supported")
            return

        connection_id = f"http-ws-{uuid4()}"
        self._ws_connections[connection_id] = websocket

        async def send(conn_id: str, payload: Mapping[str, object]) -> None:
            if conn_id != connection_id:
                return
            await websocket.send(json.dumps(payload, separators=(",", ":"), default=_json_default))

        try:
            async for raw in websocket:
                message = json.loads(raw)
                if not isinstance(message, Mapping):
                    await websocket.send(json.dumps({"type": "error", "error": ERROR_INVALID_MESSAGE}))
                    continue
                if message.get("type") == "publish" and isinstance(message.get("event"), Mapping):
                    try:
                        normalized = from_http_event(message["event"])
                        await handle_message(self._core, connection_id, {"type": "publish", "event": normalized}, send)
                    except Exception as exc:
                        await websocket.send(
                            json.dumps({"type": "error", "error": ERROR_VALIDATION_FAILED, "message": str(exc)})
                        )
                    continue
                await handle_message(self._core, connection_id, message, send)
        finally:
            self._core.clear(connection_id)
            self._ws_connections.pop(connection_id, None)

    async def _send(self, conn_id: str, payload: Mapping[str, object]) -> None:
        if payload.get("type") != "event":
            return
        sub_id = payload.get("sub_id")
        event = payload.get("event")
        if not isinstance(sub_id, str) or not isinstance(event, Mapping):
            return

        for subscription in self._subscriptions.values():
            if subscription.connection_id == conn_id and subscription.subscription_id == sub_id:
                message = {"type": "event", "sub_id": sub_id, "event": to_http_event(event)}
                if subscription.queue.full():
                    try:
                        subscription.queue.get_nowait()
                        self._dropped_messages += 1
                    except asyncio.QueueEmpty:
                        pass
                subscription.queue.put_nowait(message)
                return

        ws = self._ws_connections.get(conn_id)
        if ws is not None:
            await ws.send(json.dumps(payload, separators=(",", ":"), default=_json_default))

    async def _write_json(self, writer: asyncio.StreamWriter, status: int, payload: Mapping[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":"), default=_json_default).encode("utf-8")
        reason = _reason(status)
        response = (
            f"HTTP/1.1 {status} {reason}\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("utf-8")
        writer.write(response + body)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def _read_headers(self, reader: asyncio.StreamReader) -> dict[str, str]:
        headers: dict[str, str] = {}
        while True:
            line = await reader.readline()
            if line in (b"\r\n", b"\n", b""):
                return headers
            text = line.decode("utf-8").strip()
            if ":" not in text:
                continue
            key, value = text.split(":", 1)
            headers[key.strip().lower()] = value.strip()


def _reason(status: int) -> str:
    mapping = {
        200: "OK",
        400: "Bad Request",
        404: "Not Found",
        500: "Internal Server Error",
    }
    return mapping.get(status, "OK")


def _json_default(value: object) -> str:
    if isinstance(value, bytes):
        return value.hex()
    raise TypeError("unsupported type")
