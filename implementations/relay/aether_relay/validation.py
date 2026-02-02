"""Event validation helpers for Aether relay."""

from __future__ import annotations

import time
from typing import Mapping

from .crypto import compute_event_id, normalize_tags, verify
from .limits import RateLimiter, enforce_max_size
from .pow import validate_pow

WINDOW_NS = 60_000_000_000
MAX_KIND = 39_999


def validate_event(
    event: Mapping[str, object],
    *,
    now_ns: int | None = None,
    window_ns: int = WINDOW_NS,
    rate_limiter: RateLimiter | None = None,
    max_size: int | None = None,
    pow_difficulty: int | None = None,
) -> None:
    """Validate an event or raise ValueError."""

    pubkey = _parse_hex_or_bytes(event.get("pubkey"), "pubkey", 32)
    event_id = _parse_hex_or_bytes(event.get("event_id"), "event_id", 32)
    sig = _parse_hex_or_bytes(event.get("sig"), "sig", 64)
    created_at = _parse_int(event.get("created_at"), "created_at")
    kind = _parse_int(event.get("kind"), "kind")
    tags = normalize_tags(_parse_tags(event.get("tags")))
    content = _parse_content(event.get("content"))

    if kind < 0 or kind > MAX_KIND:
        raise ValueError("kind out of range")
    if max_size is not None:
        enforce_max_size(event, max_size)

    computed = compute_event_id(
        pubkey=pubkey,
        created_at=created_at,
        kind=kind,
        tags=tags,
        content=content,
    )
    if computed != event_id:
        raise ValueError("event_id mismatch")
    if not verify(event_id, sig, pubkey):
        raise ValueError("invalid signature")
    if pow_difficulty is not None:
        validate_pow(event_id, pow_difficulty)

    now = time.time_ns() if now_ns is None else now_ns
    if abs(created_at - now) > window_ns:
        raise ValueError("created_at outside allowed window")
    if rate_limiter is not None and not rate_limiter.allow(pubkey):
        raise ValueError("rate limit exceeded")


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


def _parse_int(value: object, field: str) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field} must be int")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"{field} must be int") from exc
    raise ValueError(f"{field} must be int")


def _parse_tags(value: object) -> list[object]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError("tags must be a list")
    return list(value)


def _parse_content(value: object) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    raise ValueError("content must be bytes or string")
