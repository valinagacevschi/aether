# Aether Protocol

## Event Kinds

Kind ranges define storage semantics:

- 0-999: Regular events. Relays store and serve these until evicted by policy.
- 10000-19999: Replaceable events. Relays store only the latest per (pubkey, kind).
- 20000-29999: Ephemeral events. Relays do not persist these beyond the live session.
- 30000-39999: Parameterized replaceable events. Relays store only the latest per parameter key.

## Replaceable Conflict Resolution

Replaceable key: `(pubkey, kind)`.

Conflict resolution rules:
- Highest `created_at` wins.
- If `created_at` ties, choose the lexicographically greatest `event_id` (byte-order).

## Parameterized Conflict Resolution

Parameterized key: `(pubkey, kind, d-tag)`.

The `d-tag` is the value of the tag whose key is `d` in the event's `tags` array.
