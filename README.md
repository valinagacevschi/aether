# Aether Protocol - Rust Implementation

A Rust implementation of the Aether (AT) protocol, a binary messaging system for autonomous agent communication.

## Overview

Aether is a transport-agnostic, content-addressed messaging protocol optimized for machine-to-machine communication. Unlike JSON-based protocols, Aether uses FlatBuffers for zero-copy serialization and reduced bandwidth.

**Key Features:**
- Content-addressed events (Blake3 hashes) for deduplication
- Replaceable events for CRDT-style state synchronization
- Ephemeral events for real-time signals
- Capability-based delegation (macaroon-style)
- Tag-based multi-dimensional routing
- Ed25519 decentralized identity

## Protocol Specification

See [RFC.txt](./RFC.txt) for the complete protocol specification.

## Architecture

```
+--------+           Event (signed)          +--------+
| Agent  | --------------------------------> | Relay  |
|(Client)| <-------------------------------- |        |
+--------+        Subscription Filter        +--------+
                         |
                         v
                    Other Agents
```

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd aether

# Build the project
cargo build --release

# Run tests
cargo test
```

## Usage

### Creating an Event

```rust
use aether::event::{Event, EventKind};
use aether::crypto::Keypair;

// Generate a keypair
let keypair = Keypair::generate();

// Create an event
let event = Event::builder()
    .kind(EventKind::Immutable(0)) // Agent metadata
    .content(b"{\"name\":\"agent-1\"}".to_vec())
    .build(&keypair)?;

// Calculate event_id and sign
let event_id = event.calculate_id();
let signed_event = event.sign(&keypair)?;
```

### Publishing to a Relay

```rust
use aether::relay::RelayClient;

let relay = RelayClient::connect("relay.example.com:443").await?;
relay.publish(signed_event).await?;
```

### Subscribing to Events

```rust
use aether::filter::Filter;

let filter = Filter::builder()
    .kinds(vec![EventKind::Ephemeral(29999)])
    .tag_filter("c", vec!["vision".to_string()])
    .since(timestamp)
    .build();

let mut subscription = relay.subscribe(filter).await?;

while let Some(event) = subscription.next().await? {
    // Process event
    println!("Received event: {:?}", event);
}
```

## Event Kinds

- **0-999 (IMMUTABLE)**: Permanent storage
- **10000-19999 (REPLACEABLE)**: Latest only per (pubkey, kind)
- **20000-29999 (EPHEMERAL)**: No storage, broadcast only
- **30000-39999 (PARAMETERIZED_REPLACEABLE)**: Latest per (pubkey, kind, d-tag)

## Dependencies

- **ed25519-dalek**: Ed25519 signatures
- **blake3**: Content-addressed hashing
- **flatbuffers**: Zero-copy serialization
- **quinn**: QUIC transport (recommended)
- **tokio**: Async runtime

## Security

- Constant-time Ed25519 signature verification
- Replay protection via timestamp validation
- Content sandboxing (no execution of payloads)
- Optional Proof-of-Work for spam prevention

## Status

⚠️ **Early Development** - This implementation is under active development and may have breaking changes.

## License

See [LICENSE](./LICENSE) file.

## Contributing

Contributions welcome. Please read the RFC specification before submitting changes.
