# Aether Protocol Spec (v1 Draft)

This document is the spec-first summary for Aether (AT). It is derived from `RFC.txt` and intended to guide implementations with a concise, implementation-ready view.

## Event Structure

An Event is a signed, content-addressed message.

Field types and limits:
- `event_id`: 32 bytes, Blake3 hash of canonical serialization.
- `pubkey`: 32 bytes, Ed25519 public key (compressed).
- `kind`: uint16. Storage policy ranges are defined below; relays SHOULD reject kinds outside 0-39999 for interoperability.
- `created_at`: uint64, Unix timestamp in nanoseconds.
- `tags`: array of Tag.
- `content`: variable-length opaque bytes. Maximum size is implementation-defined.
- `sig`: 64 bytes, Ed25519 signature over `event_id`.

Event ID calculation (canonical serialization, network byte order):
1. `pubkey` (32 bytes)
2. `created_at` (8 bytes, big-endian)
3. `kind` (2 bytes, big-endian)
4. `tags` (count as 2 bytes + tag data)
5. `content` (raw bytes)

`event_id = BLAKE3(concat(...))` and `sig = Ed25519.sign(private_key, event_id)`.

## Event Kinds

Storage semantics by kind:
- 0-999 (IMMUTABLE): Store indefinitely.
- 10000-19999 (REPLACEABLE): Keep latest per (`pubkey`, `kind`).
- 20000-29999 (EPHEMERAL): Forward only, do not persist.
- 30000-39999 (PARAMETERIZED_REPLACEABLE): Keep latest per (`pubkey`, `kind`, `d` tag value).

Relays MAY apply additional policies, but these ranges MUST be supported for interoperability.

## Tag Filtering

Tags are multi-dimensional routing metadata. A Tag has:
- `key`: 1-8 ASCII characters (alphanumeric + underscore).
- `values`: array of UTF-8 strings, max 16 values, max 1024 bytes per value.

Standard keys: `p`, `e`, `c`, `d`, `g`, `t`, `expiration`.

Filter evaluation:
- AND between filter fields.
- OR within each array of values.
- Tag filters match when the event has a tag with the same `key` and any matching `value`.

## Transport

Events are transmitted as length-prefixed FlatBuffers messages.
- 4 bytes: message length (big-endian)
- N bytes: FlatBuffers `Event`

Transport is stream-based and transport-agnostic. QUIC is recommended; TCP/WebSocket are acceptable.

## Validation

A relay/client validating an Event MUST:
1. Recompute `event_id` from canonical serialization and compare.
2. Verify `sig` against `event_id` using `pubkey`.
3. Enforce kind policy (support 0-39999; reject or policy-handle others).
4. Enforce timestamp window (recommended: reject > 60s in the future).

Relays SHOULD treat duplicate `event_id` as idempotent and ignore after first acceptance.
