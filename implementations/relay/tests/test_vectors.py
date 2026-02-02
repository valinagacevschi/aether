from __future__ import annotations

from pathlib import Path
from typing import TypedDict, cast

import yaml

from aether_relay.crypto import compute_event_id, normalize_tags, verify
from aether_relay.validation import MAX_KIND


class EventVector(TypedDict):
    pubkey: str
    created_at: int | str
    kind: int | str
    tags: list[object]
    content: str
    event_id: str
    sig: str


def test_valid_vectors_conformance() -> None:
    for event in _load_vectors("valid-events.yaml"):
        event_id = _compute_event_id(event)
        assert event_id.hex() == event["event_id"]
        assert verify(
            event_id,
            bytes.fromhex(event["sig"]),
            bytes.fromhex(event["pubkey"]),
        )
        assert _kind_in_range(event)


def test_invalid_vectors_conformance() -> None:
    for event in _load_vectors("invalid-events.yaml"):
        event_id = _compute_event_id(event)
        signature_ok = verify(
            event_id,
            bytes.fromhex(event["sig"]),
            bytes.fromhex(event["pubkey"]),
        )
        event_id_ok = event_id.hex() == event["event_id"]
        kind_ok = _kind_in_range(event)
        assert not (signature_ok and event_id_ok and kind_ok)


def _compute_event_id(event: EventVector) -> bytes:
    return compute_event_id(
        pubkey=bytes.fromhex(event["pubkey"]),
        created_at=int(event["created_at"]),
        kind=int(event["kind"]),
        tags=normalize_tags(event["tags"]),
        content=event["content"].encode("utf-8"),
    )


def _kind_in_range(event: EventVector) -> bool:
    kind = int(event["kind"])
    return 0 <= kind <= MAX_KIND


def _load_vectors(name: str) -> list[EventVector]:
    root = Path(__file__).resolve().parents[3]
    vectors_path = root / "spec" / "test-vectors" / name
    with vectors_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, list):
        raise AssertionError(f"{name} must be a list")
    for item in data:
        if not isinstance(item, dict):
            raise AssertionError(f"{name} entries must be mappings")
    return cast(list[EventVector], data)
