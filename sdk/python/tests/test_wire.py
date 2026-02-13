from __future__ import annotations

from aether.wire import decode_message, encode_message


def test_json_roundtrip() -> None:
    payload = {"type": "publish", "event": {"kind": 1}}
    raw = encode_message(payload, fmt="json")
    decoded = decode_message(raw, fmt="json")
    assert decoded.msg_type == "publish"
    assert decoded.payload["event"]["kind"] == 1


def test_flatbuffers_roundtrip() -> None:
    payload = {"type": "subscribe", "sub_id": "abc", "filters": [{"kinds": [1]}]}
    raw = encode_message(payload, fmt="flatbuffers")
    decoded = decode_message(raw, fmt="flatbuffers")
    assert decoded.msg_type == "subscribe"
    assert decoded.payload["sub_id"] == "abc"
