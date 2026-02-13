"""Wire encoding/decoding for JSON and FlatBuffers frames."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import flatbuffers
from flatbuffers import encode, number_types, packer, table

WireFormat = Literal["json", "flatbuffers"]


class MessageType:
    HELLO = 0
    WELCOME = 1
    PUBLISH = 2
    SUBSCRIBE = 3
    UNSUBSCRIBE = 4
    EVENT = 5
    ACK = 6
    ERROR = 7
    NOISE = 8


_TYPE_TO_NAME = {
    MessageType.HELLO: "hello",
    MessageType.WELCOME: "welcome",
    MessageType.PUBLISH: "publish",
    MessageType.SUBSCRIBE: "subscribe",
    MessageType.UNSUBSCRIBE: "unsubscribe",
    MessageType.EVENT: "event",
    MessageType.ACK: "ack",
    MessageType.ERROR: "error",
    MessageType.NOISE: "noise",
}

_NAME_TO_TYPE = {value: key for key, value in _TYPE_TO_NAME.items()}


@dataclass
class DecodedMessage:
    msg_type: str
    payload: dict[str, Any]


def encode_message(payload: dict[str, Any], *, fmt: WireFormat) -> bytes:
    if fmt == "json":
        return _encode_json(payload)
    return _encode_flatbuffers(payload)


def decode_message(raw: bytes | str, *, fmt: WireFormat) -> DecodedMessage:
    if fmt == "json":
        return _decode_json(raw)
    return _decode_flatbuffers(raw)


def _encode_json(payload: dict[str, Any]) -> bytes:
    import json

    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _decode_json(raw: bytes | str) -> DecodedMessage:
    import json

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    message = json.loads(raw)
    if not isinstance(message, dict):
        raise ValueError("message must be object")
    msg_type = message.get("type")
    if not isinstance(msg_type, str):
        raise ValueError("message type missing")
    return DecodedMessage(msg_type=msg_type, payload=message)


def _encode_flatbuffers(payload: dict[str, Any]) -> bytes:
    msg_type = payload.get("type")
    if not isinstance(msg_type, str):
        raise ValueError("message type missing")
    msg_type_id = _NAME_TO_TYPE.get(msg_type)
    if msg_type_id is None:
        raise ValueError("unknown message type")
    body = _encode_json(payload)
    builder = flatbuffers.Builder(len(body) + 64)
    payload_vec = builder.CreateByteVector(body)
    builder.StartObject(2)
    builder.PrependUint8Slot(0, msg_type_id, 0)
    builder.PrependUOffsetTRelativeSlot(1, payload_vec, 0)
    msg = builder.EndObject()
    builder.Finish(msg)
    return bytes(builder.Output())


def _decode_flatbuffers(raw: bytes | str) -> DecodedMessage:
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    buf = raw
    uoffset = encode.Get(packer.uoffset, buf, 0)
    tab = table.Table(buf, uoffset)
    type_offset = tab.Offset(4)
    if type_offset == 0:
        raise ValueError("message type missing")
    msg_type_id = tab.Get(number_types.Uint8Flags, type_offset + tab.Pos)
    payload_offset = tab.Offset(6)
    payload: bytes
    if payload_offset == 0:
        payload = b"{}"
    else:
        start = tab.Vector(payload_offset)
        length = tab.VectorLen(payload_offset)
        payload = tab.Bytes[start : start + length]
    msg_type = _TYPE_TO_NAME.get(msg_type_id)
    if msg_type is None:
        raise ValueError("unknown message type")
    decoded = _decode_json(payload)
    return DecodedMessage(msg_type=msg_type, payload=decoded.payload)
