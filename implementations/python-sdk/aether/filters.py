"""Filter matching for client-side subscriptions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .crypto import Tag, normalize_tags


@dataclass(frozen=True)
class EventFilter:
    kinds: set[int] | None = None
    pubkey_prefixes: tuple[bytes, ...] | None = None
    tags: set[tuple[str, str]] | None = None
    since: int | None = None
    until: int | None = None


def normalize_filter(raw: Mapping[str, object]) -> EventFilter:
    kinds = _normalize_kinds(raw.get("kinds"))
    pubkey_prefixes = _normalize_pubkey_prefixes(raw.get("pubkey_prefixes"))
    tags = _normalize_tag_filters(raw.get("tags"))
    since = _normalize_int(raw.get("since"))
    until = _normalize_int(raw.get("until"))
    return EventFilter(
        kinds=kinds,
        pubkey_prefixes=pubkey_prefixes,
        tags=tags,
        since=since,
        until=until,
    )


def match_event(event: Mapping[str, object], flt: EventFilter) -> bool:
    kind = _parse_int(event.get("kind"), "kind")
    created_at = _parse_int(event.get("created_at"), "created_at")
    pubkey = _parse_hex_or_bytes(event.get("pubkey"), "pubkey", 32)
    tags = normalize_tags(_parse_tags(event.get("tags")))

    if flt.kinds is not None and kind not in flt.kinds:
        return False
    if flt.pubkey_prefixes is not None and not _match_pubkey_prefix(pubkey, flt.pubkey_prefixes):
        return False
    if flt.tags is not None and not _match_tags(tags, flt.tags):
        return False
    if flt.since is not None and created_at < flt.since:
        return False
    if flt.until is not None and created_at > flt.until:
        return False
    return True


def _normalize_kinds(raw: object) -> set[int] | None:
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple, set)):
        raise ValueError("kinds must be a list")
    return {_parse_int(value, "kind") for value in raw}


def _normalize_pubkey_prefixes(raw: object) -> tuple[bytes, ...] | None:
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)):
        raise ValueError("pubkey_prefixes must be a list")
    prefixes = []
    for value in raw:
        prefix = _parse_hex_or_bytes(value, "pubkey_prefix", 16)
        prefixes.append(prefix)
    return tuple(prefixes)


def _normalize_tag_filters(raw: object) -> set[tuple[str, str]] | None:
    if raw is None:
        return None
    tags: set[tuple[str, str]] = set()
    if isinstance(raw, dict):
        for key, values in raw.items():
            if not isinstance(key, str):
                raise ValueError("tag key must be str")
            if not isinstance(values, (list, tuple, set)):
                raise ValueError("tag values must be list")
            for value in values:
                tags.add((key, str(value)))
        return tags
    if not isinstance(raw, (list, tuple, set)):
        raise ValueError("tags must be list or dict")
    for entry in raw:
        if isinstance(entry, (list, tuple)) and len(entry) == 2:
            key, value = entry
            if not isinstance(key, str):
                raise ValueError("tag key must be str")
            tags.add((key, str(value)))
        else:
            raise ValueError("tag filter entries must be (key, value)")
    return tags


def _match_pubkey_prefix(pubkey: bytes, prefixes: Iterable[bytes]) -> bool:
    return any(pubkey.startswith(prefix) for prefix in prefixes)


def _match_tags(tags: Iterable[Tag], required: set[tuple[str, str]]) -> bool:
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


def _normalize_int(value: object) -> int | None:
    if value is None:
        return None
    return _parse_int(value, "filter")


def _parse_tags(value: object) -> list[object]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError("tags must be a list")
    return list(value)
