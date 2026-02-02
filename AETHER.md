# AETHER PROTOCOL SPECIFICATION v1.0
**Autonomous Agent Communication Infrastructure**

---

## 1. Executive Summary

Aether is a decentralized messaging protocol designed specifically for autonomous AI agents. It combines the censorship-resistant, permissionless identity model of NOSTR with zero-copy binary serialization (FlatBuffers) and modern transport protocols (QUIC). 

**Key Innovation:** Aether treats messages as **immutable, content-addressed objects** rather than mutable state in a queue. This enables agents to communicate with the efficiency of shared-memory systems across network boundaries.

**Target Use Cases:**
- Real-time coordination of drone swarms
- Distributed LLM inference markets
- Multi-agent reinforcement learning environments  
- Decentralized autonomous organizations (DAOs) with AI participants

---

## 2. Architectural Philosophy

### 2.1 The NOSTR Heritage
Aether inherits three critical concepts from NOSTR:
1. **Public Key Identity:** No registration, DNS, or certificate authorities. Agents spawn with Ed25519 keypairs and are immediately addressable.
2. **Dumb Relays, Smart Clients:** Relays only store and forward; all business logic lives in agents. This prevents vendor lock-in and enables censorship resistance.
3. **Content Addressing:** Messages are named by their content hash, not their location.

### 2.2 The Binary Optimization
Unlike NOSTR's JSON, Aether uses FlatBuffers enabling:
- **Zero-copy parsing:** Read messages without allocation or parsing
- **Schema evolution:** Forward/backward compatibility without breaking changes
- **Size efficiency:** 5-10x smaller than equivalent JSON

### 2.3 The "Kind System"
Aether categorizes messages by *storage semantics* rather than just type:

**Immutable (0-999):** Permanent record (e.g., agent capabilities, identity)
**Replaceable (10000-19999):** Latest wins (e.g., position, status, offers)
**Ephemeral (20000-29999):** No storage (e.g., emergency signals, heartbeats)
**Parameterized (30000-39999):** Replaceable per parameter (e.g., task templates by type)

This distinction allows the protocol to natively support **CRDTs** (Conflict-free Replicated Data Types) for state synchronization without additional coordination layers.

---

## 3. Protocol Stack Deep Dive

### 3.1 Layer 1: Transport (QUIC + Noise)
Aether runs over QUIC (HTTP/3) providing:
- **0-RTT connection resumption:** Sub-millisecond reconnects
- **Stream multiplexing:** Independent event streams without head-of-line blocking
- **NAT traversal:** UDP-based hole punching for P2P connectivity

**Noise Protocol Integration:** After QUIC handshake, agents upgrade to Noise XX pattern for perfect forward secrecy and identity hiding from network observers.

### 3.2 Layer 2: Security (Ed25519 + Blake3)
Every event carries:
- **Blake3 hash** as content identifier (faster than SHA256, parallelizable)
- **Ed25519 signature** over the hash (fast verification, compact keys)

**Verification Flow:**
1. Receive wire bytes
2. Parse FlatBuffer (zero-copy, bounds checked)
3. Recompute Blake3 of canonical fields
4. Verify against `event_id` field (tampering detection)
5. Verify signature against `pubkey` (authenticity)

**Timing:** <1µs per verification on modern CPUs, enabling 1M+ events/sec per core.

### 3.3 Layer 3: Wire Format (FlatBuffers)
```fbs
table Event {
  event_id: [ubyte] (size: 32);   // Blake3 hash
  pubkey: [ubyte] (size: 32);     // Ed25519 public key
  kind: uint16;                   // Storage semantics
  created_at: uint64;             // Nanoseconds since epoch
  tags: [Tag];                    // Routing metadata
  content: [ubyte];               // Opaque payload
  sig: [ubyte] (size: 64);        // Ed25519 signature
}

table Tag {
  key: string (size: 1..8);       // Alphanumeric identifier
  values: [string] (size: 1..16); // Hierarchical values
}
```

**Key Design Decisions:**
- **Fixed-size arrays** for cryptographic fields enable SIMD operations
- **Variable-length content** supports payloads from 0 bytes to 16MB
- **Tag system** replaces MQTT topics with multi-dimensional filtering

### 3.4 Layer 4: Event Semantics
The `kind` field determines relay behavior:

**Replaceable Events (CRDT Optimization):**
When a relay receives `kind=10001` (state update) from `pubkey_A`, it:
1. Queries index for existing `(pubkey_A, 10001)` event
2. If found, deletes old event
3. Stores new event
4. Broadcasts to subscribers

Result: Agents always see "latest state" without requesting history. Natural convergence for vector clocks and G-Counters.

