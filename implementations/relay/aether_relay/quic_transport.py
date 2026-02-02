"""QUIC transport using aioquic."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import uuid4

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.asyncio.server import QuicServer
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived

from .core import RelayCore
from .handlers import handle_message


class QuicRelayProtocol(QuicConnectionProtocol):
    def __init__(self, *args: Any, core: RelayCore, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._core = core
        self._connection_id = f"quic-{uuid4()}"
        self._buffers: dict[int, bytearray] = {}

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, StreamDataReceived):
            buffer = self._buffers.setdefault(event.stream_id, bytearray())
            buffer.extend(event.data)
            while b"\n" in buffer:
                raw, _, rest = buffer.partition(b"\n")
                self._buffers[event.stream_id] = bytearray(rest)
                if not raw:
                    continue
                asyncio.create_task(self._handle_message(event.stream_id, raw))

    async def _handle_message(self, stream_id: int, raw: bytes) -> None:
        message = json.loads(raw.decode("utf-8"))

        async def send(_conn_id: str, payload: dict[str, object]) -> None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
            self._quic.send_stream_data(stream_id, data, end_stream=False)
            self.transmit()

        await handle_message(self._core, self._connection_id, message, send)


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
