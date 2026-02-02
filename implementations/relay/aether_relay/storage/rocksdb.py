"""RocksDB storage backend for the relay."""

from __future__ import annotations

import json
from typing import Iterable, Mapping

from ..crypto import normalize_tags
from .memory import (
    EPHEMERAL_RANGE,
    IMMUTABLE_RANGE,
    PARAMETERIZED_RANGE,
    REPLACEABLE_RANGE,
    _extract_d_tag,
    _parse_hex_or_bytes,
    _parse_int,
    _parse_tags,
)


class RocksDBEventStore:
    def __init__(self, path: str) -> None:
        try:
            import rocksdb  # type: ignore
        except Exception as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError("python-rocksdb is required") from exc

        self._rocksdb = rocksdb
        self._db = rocksdb.DB(path, rocksdb.Options(create_if_missing=True))

    def insert(self, event: Mapping[str, object]) -> bool:
        normalized = _normalize_event(event)
        if normalized.kind in EPHEMERAL_RANGE:
            return False
        if normalized.kind in IMMUTABLE_RANGE:
            if self._exists_event_id(normalized.event_id):
                return False
            self._write_event(normalized)
            return True
        if normalized.kind in REPLACEABLE_RANGE:
            existing = self._find_replaceable(normalized.pubkey, normalized.kind)
            if existing and existing["created_at"] >= normalized.created_at:
                return False
            if existing:
                self._delete_event(existing["event_id"])
            self._write_event(normalized)
            return True
        if normalized.kind in PARAMETERIZED_RANGE:
            existing = self._find_parameterized(normalized.pubkey, normalized.kind, normalized.d_tag)
            if existing and existing["created_at"] >= normalized.created_at:
                return False
            if existing:
                self._delete_event(existing["event_id"])
            self._write_event(normalized)
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
        events = [self._decode_event(value) for _key, value in self._db.iterator(prefix=b"e:")]
        kind_set = set(kinds) if kinds is not None else None
        pubkey_set = (
            {_parse_hex_or_bytes(value, "pubkey", 32) for value in pubkeys}
            if pubkeys is not None
            else None
        )
        tag_set = set(tags) if tags is not None else None

        result: list[Mapping[str, object]] = []
        for event in events:
            if kind_set is not None and event["kind"] not in kind_set:
                continue
            if pubkey_set is not None and event["pubkey"] not in pubkey_set:
                continue
            if since is not None and event["created_at"] < since:
                continue
            if until is not None and event["created_at"] > until:
                continue
            if tag_set is not None and not _event_has_tags(event, tag_set):
                continue
            result.append(event)
        return result

    def _write_event(self, event: _StoredEvent) -> None:
        batch = self._rocksdb.WriteBatch()
        batch.put(b"e:" + event.event_id, _encode_event(event))
        batch.put(_replaceable_key(event.pubkey, event.kind), event.event_id)
        if event.d_tag:
            batch.put(_parameterized_key(event.pubkey, event.kind, event.d_tag), event.event_id)
        for tag in event.tags:
            for value in tag.values:
                batch.put(_tag_index_key(tag.key, value, event.event_id), b"1")
        self._db.write(batch)

    def _delete_event(self, event_id: bytes) -> None:
        stored = self._db.get(b"e:" + event_id)
        if stored is None:
            return
        event = self._decode_event(stored)
        batch = self._rocksdb.WriteBatch()
        batch.delete(b"e:" + event_id)
        batch.delete(_replaceable_key(event["pubkey"], event["kind"]))
        if event.get("d_tag"):
            batch.delete(_parameterized_key(event["pubkey"], event["kind"], event["d_tag"]))
        for tag in normalize_tags(_parse_tags(event.get("tags"))):
            for value in tag.values:
                batch.delete(_tag_index_key(tag.key, value, event_id))
        self._db.write(batch)

    def _exists_event_id(self, event_id: bytes) -> bool:
        return self._db.get(b"e:" + event_id) is not None

    def _find_replaceable(self, pubkey: bytes, kind: int) -> Mapping[str, object] | None:
        event_id = self._db.get(_replaceable_key(pubkey, kind))
        if not event_id:
            return None
        stored = self._db.get(b"e:" + event_id)
        return self._decode_event(stored) if stored else None

    def _find_parameterized(self, pubkey: bytes, kind: int, d_tag: str) -> Mapping[str, object] | None:
        event_id = self._db.get(_parameterized_key(pubkey, kind, d_tag))
        if not event_id:
            return None
        stored = self._db.get(b"e:" + event_id)
        return self._decode_event(stored) if stored else None

    @staticmethod
    def _decode_event(value: bytes) -> Mapping[str, object]:
        return _decode_event(value)


