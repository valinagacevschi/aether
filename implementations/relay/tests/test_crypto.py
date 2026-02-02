from __future__ import annotations

from pathlib import Path
from typing import TypedDict, cast

import yaml

from aether_relay.crypto import (
    Tag,
    compute_event_id,
    generate_keypair,
    normalize_tags,
    sign,
    verify,
)


class EventVector(TypedDict):
    pubkey: str
    created_at: int | str
    kind: int | str
    tags: list[object]
    content: str
    event_id: str
    sig: str


def test_generate_keypair() -> None:
    private_key, public_key = generate_keypair()
    assert len(private_key) == 32
    assert len(public_key) == 32


def test_sign_and_verify_roundtrip() -> None:
    private_key, public_key = generate_keypair()
    event_id = compute_event_id(
        pubkey=public_key,
        created_at=1700000000000000000,
        kind=1,
        tags=[],
        content=b"signed payload",
    )
    sig = sign(event_id, private_key)
    assert len(sig) == 64
    assert verify(event_id, sig, public_key)


def test_compute_event_id_vectors() -> None:
    vectors = _load_vectors()
    for vector in vectors:
        tags = normalize_tags(vector["tags"])
        event_id = compute_event_id(
            pubkey=bytes.fromhex(vector["pubkey"]),
            created_at=int(vector["created_at"]),
            kind=int(vector["kind"]),
            tags=tags,
            content=vector["content"].encode("utf-8"),
        )
        assert event_id.hex() == vector["event_id"]
        assert verify(
            event_id,
            bytes.fromhex(vector["sig"]),
            bytes.fromhex(vector["pubkey"]),
        )


def _load_vectors() -> list[EventVector]:
    root = Path(__file__).resolve().parents[3]
    vectors_path = root / "spec" / "test-vectors" / "valid-events.yaml"
    with vectors_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, list):
        raise AssertionError("valid-events.yaml must be a list")
    for item in data:
        if not isinstance(item, dict):
            raise AssertionError("valid-events.yaml entries must be mappings")
    return cast(list[EventVector], data)
