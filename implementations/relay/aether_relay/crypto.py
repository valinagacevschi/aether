"""Cryptographic helpers for Aether events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from blake3 import blake3
from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey


@dataclass(frozen=True)
class Tag:
    key: str
    values: tuple[str, ...]


def generate_keypair() -> tuple[bytes, bytes]:
    """Return (private_key, public_key)."""

    signing_key = SigningKey.generate()
    return signing_key.encode(), signing_key.verify_key.encode()


def compute_event_id(
    *,
    pubkey: bytes,
    created_at: int,
    kind: int,
    tags: Sequence[Tag],
    content: bytes,
) -> bytes:
    """Compute the Blake3 event_id for canonical event serialization."""

    _validate_pubkey(pubkey)
    _validate_created_at(created_at)
    _validate_kind(kind)

    payload = bytearray()
    payload += pubkey
    payload += created_at.to_bytes(8, "big")
    payload += kind.to_bytes(2, "big")
    payload += _serialize_tags(tags)
    payload += content
    return blake3(payload).digest()


def sign(event_id: bytes, private_key: bytes) -> bytes:
    """Sign an event_id with an Ed25519 private key."""

    _validate_event_id(event_id)
    signing_key = SigningKey(private_key)
    signed = signing_key.sign(event_id)
    return signed.signature


def verify(event_id: bytes, sig: bytes, pubkey: bytes) -> bool:
    """Verify an Ed25519 signature for an event_id."""

    _validate_event_id(event_id)
    _validate_signature(sig)
    _validate_pubkey(pubkey)

    verify_key = VerifyKey(pubkey)
    try:
        verify_key.verify(event_id, sig)
    except BadSignatureError:
        return False
    return True


def _serialize_tags(tags: Sequence[Tag]) -> bytes:
    if len(tags) > 0xFFFF:
        raise ValueError("tags exceeds uint16 length")

    output = bytearray()
    output += len(tags).to_bytes(2, "big")
    for tag in tags:
        key_bytes = tag.key.encode("ascii")
        if not key_bytes:
            raise ValueError("tag key cannot be empty")
        if len(key_bytes) > 0xFF:
            raise ValueError("tag key exceeds uint8 length")
        output += len(key_bytes).to_bytes(1, "big")
        output += key_bytes

        if len(tag.values) > 0xFFFF:
            raise ValueError("tag values exceeds uint16 length")
        output += len(tag.values).to_bytes(2, "big")
        for value in tag.values:
            value_bytes = value.encode("utf-8")
            if len(value_bytes) > 0xFFFF:
                raise ValueError("tag value exceeds uint16 length")
            output += len(value_bytes).to_bytes(2, "big")
            output += value_bytes

    return bytes(output)


def _validate_event_id(event_id: bytes) -> None:
    if len(event_id) != 32:
        raise ValueError("event_id must be 32 bytes")


def _validate_signature(sig: bytes) -> None:
    if len(sig) != 64:
        raise ValueError("sig must be 64 bytes")


def _validate_pubkey(pubkey: bytes) -> None:
    if len(pubkey) != 32:
        raise ValueError("pubkey must be 32 bytes")


def _validate_created_at(created_at: int) -> None:
    if created_at < 0 or created_at > 0xFFFFFFFFFFFFFFFF:
        raise ValueError("created_at must be uint64")


def _validate_kind(kind: int) -> None:
    if kind < 0 or kind > 0xFFFF:
        raise ValueError("kind must be uint16")


def normalize_tags(raw_tags: Iterable[object]) -> list[Tag]:
    """Normalize tag data into Tag objects.

    Accepts Tag, mapping with keys "key"/"values", or list where the
    first element is the key and remaining elements are values.
    """

    normalized: list[Tag] = []
    for raw_tag in raw_tags:
        if isinstance(raw_tag, Tag):
            normalized.append(raw_tag)
            continue

        if isinstance(raw_tag, dict):
            key = raw_tag.get("key")
            values = raw_tag.get("values", [])
        elif isinstance(raw_tag, (list, tuple)) and raw_tag:
            key = raw_tag[0]
            values = list(raw_tag[1:])
        else:
            raise ValueError("Unsupported tag format")

        if not isinstance(key, str):
            raise ValueError("Tag key must be a string")
        if not isinstance(values, (list, tuple)):
            raise ValueError("Tag values must be a list")
        normalized.append(Tag(key=key, values=tuple(str(v) for v in values)))

    return normalized
