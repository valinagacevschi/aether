from __future__ import annotations

from aether_relay.storage import SQLiteEventStore


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


def test_sqlite_insert_and_query(tmp_path) -> None:
    store = SQLiteEventStore(tmp_path / "events.db")
    pubkey = b"\x01" * 32
    event = _event(
        event_id=b"\x10" * 32,
        pubkey=pubkey,
        kind=1,
        created_at=10,
        tags=[["c", "alpha"]],
    )
    assert store.insert(event) is True
    stored = store.query(kinds=[1], pubkeys=[pubkey])
    assert stored[0]["event_id"] == event["event_id"]
    tagged = store.query(tags=[("c", "alpha")])
    assert tagged[0]["event_id"] == event["event_id"]
    store.close()


def test_sqlite_replaceable_overwrite(tmp_path) -> None:
    store = SQLiteEventStore(tmp_path / "events.db")
    pubkey = b"\x02" * 32
    older = _event(event_id=b"\x20" * 32, pubkey=pubkey, kind=10_000, created_at=10)
    newer = _event(event_id=b"\x21" * 32, pubkey=pubkey, kind=10_000, created_at=20)

    assert store.insert(older) is True
    assert store.insert(newer) is True
    stored = store.query(kinds=[10_000], pubkeys=[pubkey])
    assert len(stored) == 1
    assert stored[0]["event_id"] == newer["event_id"]
    store.close()
