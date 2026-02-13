"""WebSocket transport using websockets."""

from __future__ import annotations

from uuid import uuid4

import websockets
from websockets.server import WebSocketServer, WebSocketServerProtocol

from .core import RelayCore
from .handlers import handle_message
from .noise import NoiseSession, derive_shared_key, generate_keypair
from .wire import DecodedMessage, decode_message, encode_message


class _ConnectionState:
    def __init__(self) -> None:
        self.format: str = "json"
        self.handshake_done = False
        self.noise: NoiseSession | None = None
        self.noise_pending: NoiseSession | None = None
        self.noise_required = False


async def _handle_ws(core: RelayCore, websocket: WebSocketServerProtocol) -> None:
    connection_id = f"ws-{uuid4()}"
    state = _ConnectionState()

    async def send(_conn_id: str, payload: dict[str, object]) -> None:
        data = encode_message(payload, fmt=state.format)  # type: ignore[arg-type]
        if state.noise is not None:
            data = _wrap_noise(state, data)
            await websocket.send(data)
            return
        if state.format == "json":
            await websocket.send(data.decode("utf-8"))
        else:
            await websocket.send(data)

    async for message in websocket:
        try:
            decoded = await _decode_incoming(state, message)
            await _dispatch(core, connection_id, decoded, send, state)
        except Exception as exc:
            await send(connection_id, {"type": "error", "error": str(exc)})


async def _decode_incoming(
    state: _ConnectionState, message: str | bytes
) -> DecodedMessage:
    if not state.handshake_done:
        if isinstance(message, bytes):
            decoded = decode_message(message, fmt="flatbuffers")
            state.format = "flatbuffers"
        else:
            decoded = decode_message(message, fmt="json")
            state.format = "json"
        return decoded
    if state.noise is not None:
        return _decode_noise(state, message)
    return decode_message(message, fmt=state.format)  # type: ignore[arg-type]


def _wrap_noise(state: _ConnectionState, data: bytes) -> bytes:
    assert state.noise is not None
    encrypted = state.noise.encrypt(data)
    payload = {"type": "noise", "payload_hex": encrypted.hex()}
    return encode_message(payload, fmt=state.format)  # type: ignore[arg-type]


def _decode_noise(state: _ConnectionState, message: str | bytes) -> DecodedMessage:
    assert state.noise is not None
    decoded = decode_message(message, fmt=state.format)  # type: ignore[arg-type]
    if decoded.msg_type != "noise":
        raise ValueError("noise expected")
    payload = decoded.payload
    if state.format == "json":
        payload_hex = payload.get("payload_hex")
        if not isinstance(payload_hex, str):
            raise ValueError("noise payload missing")
        encrypted = bytes.fromhex(payload_hex)
    else:
        payload_hex = payload.get("payload_hex")
        if not isinstance(payload_hex, str):
            raise ValueError("noise payload missing")
        encrypted = bytes.fromhex(payload_hex)
    inner = state.noise.decrypt(encrypted)
    return decode_message(inner, fmt=state.format)  # type: ignore[arg-type]


async def _dispatch(
    core: RelayCore,
    connection_id: str,
    decoded: DecodedMessage,
    send: callable,
    state: _ConnectionState,
) -> None:
    payload = decoded.payload
    msg_type = decoded.msg_type
    if msg_type == "hello":
        await _handle_hello(payload, send, state)
        return
    await handle_message(core, connection_id, payload, send)


async def _handle_hello(payload: dict[str, object], send: callable, state: _ConnectionState) -> None:
    version = payload.get("version")
    formats = payload.get("formats", ["json"])
    if not isinstance(formats, list):
        formats = ["json"]
    fmt = "flatbuffers" if "flatbuffers" in formats else "json"
    noise_req = False
    noise_info = payload.get("noise")
    noise_pubkey: str | None = None
    if isinstance(noise_info, dict):
        noise_req = bool(noise_info.get("required", False))
        noise_pubkey = noise_info.get("pubkey") if isinstance(noise_info.get("pubkey"), str) else None

    state.format = fmt
    state.handshake_done = True
    if noise_req:
        if noise_pubkey is None:
            raise ValueError("noise pubkey required")
        priv, pub = generate_keypair()
        shared = derive_shared_key(priv, bytes.fromhex(noise_pubkey))
        state.noise_pending = NoiseSession(shared)
        state.noise_required = True
        await send(
            "server",
            {
                "type": "welcome",
                "version": version,
                "format": fmt,
                "noise": {"required": True, "pubkey": pub.hex()},
            },
        )
        state.noise = state.noise_pending
        state.noise_pending = None
        return
    await send(
        "server",
        {"type": "welcome", "version": version, "format": fmt, "noise": {"required": False}},
    )


async def serve_websocket(*, host: str, port: int, core: RelayCore) -> WebSocketServer:
    return await websockets.serve(lambda ws: _handle_ws(core, ws), host, port)
