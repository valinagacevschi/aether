"""Capability token helpers for the Python SDK."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Mapping

from blake3 import blake3

from .crypto import sign as sign_event_id
from .crypto import verify as verify_event_id


@dataclass(frozen=True)
class CapabilityToken:
    issuer: bytes
    subject: bytes
    capability: str
    caveats: Mapping[str, object]
    sig: bytes


def compute_token_id(token: CapabilityToken) -> bytes:
    payload = _serialize_payload(token)
    return blake3(payload).digest()


def sign_token(
    *, issuer_private_key: bytes, subject: bytes, capability: str, caveats: Mapping[str, object]
) -> CapabilityToken:
    token = CapabilityToken(
        issuer=_parse_hex_or_bytes(issuer_private_key, "issuer", 32),
        subject=_parse_hex_or_bytes(subject, "subject", 32),
        capability=capability,
        caveats=caveats,
        sig=b"",
    )
    token_id = compute_token_id(token)
    sig = sign_event_id(token_id, issuer_private_key)
    return CapabilityToken(
        issuer=token.issuer,
        subject=token.subject,
        capability=token.capability,
        caveats=token.caveats,
        sig=sig,
    )


def verify_chain(
    tokens: Iterable[CapabilityToken],
    *,
    now_ns: int,
    usage: Mapping[bytes, int] | None = None,
) -> None:
    chain = list(tokens)
    if not chain:
        raise ValueError("empty capability chain")

    for idx, token in enumerate(chain):
        token_id = compute_token_id(token)
        if not verify_event_id(token_id, token.sig, token.issuer):
            raise ValueError("invalid capability signature")

        _enforce_caveats(token, now_ns, usage or {})

        if idx + 1 < len(chain):
            next_token = chain[idx + 1]
            if token.subject != next_token.issuer:
                raise ValueError("capability chain subject mismatch")


def _enforce_caveats(
    token: CapabilityToken,
    now_ns: int,
    usage: Mapping[bytes, int],
) -> None:
    caveats = token.caveats or {}
    not_before = _parse_optional_int(caveats.get("not_before"))
    not_after = _parse_optional_int(caveats.get("not_after"))
    max_uses = _parse_optional_int(caveats.get("max_uses"))

    if not_before is not None and now_ns < not_before:
        raise ValueError("capability not yet valid")
    if not_after is not None and now_ns > not_after:
        raise ValueError("capability expired")
    if max_uses is not None:
        token_id = compute_token_id(token)
        if usage.get(token_id, 0) >= max_uses:
            raise ValueError("capability usage exceeded")


def _serialize_payload(token: CapabilityToken) -> bytes:
    payload = {
        "issuer": token.issuer.hex(),
        "subject": token.subject.hex(),
        "capability": token.capability,
        "caveats": token.caveats,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _parse_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("caveat must be int")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError("caveat must be int") from exc
    raise ValueError("caveat must be int")


def _parse_hex_or_bytes(value: object, field: str, size: int) -> bytes:
    if isinstance(value, bytes):
        data = value
    elif isinstance(value, str):
        try:
            data = bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError(f"{field} must be hex") from exc
    else:
        raise ValueError(f"{field} must be bytes or hex string")

    if len(data) != size:
        raise ValueError(f"{field} must be {size} bytes")
    return data
