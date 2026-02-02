from __future__ import annotations

from aether_relay.filters import match_event, normalize_filter


def _event(*, kind: int, pubkey: bytes, created_at: int, tags: list[list[str]] | None = None) -> dict[str, object]:
    return {
        "event_id": b"\x00" * 32,
        "pubkey": pubkey,
        "kind": kind,
        "created_at": created_at,
        "tags": tags or [],
        "content": "",
        "sig": b"\x00" * 64,
    }


def test_match_kind_and_time_range() -> None:
    event = _event(kind=1, pubkey=b"\x01" * 32, created_at=100)
    flt = normalize_filter({"kinds": [1], "since": 50, "until": 150})
    assert match_event(event, flt) is True

    flt = normalize_filter({"kinds": [2]})
    assert match_event(event, flt) is False

    flt = normalize_filter({"since": 200})
    assert match_event(event, flt) is False


def test_match_pubkey_prefix() -> None:
    pubkey = b"\x02" * 32
    event = _event(kind=1, pubkey=pubkey, created_at=10)
    prefix = pubkey[:16]
    flt = normalize_filter({"pubkey_prefixes": [prefix]})
    assert match_event(event, flt) is True

    flt = normalize_filter({"pubkey_prefixes": [b"\x03" * 16]})
    assert match_event(event, flt) is False


def test_match_tags() -> None:
    event = _event(
        kind=1,
        pubkey=b"\x03" * 32,
        created_at=10,
        tags=[["c", "alpha"], ["d", "beta"]],
    )
    flt = normalize_filter({"tags": [("c", "alpha")]})
    assert match_event(event, flt) is True

    flt = normalize_filter({"tags": [("c", "missing")]})
    assert match_event(event, flt) is False

    flt = normalize_filter({"tags": {"d": ["beta"]}})
    assert match_event(event, flt) is True