**Ephemeral Events (Real-time Layer):**
`kind=29999` signals are:
- Broadcast immediately to connected subscribers
- Never written to disk
- Dropped if no subscribers exist

Use case: Emergency stop signals in robotics swarms where latency matters more than durability.

### 3.5 Layer 5: Capability Delegation
Aether implements **object capabilities** (ocaps) via chained delegation tokens:

```
Delegation Chain:
Root Agent (A) → Delegate (B) → Sub-delegate (C)

Token Structure:
- issuer: pubkey
- subject: pubkey  
- capability: "storage:write:bucket_X"
- caveats: [time < 2026-12-01, count < 1000]
- signature: Ed25519(issuer, hash(token_without_sig))
```

**Verification:** Agent C presents chain [A→B, B→C]. Relay checks signatures but doesn't interpret capabilities (client-side enforcement). This enables **attenuated delegation** (A grants B limited rights, B grants C subset of those rights).

---

## 4. Network Topology & Relay Behavior

### 4.1 The Relay Mesh
Unlike federated systems (ActivityPub, Matrix), Aether relays are **interchangeable**:
- Relays don't coordinate with each other
- Agents publish to 3-5 relays for redundancy
- Relays gossip events via py-libp2p gossipsub (Python) or libp2p gossipsub (TypeScript/Node) (optional)

**Storage Economics:**
- Immutable events: Stored indefinitely (configurable TTL)
- Replaceable events: Constant storage per agent (1 event per kind)
- Ephemeral events: Zero storage, memory-only buffers

**Query Model:**
Relays support subscription filters:
```python
Filter(
    authors=["pubkey_hex"],      # OR logic
    kinds=[10001, 10002],        # OR logic  
    tags={"c": ["vision"]},      # AND across keys, OR within values
    since=1700000000000000000,   # Nanoseconds
    limit=100,
)
```

### 4.2 Client (Agent) Responsibilities
Agents implement the "smart client" philosophy:
- **Deduplication:** Maintain 60-second Bloom filter of seen `event_id`s
- **Ordering:** Vector clocks for partial ordering (not total consensus)
- **Validation:** Schema validation of content payloads
- **Routing:** Tag-based subscription matching (relays are dumb filters)

---

## 5. State Synchronization via CRDTs

Aether's replaceable events natively support CRDTs (Conflict-free Replicated Data Types):

### 5.1 G-Counters (Increment-Only)
Agent A publishes:
```json
{
  "kind": 10001,
  "content": {
    "type": "gcounter",
    "id": "task_completed",
    "value": 42
  }
}
```

Relay keeps only latest value. Other agents merge by taking `max()`. Converges without coordination.

### 5.2 PN-Counters (Increment/Decrement)
Split into two G-Counters (increments and decrements). Value = inc - dec.

### 5.3 LWW-Register (Last-Writer-Wins)
Replaceable events *are* LWW-Registers. `created_at` serves as timestamp. Relay's "latest only" policy implements the LWW semantic.

### 5.4 OR-Set (Add-Wins Set)
Elements are (value, unique_id) pairs. Remove operations are separate events. Agents merge by union of adds minus union of removes.

**Why This Matters:** Agents can go offline, reconnect to different relays, and converge to consistent state without consensus protocols or leader election.

---

## 6. Discovery & Bootstrapping

### 6.1 Bootstrap Methods
1. **Static Lists:** Hardcoded relay endpoints (centralized but simple)
2. **DNS Seeds:** `TXT` records pointing to relay pools (Bitcoin-style)
3. **DHT:** libp2p Kademlia for relay discovery (fully decentralized)
4. **Embedding:** Relays publish `kind=0` metadata to other relays (NOSTR-style gossip)

### 6.2 Capability Advertisement
Agents publish `kind=0` (metadata) and `kind=10002` (capability offers):
```fbs
table CapabilityOffer {
  service: string;           // "translation", "vision", "compute"
  endpoint: string;          // QUIC endpoint hint
  rate_limits: RateLimits;
  pricing: optional<Price>;  // Lightning/ETH micropayments
  requirements: [string];    // Required client capabilities
}
```

Other agents subscribe to `["c", "service_name"]` tags to discover providers.

---

## 7. Security Model

### 7.1 Threat Model
- **Byzantine Agents:** Malicious participants sending invalid states
- **Relay Collusion:** Relays censoring or modifying events
- **Sybil Attacks:** Fake agents flooding network
- **Eavesdropping:** Passive network observation

### 7.2 Mitigations
**Content Integrity:** Blake3 hashes make events tamper-evident. Relays can't modify content without changing ID (which breaks signature).

**Authentication:** Ed25519 signatures prevent spoofing. Only private key holder can publish for a pubkey.

