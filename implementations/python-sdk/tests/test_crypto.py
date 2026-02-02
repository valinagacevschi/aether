from __future__ import annotations

from aether.crypto import compute_event_id, event_id_from_dict, generate_keypair, sign, verify
from aether.keys import decode_private_bech32, decode_public_bech32, encode_private_bech32, encode_public_bech32


def test_sign_and_verify_roundtrip() -> None:
    private_key, public_key = generate_keypair()
    event_id = compute_event_id(
        pubkey=public_key,
        created_at=1,
        kind=1,
        tags=[],
        content=b"hello",
    )
    sig = sign(event_id, private_key)
    assert verify(event_id, sig, public_key) is True


def test_event_id_from_dict_matches_compute() -> None:
    event = {
        "pubkey": b"\x01" * 32,
        "created_at": 1,
        "kind": 1,
        "tags": [],
        "content": "hello",
    }
    event_id = event_id_from_dict(event)
    direct = compute_event_id(
        pubkey=event["pubkey"],
        created_at=event["created_at"],
        kind=event["kind"],
        tags=[],
        content=b"hello",
    )
    assert event_id == direct


def test_bech32_public_roundtrip() -> None:
    _, public_key = generate_keypair()
    encoded = encode_public_bech32(public_key)
    decoded = decode_public_bech32(encoded)
    assert decoded == public_key


def test_bech32_private_roundtrip() -> None:
    private_key, _ = generate_keypair()
    encoded = encode_private_bech32(private_key)
    decoded = decode_private_bech32(encoded)
    assert decoded == private_key
