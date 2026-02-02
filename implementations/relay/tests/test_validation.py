from __future__ import annotations

from pathlib import Path
from typing import TypedDict, cast

import pytest
import yaml

from aether_relay.validation import MAX_KIND, WINDOW_NS, validate_event


class EventVector(TypedDict):
    pubkey: str
    created_at: int | str
    kind: int | str
    tags: list[object]
    content: str
    event_id: str
    sig: str


def test_validation_passes_for_valid_vectors() -> None:
    for event in _load_vectors("valid-events.yaml"):
        validate_event(event, now_ns=int(event["created_at"]))


def test_validation_rejects_invalid_vectors() -> None:
    for event in _load_vectors("invalid-events.yaml"):
        with pytest.raises(ValueError):
            validate_event(event, now_ns=int(event["created_at"]))


def test_rejects_event_id_mismatch() -> None:
    event = _load_vectors("valid-events.yaml")[0].copy()
    event["event_id"] = "00" * 32
    with pytest.raises(ValueError, match="event_id mismatch"):
        validate_event(event, now_ns=int(event["created_at"]))


def test_rejects_invalid_signature() -> None:
    event = _load_vectors("valid-events.yaml")[0].copy()
    event["sig"] = "11" * 64
    with pytest.raises(ValueError, match="invalid signature"):
        validate_event(event, now_ns=int(event["created_at"]))


def test_rejects_out_of_range_kind() -> None:
    event = _load_vectors("valid-events.yaml")[0].copy()
    event["kind"] = MAX_KIND + 1
    with pytest.raises(ValueError, match="kind out of range"):
        validate_event(event, now_ns=int(event["created_at"]))


def test_rejects_timestamp_outside_window() -> None:
    event = _load_vectors("valid-events.yaml")[0].copy()
    created_at = int(event["created_at"])
    now = created_at - (WINDOW_NS + 1)
    with pytest.raises(ValueError, match="created_at outside allowed window"):
        validate_event(event, now_ns=now)


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
