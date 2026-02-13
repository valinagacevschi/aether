from __future__ import annotations

from aether_relay.gateways.common import nostr_filter_to_aether


def test_filter_mapping_parity() -> None:
    raw = {
        "kinds": [1, 2],
        "authors": ["abcd"],
        "since": 1,
        "until": 9,
        "#t": ["alpha", "beta"],
    }
    mapped = nostr_filter_to_aether(raw)
    assert mapped["kinds"] == [1, 2]
    assert mapped["since"] == 1
    assert mapped["until"] == 9
    assert mapped["pubkey_prefixes"] == ["abcd".ljust(32, "0")]
    assert set(mapped["tags"]) == {("t", "alpha"), ("t", "beta")}
