"""Rate limiting and size checks for relay events."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Mapping

from .crypto import normalize_tags
from .crypto import _serialize_tags  # type: ignore[attr-defined]


@dataclass
class TokenBucket:
    capacity: int
    refill_per_second: float
    tokens: float
    updated_ns: int

    def refill(self, now_ns: int) -> None:
        delta = (now_ns - self.updated_ns) / 1_000_000_000
        if delta <= 0:
            return
        self.tokens = min(self.capacity, self.tokens + delta * self.refill_per_second)
        self.updated_ns = now_ns

    def consume(self, now_ns: int, amount: float = 1.0) -> bool:
        self.refill(now_ns)
        if self.tokens < amount:
            return False
        self.tokens -= amount
        return True


class RateLimiter:
    def __init__(
        self,
        *,
        capacity: int,
        refill_per_second: float,
        now_ns: Callable[[], int] = time.time_ns,
    ) -> None:
        self._capacity = capacity
        self._refill_per_second = refill_per_second
        self._now_ns = now_ns
        self._buckets: dict[bytes, TokenBucket] = {}

    def allow(self, pubkey: bytes) -> bool:
        now = self._now_ns()
        bucket = self._buckets.get(pubkey)
        if bucket is None:
            bucket = TokenBucket(
                capacity=self._capacity,
                refill_per_second=self._refill_per_second,
                tokens=float(self._capacity),
                updated_ns=now,
            )
            self._buckets[pubkey] = bucket
        return bucket.consume(now)


def compute_event_size(event: Mapping[str, object]) -> int:
    pubkey = _parse_hex_or_bytes(event.get("pubkey"), "pubkey", 32)
    event_id = _parse_hex_or_bytes(event.get("event_id"), "event_id", 32)
    sig = _parse_hex_or_bytes(event.get("sig"), "sig", 64)
    created_at = _parse_int(event.get("created_at"), "created_at")
    kind = _parse_int(event.get("kind"), "kind")
    tags = normalize_tags(_parse_tags(event.get("tags")))
    content = _parse_content(event.get("content"))

    size = 0
    size += len(event_id)
    size += len(pubkey)
    size += 8  # created_at
    size += 2  # kind
    size += len(_serialize_tags(tags))
    size += len(content)
    size += len(sig)
    return size


def enforce_max_size(event: Mapping[str, object], max_bytes: int) -> None:
    if compute_event_size(event) > max_bytes:
        raise ValueError("event exceeds maximum size")


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
