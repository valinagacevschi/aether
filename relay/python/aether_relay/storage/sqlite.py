"""SQLite storage backend for the relay."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Mapping

from ..crypto import Tag, normalize_tags
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


class SQLiteEventStore:
    def __init__(self, path: str | Path, *, retention_ns: int | None = None) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()
        self._retention_ns = retention_ns

    def insert(self, event: Mapping[str, object]) -> bool:
        normalized = _normalize_event(event)
        if normalized.kind in EPHEMERAL_RANGE:
            return False
        if normalized.kind in IMMUTABLE_RANGE:
            stored = self._insert_immutable(normalized)
            self._prune_if_needed()
            return stored
        if normalized.kind in REPLACEABLE_RANGE:
            return self._insert_replaceable(normalized)
        if normalized.kind in PARAMETERIZED_RANGE:
            return self._insert_parameterized(normalized)
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
        where = []
        params: list[object] = []

        if kinds is not None:
            kinds_list = list(kinds)
            where.append(f"kind IN ({','.join('?' for _ in kinds_list)})")
            params.extend(kinds_list)
        if pubkeys is not None:
            pubkey_list = [_parse_hex_or_bytes(value, "pubkey", 32) for value in pubkeys]
            where.append(f"pubkey IN ({','.join('?' for _ in pubkey_list)})")
            params.extend(pubkey_list)
        if since is not None:
            where.append("created_at >= ?")
            params.append(since)
        if until is not None:
            where.append("created_at <= ?")
            params.append(until)

        base_query = "SELECT event_id, pubkey, kind, created_at, tags, content, sig FROM events"
        if where:
            base_query += " WHERE " + " AND ".join(where)

        rows = self._conn.execute(base_query, params).fetchall()
        events = [_row_to_event(row) for row in rows]
        if tags is None:
            return events

        tag_set = set(tags)
        if not tag_set:
            return events
        return [event for event in events if _event_has_tags(event, tag_set)]

    def _prune_if_needed(self) -> None:
        if self._retention_ns is None:
            return
        import time

        cutoff = time.time_ns() - self._retention_ns
        self._conn.execute(
            "DELETE FROM events WHERE kind BETWEEN ? AND ? AND created_at < ?",
            (IMMUTABLE_RANGE.start, IMMUTABLE_RANGE.stop - 1, cutoff),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id BLOB PRIMARY KEY,
                pubkey BLOB NOT NULL,
                kind INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                d_tag TEXT NOT NULL,
                tags TEXT NOT NULL,
                content BLOB NOT NULL,
                sig BLOB NOT NULL
            );
            CREATE INDEX IF NOT EXISTS events_pubkey_idx ON events(pubkey);
            CREATE INDEX IF NOT EXISTS events_kind_idx ON events(kind);

            CREATE TABLE IF NOT EXISTS event_tags (
                event_id BLOB NOT NULL,
                tag_key TEXT NOT NULL,
                tag_value TEXT NOT NULL,
                FOREIGN KEY(event_id) REFERENCES events(event_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS event_tags_idx ON event_tags(tag_key, tag_value);
            """
        )

    def _insert_immutable(self, event: _StoredEvent) -> bool:
        if self._exists_event_id(event.event_id):
            return False
        self._insert_event(event)
        return True

    def _insert_replaceable(self, event: _StoredEvent) -> bool:
        row = self._conn.execute(
            "SELECT event_id, created_at FROM events WHERE pubkey = ? AND kind = ?",
            (event.pubkey, event.kind),
        ).fetchone()
        if row and row[1] >= event.created_at:
            return False
        if row:
            self._delete_event(row[0])
        self._insert_event(event)
        return True

    def _insert_parameterized(self, event: _StoredEvent) -> bool:
        row = self._conn.execute(
            "SELECT event_id, created_at FROM events WHERE pubkey = ? AND kind = ? AND d_tag = ?",
            (event.pubkey, event.kind, event.d_tag),
        ).fetchone()
        if row and row[1] >= event.created_at:
            return False
        if row:
            self._delete_event(row[0])
        self._insert_event(event)
        return True

    def _exists_event_id(self, event_id: bytes) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        return row is not None

    def _insert_event(self, event: _StoredEvent) -> None:
        self._conn.execute(
            """
            INSERT INTO events (event_id, pubkey, kind, created_at, d_tag, tags, content, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.pubkey,
                event.kind,
                event.created_at,
                event.d_tag,
                json.dumps(event.raw_tags),
                event.content,
                event.sig,
            ),
        )
        self._conn.executemany(
            "INSERT INTO event_tags (event_id, tag_key, tag_value) VALUES (?, ?, ?)",
            [(event.event_id, tag.key, value) for tag in event.tags for value in tag.values],
        )
        self._conn.commit()

    def _delete_event(self, event_id: bytes) -> None:
        self._conn.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
        self._conn.commit()


class _StoredEvent:
    def __init__(
        self,
        *,
        event_id: bytes,
        pubkey: bytes,
        kind: int,
        created_at: int,
        d_tag: str,
        tags: list[Tag],
        raw_tags: list[object],
        content: bytes,
        sig: bytes,
    ) -> None:
        self.event_id = event_id
        self.pubkey = pubkey
        self.kind = kind
        self.created_at = created_at
        self.d_tag = d_tag
        self.tags = tags
        self.raw_tags = raw_tags
        self.content = content
        self.sig = sig


def _normalize_event(event: Mapping[str, object]) -> _StoredEvent:
    event_id = _parse_hex_or_bytes(event.get("event_id"), "event_id", 32)
    pubkey = _parse_hex_or_bytes(event.get("pubkey"), "pubkey", 32)
    kind = _parse_int(event.get("kind"), "kind")
    created_at = _parse_int(event.get("created_at"), "created_at")
    raw_tags = _parse_tags(event.get("tags"))
    tags = normalize_tags(raw_tags)
    d_tag = _extract_d_tag(tags)
    content = _parse_content(event.get("content"))
    sig = _parse_hex_or_bytes(event.get("sig"), "sig", 64)

    return _StoredEvent(
        event_id=event_id,
        pubkey=pubkey,
        kind=kind,
        created_at=created_at,
        d_tag=d_tag,
        tags=tags,
        raw_tags=raw_tags,
        content=content,
        sig=sig,
    )


def _row_to_event(row: tuple[object, ...]) -> dict[str, object]:
    event_id, pubkey, kind, created_at, tags, content, sig = row
    return {
        "event_id": event_id,
        "pubkey": pubkey,
        "kind": kind,
        "created_at": created_at,
        "tags": json.loads(tags) if isinstance(tags, str) else tags,
        "content": content,
        "sig": sig,
    }


def _event_has_tags(event: Mapping[str, object], required: set[tuple[str, str]]) -> bool:
    tags = normalize_tags(_parse_tags(event.get("tags")))
    available = {(tag.key, value) for tag in tags for value in tag.values}
    return required.issubset(available)


def _parse_content(value: object) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    raise ValueError("content must be bytes or string")