class _StoredEvent:
    def __init__(
        self,
        *,
        event_id: bytes,
        pubkey: bytes,
        kind: int,
        created_at: int,
        d_tag: str,
        tags: list[object],
        content: bytes,
        sig: bytes,
    ) -> None:
        self.event_id = event_id
        self.pubkey = pubkey
        self.kind = kind
        self.created_at = created_at
        self.d_tag = d_tag
        self.tags = normalize_tags(tags)
        self.raw_tags = tags
        self.content = content
        self.sig = sig


def _normalize_event(event: Mapping[str, object]) -> _StoredEvent:
    event_id = _parse_hex_or_bytes(event.get("event_id"), "event_id", 32)
    pubkey = _parse_hex_or_bytes(event.get("pubkey"), "pubkey", 32)
    kind = _parse_int(event.get("kind"), "kind")
    created_at = _parse_int(event.get("created_at"), "created_at")
    tags = _parse_tags(event.get("tags"))
    d_tag = _extract_d_tag(normalize_tags(tags))
    content = _parse_content(event.get("content"))
    sig = _parse_hex_or_bytes(event.get("sig"), "sig", 64)

    return _StoredEvent(
        event_id=event_id,
        pubkey=pubkey,
        kind=kind,
        created_at=created_at,
        d_tag=d_tag,
        tags=tags,
        content=content,
        sig=sig,
    )


def _encode_event(event: _StoredEvent) -> bytes:
    payload = {
        "event_id": event.event_id.hex(),
        "pubkey": event.pubkey.hex(),
        "kind": event.kind,
        "created_at": event.created_at,
        "d_tag": event.d_tag,
        "tags": event.raw_tags,
        "content": event.content.hex(),
        "sig": event.sig.hex(),
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _decode_event(value: bytes) -> Mapping[str, object]:
    payload = json.loads(value.decode("utf-8"))
    return {
        "event_id": bytes.fromhex(payload["event_id"]),
        "pubkey": bytes.fromhex(payload["pubkey"]),
        "kind": payload["kind"],
        "created_at": payload["created_at"],
        "d_tag": payload.get("d_tag", ""),
        "tags": payload.get("tags", []),
        "content": bytes.fromhex(payload["content"]),
        "sig": bytes.fromhex(payload["sig"]),
    }


def _event_has_tags(event: Mapping[str, object], required: set[tuple[str, str]]) -> bool:
    tags = normalize_tags(_parse_tags(event.get("tags")))
    available = {(tag.key, value) for tag in tags for value in tag.values}
    return required.issubset(available)


def _replaceable_key(pubkey: bytes, kind: int) -> bytes:
    return b"r:" + pubkey + kind.to_bytes(2, "big")


def _parameterized_key(pubkey: bytes, kind: int, d_tag: str) -> bytes:
    return b"p:" + pubkey + kind.to_bytes(2, "big") + d_tag.encode("utf-8")


def _tag_index_key(tag_key: str, tag_value: str, event_id: bytes) -> bytes:
    return b"t:" + tag_key.encode("utf-8") + b":" + tag_value.encode("utf-8") + b":" + event_id


def _parse_content(value: object) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    raise ValueError("content must be bytes or string")