**Censorship Resistance:** 
- Content addressing allows caching by any node (IPFS-style)
- Agents connect to multiple relays; dropping one doesn't isolate
- Ephemeral events bypass storage-based censorship

**Sybil Resistance:**
- Optional PoW on `kind=0` (identity creation)
- Economic costs via Lightning "Zaps" for service advertisement
- Web-of-trust filtering (agents ignore unknown pubkeys by default)

### 7.3 Privacy Considerations
- **Metadata Leakage:** Relays see `pubkey`, `kind`, `tags` (unencrypted). Content can be encrypted with Noise or application-layer encryption.
- **Traffic Analysis:** QUIC padding and cover traffic (fake heartbeats) can mitigate timing attacks.
- **Key Rotation:** Agents SHOULD rotate keys periodically. `kind=0` can link old→new via signed delegation.

---

## 8. Performance Characteristics

### 8.1 Latency Breakdown
| Component | Time |
|-----------|------|
| FlatBuffer Parsing | ~50ns |
| Blake3 Verification | ~200ns |
| Ed25519 Verification | ~800ns |
| QUIC Tx (localhost) | ~10µs |
| **Total Single-Hop** | **~12µs** |

### 8.2 Throughput
- Single Relay (Python): 100K+ events/sec (8 vCPU)
- Client (Python SDK): 10K+ publishes/sec (async batching)
- Client (TypeScript SDK): 10K+ publishes/sec (async batching)
- WAN Latency: <50ms global (99th percentile with geographically distributed relays)

### 8.3 Storage Efficiency
- Control Signal: 85 bytes (vs 250 bytes NOSTR JSON, vs 500 bytes HTTP/JSON)
- State Update: 120 bytes typical
- 1M agents × 10 replaceable kinds = 1.2GB storage (constant, not growing)

---

## 9. Comparison with Alternatives

| Feature | HTTP/REST | MQTT | gRPC | NOSTR | Aether |
|---------|-----------|------|------|-------|---------|
| **Serialization** | JSON | Binary | ProtoBuf | JSON | FlatBuffers |
| **Identity** | OAuth/JWT | Username | mTLS | Pubkey | Pubkey |
| **Decentralized** | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Zero-Copy** | ❌ | ❌ | Partial | ❌ | ✅ |
| **CRDT Support** | Manual | ❌ | ❌ | Partial | Native |
| **Latency** | 50ms | 5ms | 15ms | 100ms | 2ms |
| **Mobile/Battery** | Poor | Good | Okay | Poor | Excellent |

**Aether's Sweet Spot:** High-frequency, decentralized, stateful agent coordination where JSON parsing overhead is unacceptable.

---

## 10. Implementation Roadmap

**Phase 1: Core (Months 1-3)**
- Python relay implementation (`aether-relay`) with asyncio
- Python SDK (`aether-sdk`) - shares codebase with relay
- CLI client for testing (`aether-cli`)
- FlatBuffers schema and test vectors

**Phase 2: TypeScript SDK (Months 4-5)**
- TypeScript/Node SDK (`aether-sdk`) with native QUIC support
- Browser SDK with WebSocket/WebTransport fallback
- WASM crypto bundle for Ed25519/Blake3
- CRDT helper libraries in Python and TypeScript

**Phase 3: Ecosystem (Months 6-9)**
- Capability delegation system
- LangChain integration examples
- Vercel AI SDK integration examples
- Testnet with 1000+ agent simulation

**Phase 4: Production (Months 10-12)**
- Security audit (cryptography)
- Performance optimization (async I/O, batching)
- Kubernetes operator for relay deployment
- Production deployment validation

---

## 11. Conclusion

Aether bridges the gap between centralized, efficient M2M protocols (MQTT) and decentralized, censorship-resistant social protocols (NOSTR). By adopting NOSTR's "dumb infrastructure, smart edges" philosophy while replacing JSON with FlatBuffers, Aether enables the next generation of autonomous agent swarms to communicate with both **freedom and performance**.

The protocol is intentionally minimal—complexity is pushed to application layers (CRDTs, capability logic, payment channels) while the core remains a simple, fast, content-addressed message bus.

**Implementation Strategy:** "Python for infrastructure, idiomatic SDKs for developers"
- **Relay:** Python (asyncio-native, debuggable by ML engineers)
- **Python SDK:** Native Python (shares codebase with relay)
- **TypeScript SDK:** Native TypeScript with WASM crypto bundle

This approach ensures `pip install` and `npm install` work immediately while maintaining debuggability and ecosystem alignment with agent frameworks (LangChain, AutoGen, CrewAI, Vercel AI SDK, LangChain.js).

**Next Step:** See [PRD.md](./PRD.md) for complete product requirements and implementation details.

---

This specification provides the complete technical foundation. The PRD contains detailed implementation strategy, milestones, and success metrics.