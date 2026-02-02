# Aether Protocol

A Python and TypeScript implementation of the Aether (AT) protocol, a binary messaging system for autonomous agent communication optimized for AI agent frameworks.

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

See [PRD.md](./PRD.md) for the complete product requirements and [RFC.txt](./RFC.txt) for the protocol specification.

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

### Python SDK

```bash
# Install from PyPI (when available)
pip install aether-sdk

# Or install from source
git clone https://github.com/valinagacevschi/aether
cd aether
cd implementations/python-sdk
pip install -e .
```

### TypeScript SDK

```bash
# Install from npm (when available)
npm install aether-sdk

# Or install from source
git clone https://github.com/valinagacevschi/aether
cd aether
cd implementations/typescript-sdk
npm install
```

### Python Relay

```bash
# Install relay server
git clone https://github.com/valinagacevschi/aether
cd aether
cd implementations/relay
pip install -e .

# Run relay
aether-relay --port 443 --storage ./data
```

## Usage

### Python SDK

```python
import asyncio
from aether import AetherClient, EventKind, Filter

async def main():
    # Connect to relay
    client = await AetherClient.connect("relay.example.com:443")
    
    # Generate keypair
    keypair = client.generate_keypair()
    
    # Create and publish an event
    event = await client.create_event(
        kind=EventKind.IMMUTABLE(0),  # Agent metadata
        content=b'{"name":"agent-1"}',
        keypair=keypair
    )
    await client.publish(event)
    
    # Subscribe to events
    filter = Filter(
        kinds=[EventKind.EPHEMERAL(29999)],
        tags={"c": ["vision"]},
        since=timestamp
    )
    
    async for event in client.subscribe(filter):
        print(f"Received event: {event}")

asyncio.run(main())
```

### TypeScript SDK

```typescript
import { AetherClient, EventKind, Filter } from 'aether-sdk';

async function main() {
  // Connect to relay
  const client = await AetherClient.connect('relay.example.com:443');
  
  // Generate keypair
  const keypair = client.generateKeypair();
  
  // Create and publish an event
  const event = await client.createEvent({
    kind: EventKind.IMMUTABLE(0), // Agent metadata
    content: Buffer.from('{"name":"agent-1"}'),
    keypair
  });
  await client.publish(event);
  
  // Subscribe to events
  const filter = new Filter({
    kinds: [EventKind.EPHEMERAL(29999)],
    tags: { c: ['vision'] },
    since: timestamp
  });
  
  for await (const event of client.subscribe(filter)) {
    console.log('Received event:', event);
  }
}

main();
```

## Event Kinds

- **0-999 (IMMUTABLE)**: Permanent storage
- **10000-19999 (REPLACEABLE)**: Latest only per (pubkey, kind)
- **20000-29999 (EPHEMERAL)**: No storage, broadcast only
- **30000-39999 (PARAMETERIZED_REPLACEABLE)**: Latest per (pubkey, kind, d-tag)

## Dependencies

### Python SDK & Relay
- **PyNaCl**: Ed25519 signatures
- **blake3**: Content-addressed hashing
- **flatbuffers**: Zero-copy serialization
- **aioquic**: QUIC transport (asyncio-native)
- **websockets**: WebSocket fallback
- **py-libp2p**: Gossipsub for relay mesh

### TypeScript SDK
- **@noble/ed25519** or **tweetnacl**: Ed25519 signatures
- **blake3**: Content-addressed hashing (WASM)
- **flatbuffers**: Zero-copy serialization
- **ws** or **node-quic**: Transport (WebSocket/QUIC)
- **libp2p**: Gossipsub (Node.js only)

## Security

- Constant-time Ed25519 signature verification
- Replay protection via timestamp validation
- Content sandboxing (no execution of payloads)
- Optional Proof-of-Work for spam prevention

## Architecture

**Implementation Strategy:** "Python for infrastructure, idiomatic SDKs for developers"
- **Relay:** Python (asyncio-native, handles 100K+ TPS)
- **Python SDK:** Native Python (shares codebase with relay)
- **TypeScript SDK:** Native TypeScript with WASM crypto bundle

This approach ensures `pip install` and `npm install` work immediately while maintaining debuggability and ecosystem alignment with agent frameworks (LangChain, AutoGen, CrewAI, Vercel AI SDK, LangChain.js).

## Status

⚠️ **Early Development** - This implementation is under active development and may have breaking changes.

See [PRD.md](./PRD.md) for the complete product requirements and roadmap.

## License

See [LICENSE](./LICENSE) file.

## Contributing

Contributions welcome. Please read the RFC specification before submitting changes.
