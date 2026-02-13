"""Shared gateway adapters and validation helpers."""

from __future__ import annotations

from typing import Any, Mapping

ERROR_INVALID_MESSAGE = "invalid_message"
ERROR_INVALID_EVENT = "invalid_event"
ERROR_VALIDATION_FAILED = "validation_failed"
ERROR_SUBSCRIPTION_NOT_FOUND = "subscription_not_found"


def from_nostr_event(event: Mapping[str, object]) -> dict[str, object]:
    translated = dict(event)
    if "event_id" not in translated and "id" in translated:
        translated["event_id"] = translated["id"]
    return _normalize_event(translated)


def to_nostr_event(event: Mapping[str, object]) -> dict[str, object]:
    normalized = _normalize_event(event)
    normalized["id"] = normalized["event_id"]
    return normalized


def from_http_event(event: Mapping[str, object]) -> dict[str, object]:
    return _normalize_event(event)


def to_http_event(event: Mapping[str, object]) -> dict[str, object]:
    return _normalize_event(event)


def nostr_filter_to_aether(raw: Mapping[str, object]) -> dict[str, object]:
    out: dict[str, object] = {}
    kinds = raw.get("kinds")
    if kinds is not None:
        out["kinds"] = kinds

    authors = raw.get("authors")
    if isinstance(authors, list):
        prefixes: list[str] = []
        for author in authors:
            if isinstance(author, str):
                prefixes.append(_pad_pubkey_prefix(author))
        if prefixes:
            out["pubkey_prefixes"] = prefixes

    since = raw.get("since")
    if since is not None:
        out["since"] = since
    until = raw.get("until")
    if until is not None:
        out["until"] = until

    tags: list[tuple[str, str]] = []
    for key, value in raw.items():
        if not isinstance(key, str) or not key.startswith("#"):
            continue
        tag_key = key[1:]
        if not isinstance(value, list):
            continue
        for entry in value:
            tags.append((tag_key, str(entry)))
    if tags:
        out["tags"] = tags

    return out


def _normalize_event(event: Mapping[str, object]) -> dict[str, object]:
    event_id = _require_hex(event.get("event_id"), "event_id")
    pubkey = _require_hex(event.get("pubkey"), "pubkey")
    sig = _require_hex(event.get("sig"), "sig")
    kind = _require_int(event.get("kind"), "kind")
    created_at = _require_int(event.get("created_at"), "created_at")
    tags = _normalize_tags(event.get("tags"))
    content = event.get("content", "")
    if not isinstance(content, str):
        raise ValueError(f"{ERROR_INVALID_EVENT}: content must be string")
    return {
        "event_id": event_id,
        "pubkey": pubkey,
        "sig": sig,
        "kind": kind,
        "created_at": created_at,
        "tags": tags,
        "content": content,
    }


def _normalize_tags(raw: object) -> list[list[str]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{ERROR_INVALID_EVENT}: tags must be list")
    out: list[list[str]] = []
    for entry in raw:
        if not isinstance(entry, list) or len(entry) < 1:
            raise ValueError(f"{ERROR_INVALID_EVENT}: malformed tag")
        if not all(isinstance(item, str) for item in entry):
            raise ValueError(f"{ERROR_INVALID_EVENT}: malformed tag")
        out.append(entry)
    return out


def _require_hex(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{ERROR_INVALID_EVENT}: {field} must be hex string")
    try:
        bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError(f"{ERROR_INVALID_EVENT}: {field} must be hex") from exc
    return value


def _require_int(value: object, field: str) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{ERROR_INVALID_EVENT}: {field} must be int")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"{ERROR_INVALID_EVENT}: {field} must be int") from exc
    raise ValueError(f"{ERROR_INVALID_EVENT}: {field} must be int")


def _pad_pubkey_prefix(prefix: str) -> str:
    # relay filter expects 16-byte prefix hex strings; pad shorter nostr author prefixes.
    if len(prefix) % 2 == 1:
        prefix = f"0{prefix}"
    if len(prefix) > 32:
        return prefix[:32]
    return prefix.ljust(32, "0")
