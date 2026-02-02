from __future__ import annotations

import pytest

from aether_relay.storage import RocksDBEventStore


def _event(
    *,
    event_id: bytes,
    pubkey: bytes,
    kind: int,
    created_at: int,
    tags: list[list[str]] | None = None,
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "pubkey": pubkey,
        "kind": kind,
        "created_at": created_at,
        "tags": tags or [],
        "content": "",
        "sig": b"\x00" * 64,
    }


def test_rocksdb_insert_and_query(tmp_path) -> None:
    pytest.importorskip("rocksdb")
    store = RocksDBEventStore(str(tmp_path / "rocksdb"))
    pubkey = b"\x01" * 32
    event = _event(event_id=b"\x10" * 32, pubkey=pubkey, kind=1, created_at=10)
    assert store.insert(event) is True
    stored = store.query(kinds=[1], pubkeys=[pubkey])
    assert stored[0]["event_id"] == event["event_id"]
