from __future__ import annotations

from aether_relay.bloom import BloomFilter
from aether_relay.storage import InMemoryEventStore


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


def test_immutable_events_store_multiple() -> None:
    store = InMemoryEventStore()
    pubkey = b"\x01" * 32
    event_a = _event(event_id=b"\x10" * 32, pubkey=pubkey, kind=1, created_at=10)
    event_b = _event(event_id=b"\x11" * 32, pubkey=pubkey, kind=2, created_at=20)

    assert store.insert(event_a) is True
    assert store.insert(event_b) is True

    stored = store.query(kinds=[1, 2])
    assert {entry["event_id"] for entry in stored} == {event_a["event_id"], event_b["event_id"]}


def test_replaceable_events_overwrite_by_pubkey_kind() -> None:
    store = InMemoryEventStore()
    pubkey = b"\x02" * 32
    older = _event(event_id=b"\x20" * 32, pubkey=pubkey, kind=10_000, created_at=100)
    newer = _event(event_id=b"\x21" * 32, pubkey=pubkey, kind=10_000, created_at=200)

    assert store.insert(older) is True
    assert store.insert(newer) is True

    stored = store.query(kinds=[10_000], pubkeys=[pubkey])
    assert len(stored) == 1
    assert stored[0]["event_id"] == newer["event_id"]


def test_replaceable_events_ignore_older_update() -> None:
    store = InMemoryEventStore()
    pubkey = b"\x03" * 32
    newer = _event(event_id=b"\x30" * 32, pubkey=pubkey, kind=10_001, created_at=200)
    older = _event(event_id=b"\x31" * 32, pubkey=pubkey, kind=10_001, created_at=100)

    assert store.insert(newer) is True
    assert store.insert(older) is False

    stored = store.query(kinds=[10_001], pubkeys=[pubkey])
    assert len(stored) == 1
    assert stored[0]["event_id"] == newer["event_id"]


def test_parameterized_events_use_d_tag() -> None:
    store = InMemoryEventStore()
    pubkey = b"\x04" * 32
    alpha = _event(
        event_id=b"\x40" * 32,
        pubkey=pubkey,
        kind=30_000,
        created_at=100,
        tags=[["d", "alpha"]],
    )
    beta = _event(
        event_id=b"\x41" * 32,
        pubkey=pubkey,
        kind=30_000,
        created_at=150,
        tags=[["d", "beta"]],
    )
    alpha_newer = _event(
        event_id=b"\x42" * 32,
        pubkey=pubkey,
        kind=30_000,
        created_at=200,
        tags=[["d", "alpha"]],
    )

    assert store.insert(alpha) is True
    assert store.insert(beta) is True
    assert store.insert(alpha_newer) is True

    stored = store.query(kinds=[30_000], pubkeys=[pubkey])
    assert {entry["event_id"] for entry in stored} == {beta["event_id"], alpha_newer["event_id"]}


def test_ephemeral_events_are_not_stored() -> None:
    store = InMemoryEventStore()
    pubkey = b"\x05" * 32
    event = _event(event_id=b"\x50" * 32, pubkey=pubkey, kind=20_000, created_at=10)

    assert store.insert(event) is False
    assert store.query() == []


def test_immutable_events_respect_retention_window() -> None:
    now = 1_000
    store = InMemoryEventStore(retention_ns=100, now_ns=lambda: now)
    pubkey = b"\x06" * 32
    fresh = _event(event_id=b"\x60" * 32, pubkey=pubkey, kind=1, created_at=950)
    stale = _event(event_id=b"\x61" * 32, pubkey=pubkey, kind=2, created_at=800)

    assert store.insert(stale) is False
    assert store.insert(fresh) is True

    stored = store.query(kinds=[1, 2])
    assert [entry["event_id"] for entry in stored] == [fresh["event_id"]]


def test_query_filters_by_tags() -> None:
    store = InMemoryEventStore()
    pubkey = b"\x07" * 32
    event_a = _event(
        event_id=b"\x70" * 32,
        pubkey=pubkey,
        kind=1,
        created_at=10,
        tags=[["c", "alpha"]],
    )
    event_b = _event(
        event_id=b"\x71" * 32,
        pubkey=pubkey,
        kind=1,
        created_at=20,
        tags=[["c", "beta"]],
    )

    assert store.insert(event_a) is True
    assert store.insert(event_b) is True

    results = store.query(tags=[("c", "alpha")])
    assert [entry["event_id"] for entry in results] == [event_a["event_id"]]


def test_replaceable_updates_tag_indexes() -> None:
    store = InMemoryEventStore()
    pubkey = b"\x08" * 32
    older = _event(
        event_id=b"\x80" * 32,
        pubkey=pubkey,
        kind=10_000,
        created_at=100,
        tags=[["c", "alpha"]],
    )
    newer = _event(
        event_id=b"\x81" * 32,
        pubkey=pubkey,
        kind=10_000,
        created_at=200,
        tags=[["c", "beta"]],
    )

    assert store.insert(older) is True
    assert store.insert(newer) is True

    assert store.query(tags=[("c", "alpha")]) == []
    results = store.query(tags=[("c", "beta")])
    assert [entry["event_id"] for entry in results] == [newer["event_id"]]


def test_bloom_filter_rejects_duplicates() -> None:
    bloom = BloomFilter(size_bits=128, hash_count=3)
    store = InMemoryEventStore(bloom=bloom)
    pubkey = b"\x09" * 32
    event = _event(event_id=b"\x90" * 32, pubkey=pubkey, kind=1, created_at=10)

    assert store.insert(event) is True
    assert store.insert(event) is False
