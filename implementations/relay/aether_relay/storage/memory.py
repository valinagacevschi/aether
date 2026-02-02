"""In-memory event storage for Aether relay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from ..crypto import Tag, normalize_tags

IMMUTABLE_RANGE = range(0, 1000)
REPLACEABLE_RANGE = range(10_000, 20_000)
EPHEMERAL_RANGE = range(20_000, 30_000)
PARAMETERIZED_RANGE = range(30_000, 40_000)


@dataclass(frozen=True)
class StoredEvent:
    event: dict[str, object]
    event_id: bytes
    pubkey: bytes
    kind: int
    created_at: int
    d_tag: str


class InMemoryEventStore:
    def __init__(self) -> None:
        self._immutable: dict[bytes, StoredEvent] = {}
        self._replaceable: dict[tuple[bytes, int], StoredEvent] = {}
        self._parameterized: dict[tuple[bytes, int, str], StoredEvent] = {}

    def insert(self, event: Mapping[str, object]) -> bool:
        stored = _normalize_event(event)
        kind = stored.kind

        if kind in EPHEMERAL_RANGE:
            return False
        if kind in IMMUTABLE_RANGE:
            if stored.event_id in self._immutable:
                return False
            self._immutable[stored.event_id] = stored
            return True
        if kind in REPLACEABLE_RANGE:
            key = (stored.pubkey, stored.kind)
            existing = self._replaceable.get(key)
            if existing and stored.created_at <= existing.created_at:
                return False
            self._replaceable[key] = stored
            return True
        if kind in PARAMETERIZED_RANGE:
            key = (stored.pubkey, stored.kind, stored.d_tag)
            existing = self._parameterized.get(key)
            if existing and stored.created_at <= existing.created_at:
                return False
            self._parameterized[key] = stored
            return True

        raise ValueError("kind out of supported range")

    def query(
        self,
        *,
        kinds: Iterable[int] | None = None,
        pubkeys: Iterable[bytes | str] | None = None,
    ) -> list[Mapping[str, object]]:
        kind_set = set(kinds) if kinds is not None else None
        pubkey_set = (
            {_parse_hex_or_bytes(value, "pubkey", 32) for value in pubkeys}
            if pubkeys is not None
            else None
        )

        events = [*self._immutable.values(), *self._replaceable.values(), *self._parameterized.values()]
        result: list[Mapping[str, object]] = []
        for stored in events:
            if kind_set is not None and stored.kind not in kind_set:
                continue
            if pubkey_set is not None and stored.pubkey not in pubkey_set:
                continue
            result.append(stored.event)
        return result


def _normalize_event(event: Mapping[str, object]) -> StoredEvent:
    event_id = _parse_hex_or_bytes(event.get("event_id"), "event_id", 32)
    pubkey = _parse_hex_or_bytes(event.get("pubkey"), "pubkey", 32)
    kind = _parse_int(event.get("kind"), "kind")
    created_at = _parse_int(event.get("created_at"), "created_at")
    tags = normalize_tags(_parse_tags(event.get("tags")))
    d_tag = _extract_d_tag(tags)

    normalized = dict(event)
    normalized["event_id"] = event_id
    normalized["pubkey"] = pubkey
    normalized["kind"] = kind
    normalized["created_at"] = created_at
    normalized["tags"] = tags

    return StoredEvent(
        event=normalized,
        event_id=event_id,
        pubkey=pubkey,
        kind=kind,
        created_at=created_at,
        d_tag=d_tag,
    )


def _extract_d_tag(tags: Sequence[Tag]) -> str:
    for tag in tags:
        if tag.key == "d" and tag.values:
            return tag.values[0]
    return ""


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
