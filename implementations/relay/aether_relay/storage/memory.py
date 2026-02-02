"""In-memory event storage for Aether relay."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable, Iterable, Mapping, Sequence

from ..bloom import BloomFilter
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
    tags: tuple[Tag, ...]


class InMemoryEventStore:
    def __init__(
        self,
        *,
        retention_ns: int | None = None,
        now_ns: Callable[[], int] = time.time_ns,
        bloom: BloomFilter | None = None,
    ) -> None:
        self._immutable: dict[bytes, StoredEvent] = {}
        self._replaceable: dict[tuple[bytes, int], StoredEvent] = {}
        self._parameterized: dict[tuple[bytes, int, str], StoredEvent] = {}
        self._by_id: dict[bytes, StoredEvent] = {}
        self._index_pubkey: dict[bytes, set[bytes]] = {}
        self._index_kind: dict[int, set[bytes]] = {}
        self._index_tag: dict[tuple[str, str], set[bytes]] = {}
        self._retention_ns = retention_ns
        self._now_ns = now_ns
        self._bloom = bloom

    def insert(self, event: Mapping[str, object]) -> bool:
        stored = _normalize_event(event)
        kind = stored.kind

        if kind in EPHEMERAL_RANGE:
            return False
        if self._bloom and self._bloom.might_contain(stored.event_id):
            if stored.event_id in self._by_id:
                return False
        if kind in IMMUTABLE_RANGE:
            self._prune_expired()
            if self._is_expired(stored):
                return False
            if stored.event_id in self._immutable:
                return False
            self._immutable[stored.event_id] = stored
            self._add_indexes(stored)
            if self._bloom:
                self._bloom.add(stored.event_id)
            return True
        if kind in REPLACEABLE_RANGE:
            replaceable_key = (stored.pubkey, stored.kind)
            existing = self._replaceable.get(replaceable_key)
            if existing and stored.created_at <= existing.created_at:
                return False
            if existing:
                self._remove_indexes(existing)
            self._replaceable[replaceable_key] = stored
            self._add_indexes(stored)
            if self._bloom:
                self._bloom.add(stored.event_id)
            return True
        if kind in PARAMETERIZED_RANGE:
            parameterized_key = (stored.pubkey, stored.kind, stored.d_tag)
            existing = self._parameterized.get(parameterized_key)
            if existing and stored.created_at <= existing.created_at:
                return False
            if existing:
                self._remove_indexes(existing)
            self._parameterized[parameterized_key] = stored
            self._add_indexes(stored)
            if self._bloom:
                self._bloom.add(stored.event_id)
            return True

        raise ValueError("kind out of supported range")

    def query(
        self,
        *,
        kinds: Iterable[int] | None = None,
        pubkeys: Iterable[bytes | str] | None = None,
        tags: Iterable[tuple[str, str]] | None = None,
        since: int | None = None,
        until: int | None = None,
    ) -> list[Mapping[str, object]]:
        self._prune_expired()
        kind_set = set(kinds) if kinds is not None else None
        pubkey_set = (
            {_parse_hex_or_bytes(value, "pubkey", 32) for value in pubkeys}
            if pubkeys is not None
            else None
        )
        tag_set = set(tags) if tags is not None else None

        event_ids = self._candidate_ids(kind_set, pubkey_set, tag_set)
        events = [self._by_id[event_id] for event_id in event_ids] if event_ids is not None else [
            *self._immutable.values(),
            *self._replaceable.values(),
            *self._parameterized.values(),
        ]
        result: list[Mapping[str, object]] = []
        for stored in events:
            if kind_set is not None and stored.kind not in kind_set:
                continue
            if pubkey_set is not None and stored.pubkey not in pubkey_set:
                continue
            if tag_set is not None and not _event_has_tags(stored.tags, tag_set):
                continue
            if since is not None and stored.created_at < since:
                continue
            if until is not None and stored.created_at > until:
                continue
            result.append(stored.event)
        return result

    def _is_expired(self, stored: StoredEvent) -> bool:
        if self._retention_ns is None:
            return False
        return (self._now_ns() - stored.created_at) > self._retention_ns

    def _prune_expired(self) -> None:
        if self._retention_ns is None:
            return
        expired = [event_id for event_id, stored in self._immutable.items() if self._is_expired(stored)]
        for event_id in expired:
            stored = self._immutable.pop(event_id, None)
            if stored:
                self._remove_indexes(stored)

    def _candidate_ids(
        self,
        kind_set: set[int] | None,
        pubkey_set: set[bytes] | None,
        tag_set: set[tuple[str, str]] | None,
    ) -> set[bytes] | None:
        candidates: set[bytes] | None = None
        if kind_set:
            candidates = set()
            for kind in kind_set:
                candidates |= self._index_kind.get(kind, set())
        if pubkey_set:
            pubkey_ids: set[bytes] = set()
            for pubkey in pubkey_set:
                pubkey_ids |= self._index_pubkey.get(pubkey, set())
            candidates = pubkey_ids if candidates is None else candidates & pubkey_ids
        if tag_set:
            tag_ids: set[bytes] | None = None
            for tag in tag_set:
                ids = self._index_tag.get(tag, set())
                tag_ids = ids if tag_ids is None else tag_ids & ids
            candidates = tag_ids if candidates is None else candidates & (tag_ids or set())
        return candidates

    def _add_indexes(self, stored: StoredEvent) -> None:
        self._by_id[stored.event_id] = stored
        self._index_pubkey.setdefault(stored.pubkey, set()).add(stored.event_id)
        self._index_kind.setdefault(stored.kind, set()).add(stored.event_id)
        for tag in stored.tags:
            for value in tag.values:
                self._index_tag.setdefault((tag.key, value), set()).add(stored.event_id)

    def _remove_indexes(self, stored: StoredEvent) -> None:
        self._by_id.pop(stored.event_id, None)
        self._discard_index(self._index_pubkey, stored.pubkey, stored.event_id)
        self._discard_index(self._index_kind, stored.kind, stored.event_id)
        for tag in stored.tags:
            for value in tag.values:
                self._discard_index(self._index_tag, (tag.key, value), stored.event_id)

    @staticmethod
    def _discard_index(
        index: dict[object, set[bytes]],
        key: object,
        event_id: bytes,
    ) -> None:
        bucket = index.get(key)
        if not bucket:
            return
        bucket.discard(event_id)
        if not bucket:
            index.pop(key, None)


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
        tags=tuple(tags),
    )


def _extract_d_tag(tags: Sequence[Tag]) -> str:
    for tag in tags:
        if tag.key == "d" and tag.values:
            return tag.values[0]
    return ""


def _event_has_tags(tags: Sequence[Tag], required: set[tuple[str, str]]) -> bool:
    if not required:
        return True
    available = {(tag.key, value) for tag in tags for value in tag.values}
    return required.issubset(available)


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
