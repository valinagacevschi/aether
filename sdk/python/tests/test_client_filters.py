from __future__ import annotations

from aether.filters import match_event, normalize_filter


def test_filter_matches_event() -> None:
    flt = normalize_filter({"kinds": [1], "tags": [("c", "alpha")]})
    event = {
        "pubkey": b"\x01" * 32,
        "kind": 1,
        "created_at": 10,
        "tags": [["c", "alpha"]],
        "content": "",
    }
    assert match_event(event, flt) is True
