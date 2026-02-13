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

### Clone

```bash
git clone https://github.com/valinagacevschi/aether
cd aether
```

### Python SDK

```bash
# Install from PyPI (when available)
pip install aether-protocol

# Or install from source
cd sdk/python
pip install -e .
```

Local import (no install):

```bash
export PYTHONPATH="$PWD/sdk/python"
```

### TypeScript SDK

```bash
# Install from npm (when available)
npm install @aether-protocol/sdk

# Or install from source
cd sdk/typescript
npm install
```

### Python Relay

```bash
# Install relay server
cd relay/python
pip install -e .

# Run relay
python -m aether_relay.server --ws-port 9000 --quic-port 4433 --storage sqlite --storage-path data/relay.db
```

WebSocket is always enabled. QUIC is enabled when cert files exist.
See `/Users/valentin.nagacevschi/dev/aether/relay/README.md` for a full QUIC setup example.

## 5-Minute Start (Gateway Mode)

```bash
git clone https://github.com/valinagacevschi/aether
cd aether

python -m venv .venv
source .venv/bin/activate
python -m pip install -e relay/python -e sdk/python

cd sdk/typescript && npm install && npm run build && cd ../..

cd relay/python
PYTHONPATH=. python -m aether_relay.server \
  --ws-host 127.0.0.1 --ws-port 9000 \
  --gateway nostr,http \
  --nostr-port 7447 \
  --http-port 8081 \
  --http-ws-port 8082
```

In another terminal:

```bash
source .venv/bin/activate
PYTHONPATH="$PWD/sdk/python" python integration-tests/examples/nostr_client_min.py
PYTHONPATH="$PWD/sdk/python" python integration-tests/examples/http_publish_sse.py
```

## Usage

### Python SDK

```python
import asyncio
from aether import Client, compute_event_id, generate_keypair, sign

async def main():
    client = Client()
    await client.connect(["ws://127.0.0.1:9000"])

    private_key, pubkey = generate_keypair()
    content = b'{"name":"agent-1"}'
    event_id = compute_event_id(
        pubkey=pubkey,
        created_at=1,
        kind=1,
        tags=[],
        content=content,
    )
    event = {
        "event_id": event_id,
        "pubkey": pubkey,
        "kind": 1,
        "created_at": 1,
        "tags": [],
        "content": content.decode("utf-8"),
        "sig": sign(event_id, private_key),
    }
    await client.publish(event)

asyncio.run(main())
```

### TypeScript SDK

```typescript
import { AetherClient, computeEventId, generateKeypair, signEventId } from "@aether-protocol/sdk";

async function main() {
  const client = new AetherClient();
  await client.connect(["ws://127.0.0.1:9000"]);

  const { privateKey, publicKey } = await generateKeypair();
  const content = Buffer.from('{"name":"agent-1"}');
  const eventId = computeEventId({
    pubkey: publicKey,
    createdAt: 1,
    kind: 1,
    tags: [],
    content,
  });
  const sig = await signEventId(eventId, privateKey);
  await client.publish({
    event_id: Buffer.from(eventId).toString("hex"),
    pubkey: Buffer.from(publicKey).toString("hex"),
    kind: 1,
    created_at: 1,
    tags: [],
    content: content.toString("utf-8"),
    sig: Buffer.from(sig).toString("hex"),
  });
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
- **cryptography**: Noise-style upgrade (X25519 + AEAD)
- **aioquic**: QUIC transport (asyncio-native)
- **websockets**: WebSocket fallback
- **py-libp2p**: Gossipsub for relay mesh

### TypeScript SDK
- **@noble/ed25519**: Ed25519 signatures
- **@noble/curves / @noble/ciphers / @noble/hashes**: Noise-style upgrade (X25519 + AEAD)
- **blake3**: Content-addressed hashing (WASM)
- **flatbuffers**: Zero-copy serialization
- **ws** or **node-quic**: Transport (WebSocket/QUIC)
- **libp2p**: Gossipsub (Node.js only)

## Security

- Constant-time Ed25519 signature verification
- Replay protection via timestamp validation
- Content sandboxing (no execution of payloads)
- Optional Proof-of-Work for spam prevention
- Noise-style transport upgrade (X25519 + ChaCha20-Poly1305)

## Architecture

**Implementation Strategy:** "Python for infrastructure, idiomatic SDKs for developers"
- **Relay:** Python (asyncio-native, handles 100K+ TPS)
- **Python SDK:** Native Python (shares codebase with relay)
- **TypeScript SDK:** Native TypeScript with WASM crypto bundle

This approach ensures `pip install` and `npm install` work immediately while maintaining debuggability and ecosystem alignment with agent frameworks (LangChain, AutoGen, CrewAI, Vercel AI SDK, LangChain.js).

## Compatibility Matrix

| Surface | Transport | Protocol | Status |
|---|---|---|---|
| Native Aether | WebSocket/QUIC | Aether messages (JSON/FlatBuffers) | Available |
| NOSTR Gateway | WebSocket | NIP-01 core (`EVENT`,`REQ`,`CLOSE`) | Available |
| HTTP Gateway | REST + SSE + WebSocket | JSON | Available |

## Release Checklist

1. `python -m build sdk/python`
2. `cd sdk/typescript && npm install && npm run build && npm pack`
3. `PYTHONPATH=. python -m pytest relay/python/tests`
4. Validate quickstarts in `integration-tests/examples/`
5. Tag and publish:
   - Python: `py-vX.Y.Z`
   - TypeScript: `ts-vX.Y.Z`

## Status

⚠️ **Early Development** - This implementation is under active development and may have breaking changes.

See [PRD.md](./PRD.md) for the complete product requirements and roadmap.

## License

See [LICENSE](./LICENSE) file.

## Contributing

Contributions welcome. Please read the RFC specification before submitting changes.
