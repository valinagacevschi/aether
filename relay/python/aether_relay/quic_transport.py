"""QUIC transport using aioquic."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.asyncio.server import QuicServer
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived

from .core import RelayCore
from .handlers import handle_message
from .noise import NoiseSession, derive_shared_key, generate_keypair
from .wire import DecodedMessage, decode_message, encode_message


class QuicRelayProtocol(QuicConnectionProtocol):
    def __init__(self, *args: Any, core: RelayCore, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._core = core
        self._connection_id = f"quic-{uuid4()}"
        self._buffers: dict[int, bytearray] = {}
        self._format = "json"
        self._handshake_done = False
        self._noise: NoiseSession | None = None
        self._noise_pending: NoiseSession | None = None

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, StreamDataReceived):
            buffer = self._buffers.setdefault(event.stream_id, bytearray())
            buffer.extend(event.data)
            while True:
                if len(buffer) < 4:
                    break
                size = int.from_bytes(buffer[:4], "big")
                if len(buffer) < 4 + size:
                    break
                raw = bytes(buffer[4 : 4 + size])
                del buffer[: 4 + size]
                asyncio.create_task(self._handle_message(event.stream_id, raw))

    async def _handle_message(self, stream_id: int, raw: bytes) -> None:
        try:
            decoded = await self._decode_incoming(raw)

            async def send(_conn_id: str, payload: dict[str, object]) -> None:
                data = encode_message(payload, fmt=self._format)  # type: ignore[arg-type]
                if self._noise is not None:
                    data = self._wrap_noise(data)
                frame = len(data).to_bytes(4, "big") + data
                self._quic.send_stream_data(stream_id, frame, end_stream=False)
                self.transmit()

            if decoded.msg_type == "hello":
                await self._handle_hello(decoded.payload, send)
            else:
                await handle_message(self._core, self._connection_id, decoded.payload, send)
        except Exception as exc:
            data = encode_message({"type": "error", "error": str(exc)}, fmt=self._format)
            frame = len(data).to_bytes(4, "big") + data
            self._quic.send_stream_data(stream_id, frame, end_stream=False)
            self.transmit()

    async def _decode_incoming(self, raw: bytes) -> DecodedMessage:
        if not self._handshake_done:
            if raw.startswith(b"{"):
                self._format = "json"
                return decode_message(raw, fmt="json")
            self._format = "flatbuffers"
            return decode_message(raw, fmt="flatbuffers")
        if self._noise is not None:
            decoded = decode_message(raw, fmt=self._format)  # type: ignore[arg-type]
            if decoded.msg_type != "noise":
                raise ValueError("noise expected")
            payload_hex = decoded.payload.get("payload_hex")
            if not isinstance(payload_hex, str):
                raise ValueError("noise payload missing")
            inner = self._noise.decrypt(bytes.fromhex(payload_hex))
            return decode_message(inner, fmt=self._format)  # type: ignore[arg-type]
        return decode_message(raw, fmt=self._format)  # type: ignore[arg-type]

    def _wrap_noise(self, data: bytes) -> bytes:
        assert self._noise is not None
        encrypted = self._noise.encrypt(data)
        return encode_message({"type": "noise", "payload_hex": encrypted.hex()}, fmt=self._format)

    async def _handle_hello(self, payload: dict[str, object], send: callable) -> None:
        version = payload.get("version")
        formats = payload.get("formats", ["json"])
        if not isinstance(formats, list):
            formats = ["json"]
        self._format = "flatbuffers" if "flatbuffers" in formats else "json"
        self._handshake_done = True

        noise_req = False
        noise_info = payload.get("noise")
        noise_pubkey: str | None = None
        if isinstance(noise_info, dict):
            noise_req = bool(noise_info.get("required", False))
            noise_pubkey = noise_info.get("pubkey") if isinstance(noise_info.get("pubkey"), str) else None

        if noise_req:
            if noise_pubkey is None:
                raise ValueError("noise pubkey required")
            priv, pub = generate_keypair()
            shared = derive_shared_key(priv, bytes.fromhex(noise_pubkey))
            self._noise_pending = NoiseSession(shared)
            await send(
                "server",
                {
                    "type": "welcome",
                    "version": version,
                    "format": self._format,
                    "noise": {"required": True, "pubkey": pub.hex()},
                },
            )
            self._noise = self._noise_pending
            self._noise_pending = None
            return
        await send(
            "server",
            {"type": "welcome", "version": version, "format": self._format, "noise": {"required": False}},
        )


async def serve_quic(
    *,
    host: str,
    port: int,
    cert_path: str,
    key_path: str,
    core: RelayCore,
) -> QuicServer:
    config = QuicConfiguration(is_client=False)
    config.load_cert_chain(cert_path, key_path)
    return await serve(
        host=host,
        port=port,
        configuration=config,
        create_protocol=lambda *args, **kwargs: QuicRelayProtocol(*args, core=core, **kwargs),
    )
