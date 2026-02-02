"""Key import/export helpers for Aether."""

from __future__ import annotations

from bech32 import bech32_decode, bech32_encode, convertbits


BECH32_PRIV_PREFIX = "nsec"
BECH32_PUB_PREFIX = "npub"


def encode_hex(data: bytes) -> str:
    return data.hex()


def decode_hex(value: str) -> bytes:
    return bytes.fromhex(value)


def encode_bech32(data: bytes, *, prefix: str) -> str:
    five_bits = convertbits(data, 8, 5, True)
    if five_bits is None:
        raise ValueError("failed to convert to bech32")
    return bech32_encode(prefix, five_bits)


def decode_bech32(value: str) -> tuple[str, bytes]:
    hrp, data = bech32_decode(value)
    if hrp is None or data is None:
        raise ValueError("invalid bech32")
    eight_bits = convertbits(data, 5, 8, False)
    if eight_bits is None:
        raise ValueError("invalid bech32 payload")
    return hrp, bytes(eight_bits)


def encode_private_bech32(data: bytes) -> str:
    return encode_bech32(data, prefix=BECH32_PRIV_PREFIX)


def encode_public_bech32(data: bytes) -> str:
    return encode_bech32(data, prefix=BECH32_PUB_PREFIX)


def decode_private_bech32(value: str) -> bytes:
    hrp, payload = decode_bech32(value)
    if hrp != BECH32_PRIV_PREFIX:
        raise ValueError("invalid bech32 private key prefix")
    return payload


def decode_public_bech32(value: str) -> bytes:
    hrp, payload = decode_bech32(value)
    if hrp != BECH32_PUB_PREFIX:
        raise ValueError("invalid bech32 public key prefix")
    return payload
