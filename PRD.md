# AETHER PROTOCOL PRD v1.0
**Product Requirements Document**

**Date:** February 2026  
**Status:** Draft  
**Owner:** Protocol Engineering Team  
**Stakeholders:** Agent Framework Developers, Robotics Engineers, LLM Infrastructure Teams

---

## 1. Executive Summary

**Product:** Aether Protocol - A decentralized, binary messaging infrastructure for autonomous AI agents.

**Problem Statement:**  
Current agent communication relies on HTTP/JSON (too slow, centralized) or MQTT (efficient but federated/centralized). There is no protocol optimized for **high-frequency, stateful, decentralized** agent coordination. NOSTR provides decentralization but uses JSON (10x overhead). We need the efficiency of MQTT with the censorship-resistance of NOSTR.

**Solution:**  
Aether combines NOSTR's public-key identity and content-addressing with FlatBuffers binary serialization and QUIC transport. It enables sub-millisecond latency for agent swarms while maintaining Byzantine fault tolerance. 

**Implementation Strategy:** "Python for infrastructure, idiomatic SDKs for developers"
- **Relay:** Python (asyncio-native, handles 100K+ TPS, debuggable by ML engineers)
- **Python SDK:** Native Python with `asyncio` (shared codebase with relay)
- **TypeScript SDK:** Native TypeScript with WASM crypto bundle for browser + Node

This approach ensures `pip install` and `npm install` work immediately while maintaining debuggability and ecosystem alignment (LangChain, AutoGen, CrewAI, Vercel AI SDK, LangChain.js).

**Target Launch:** Q3 2026 (v1.0 stable)

---

## 2. Objectives & Success Metrics

### 2.1 Primary Objectives

| Objective | Metric | Target | Measurement Method |
|-----------|--------|--------|-------------------|
| **Performance** | End-to-end latency (P99) | <5ms | Benchmark: 1000 agents, 1M msgs/sec |
| **Efficiency** | Protocol overhead per message | <100 bytes | Wire analysis vs JSON |
| **Decentralization** | Relay failure tolerance | 50% relay loss = 99.9% delivery | Chaos engineering test |
| **Adoption** | Integration by agent frameworks | 3 major frameworks | GitHub tracking |
| **Security** | Audit findings | 0 critical | Third-party audit |

### 2.2 Secondary Objectives
- **Developer Experience:** SDK integration time <30 minutes for Python and TypeScript developers
- **Mobile Efficiency:** Battery impact <3% for 100Hz state updates (vs 15% MQTT)
- **Scalability:** Single Python relay supports 100K+ concurrent agents; Python/TypeScript SDKs handle 10K+ publishes/sec per client

---

## 3. User Personas & Stories

### Persona 1: Drone Fleet Operator (Robotics)
**Name:** Alex  
**Context:** Operating 500 delivery drones in urban environment  
**Pain Point:** Current MQTT broker is single point of failure; JSON parsing adds 20ms latency to collision avoidance signals.

**User Stories:**
- **US-R1:** As an operator, I want drones to maintain formation even if the primary relay fails, so that safety is maintained during network partitions.
- **US-R2:** As a drone, I want to broadcast my position as a "replaceable event" so other drones always see my current location, not outdated coordinates.
- **US-R3:** As a safety system, I want to send emergency stop signals as ephemeral events with <2ms latency so drones halt immediately.

### Persona 2: LLM Agent Orchestrator (AI Infrastructure)
**Name:** Sarah  
**Context:** Running a distributed network of specialized LLM agents (planner, coder, reviewer)  
**Pain Point:** HTTP API calls between agents create bottlenecks; need to share embedding vectors (large binary payloads) efficiently.

**User Stories:**
- **US-A1:** As an orchestrator, I want to discover available "coder" agents via capability advertisements without a central registry.
- **US-A2:** As an agent, I want to delegate my API keys to sub-agents using attenuated capabilities that expire after 1 hour.
- **US-A3:** As a system, I want to share 768-dimensional embedding vectors (3KB) with zero-copy efficiency between Python processes.

### Persona 3: IoT Device Manufacturer (Edge Computing)
**Name:** Chen  
**Context:** Manufacturing battery-powered sensors for smart agriculture  
**Pain Point:** HTTPS overhead drains battery; devices need to work offline and sync when connected.

**User Stories:**
- **US-I1:** As a sensor, I want to queue state updates while offline and sync via CRDT merge when reconnecting, without data loss.
- **US-I2:** As a manufacturer, I want devices to join the network with only a keypair (no SIM card or registration) to reduce BOM costs.
- **US-I3:** As a farmer, I want to run a relay on a Raspberry Pi that can handle 10,000 sensors.

---

## 4. Functional Requirements

### 4.1 Core Protocol (P0 - Must Have)

**FR-1: Event Structure**  
The system SHALL support events with the following immutable fields:
- `event_id`: 32-byte Blake3 hash
- `pubkey`: 32-byte Ed25519 public key  
- `kind`: 16-bit unsigned integer (0-65535)
- `created_at`: 64-bit nanosecond timestamp
- `tags`: Array of key-value pairs (max 100 tags, max 1KB per tag)
- `content`: Variable-length byte array (max 16MB)
- `sig`: 64-byte Ed25519 signature

**FR-2: Event Kinds**  
The system SHALL implement four storage semantics:
- **Immutable (0-999):** Permanent storage, indexed by time
- **Replaceable (10000-19999):** Store only latest per (pubkey, kind)
- **Ephemeral (20000-29999):** Broadcast only, no storage
- **Parameterized (30000-39999):** Store latest per (pubkey, kind, d-tag)

**FR-3: Content Addressing**  
The system SHALL deduplicate events by `event_id`. Relays MUST reject duplicate event_ids silently.

**FR-4: Tag Filtering**  
The system SHALL support subscriptions filtered by:
- Exact match on `kind`
- Prefix match on `pubkey` (first 16 bytes)
- Tag presence and value (e.g., `["c", "vision", "analysis"]`)
- Time range (`since`, `until`)

**FR-5: Transport**  
The system SHALL support:
- QUIC (RFC 9000) as primary transport
- WebSocket fallback for browser compatibility
- Noise Protocol encryption upgrade post-handshake

### 4.2 Relay Functionality (P0)

**FR-6: Validation**  
Relays SHALL validate:
1. Signature correctness (Ed25519)
2. Event_id matches computed hash
3. Timestamp within ±60 seconds of current time (prevent replay)
4. Kind-specific policy compliance

**FR-7: Storage**  
Relays SHALL:
- Store Immutable events for minimum 30 days (configurable)
- Implement Replaceable logic (delete previous on conflict)
- Drop Ephemeral events after broadcast
- Index events by `pubkey`, `kind`, and tags for O(1) lookup

**FR-8: Gossip**  
Relays SHALL support optional gossipsub protocol to forward events to mesh peers.

### 4.3 Client SDK (P0)

**FR-9: Key Management**  
SDKs SHALL provide:
- Ed25519 keypair generation (secure random)
- Key import/export (hex or bech32 format)
- Delegation chain construction and validation

**FR-10: Connection Management**  
SDKs SHALL implement:
- Connection pooling to 3-5 relays
- Automatic failover on relay disconnect
- Exponential backoff for reconnection
- 0-RTT session resumption

**FR-11: CRDT Support**  
SDKs SHALL provide helper libraries for:
- G-Counter (increment-only)
- PN-Counter (increment/decrement)
- LWW-Register (Last-Writer-Wins)
- OR-Set (Observed-Remove Set)

### 4.4 Capability System (P1 - Should Have)

**FR-12: Delegation**  
The system SHALL support chained capability tokens with:
- Issuer and subject pubkeys
- Capability string (URI-style: `service:resource:action`)
- Caveats (time bounds, usage limits, IP restrictions)
- Ed25519 signatures at each link

**FR-13: Attenuation**  
Agents SHALL be able to delegate a subset of their capabilities to other agents.

### 4.5 Economic Layer (P2 - Nice to Have)

**FR-14: Proof of Work**  
Relays MAY require configurable PoW difficulty (leading zero bits in event_id) for spam prevention.

**FR-15: Micropayments**  
Support for Lightning Network invoices attached to Capability Offers (kind 10002).

---

## 5. Non-Functional Requirements

### 5.1 Performance

**NFR-1: Latency**  
- Localhost relay: <100µs per event (end-to-end)
- Same-datacenter: <1ms P99
- Cross-continent: <50ms P99

**NFR-2: Throughput**  
- Single relay (Python): Minimum 100K events/second (8 vCPU, 16GB RAM)
- Single client (Python SDK): Minimum 10K publishes/second (batched)
- Single client (TypeScript SDK): Minimum 10K publishes/second (batched)

**NFR-3: Resource Usage**  
- Memory per connection: <50KB
- Storage overhead: <2x raw event size (indexes included)
- CPU per verification: <1µs (Ed25519 verify)

### 5.2 Reliability

**NFR-4: Availability**  
- Relay uptime target: 99.99%
- Network partition tolerance: System functions with 50% relay failure
- Message delivery: At-least-once semantics (exactly-once via idempotency)

**NFR-5: Data Integrity**  
- No silent data corruption (Blake3 verification)
- Crash consistency: Relay can recover to consistent state after power loss

### 5.3 Security

**NFR-6: Cryptography**  
- Constant-time signature verification (prevent timing attacks)
- Constant-time hash comparison
- Secure random number generation (OS-level)

**NFR-7: Privacy**  
- Metadata minimization: Relays don't log IP addresses (optional)
- Perfect forward secrecy via Noise protocol
- Support for encrypted content (application-layer)

**NFR-8: DoS Resistance**  
- Rate limiting per pubkey (token bucket algorithm)
- Maximum message size enforcement (16MB hard limit)
- Connection limits per IP (configurable)

### 5.4 Compatibility

**NFR-9: Backwards Compatibility**  
- Schema evolution: Forward-compatible FlatBuffers schema
- Version negotiation: Protocol version in handshake

**NFR-10: Cross-Platform**  
- Reference implementations in Python and TypeScript; run on Linux, macOS, Windows
- ARM64 support (Apple Silicon, Raspberry Pi)
- TypeScript/Node for servers; browser clients via WebSocket or WASM

---

## 6. Technical Architecture

### 6.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│              CLIENT SDK (Python / TypeScript)               │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│   │   Key Store  │  │   CRDT Lib   │  │ Capabilities │      │
│   └──────────────┘  └──────────────┘  └──────────────┘      │
└──────────────────┬──────────────────────────────────────────┘
                   │ FlatBuffers / QUIC or WebSocket
┌──────────────────▼──────────────────────────────────────────┐
│             RELAY NODE (Python / TypeScript)                │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│   │ QUIC/WS Srv  │  │ Event Store  │  │   Gossipsub  │      │
│   │ (aioquic/ws) │  │ (SQLite/…)   │  │ (py-libp2p/  │      │
│   │              │  │              │  │  libp2p)     │      │
│   └──────────────┘  └──────────────┘  └──────────────┘      │
│   ┌──────────────┐  ┌──────────────┐                        │
│   │ Tag Index    │  │  Bloom Filter│                        │
│   │ (Inverted)   │  │ (Deduplic)   │                        │
│   └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Implementation Strategy: "Core Spec + Native SDKs"

Rather than FFI everything (which creates build nightmares), we use a **specification-first approach** with **native implementations** optimized for each ecosystem.

**Repository Structure:**
```
aether-protocol/
├── spec/                    # Source of truth
│   ├── schema.fbs           # FlatBuffers schema
│   ├── test-vectors/        # YAML test cases (conformance)
│   └── protocol.md          # Protocol specification
│
├── implementations/
│   ├── relay/               # Python (asyncio-native)
│   │   ├── pyproject.toml
│   │   └── aether_relay/
│   │       ├── __init__.py
│   │       ├── server.py    # QUIC server (aioquic)
│   │       ├── storage/     # SQLite or RocksDB bindings
│   │       └── crypto.py    # PyNaCl/Blake3 (pure Python)
│   │
│   ├── python-sdk/          # Pure Python (shares code with relay)
│   │   ├── aether/
│   │   │   ├── __init__.py
│   │   │   ├── client.py    # asyncio native
│   │   │   └── crypto.py    # PyNaCl/Blake3
│   │   └── setup.py         # pip installable
│   │
│   └── typescript-sdk/      # TypeScript + WASM
│       ├── src/
│       │   ├── client.ts    # Universal transport
│       │   ├── wasm/        # WASM crypto bundle
│       │   └── types/       # Generated from schema
│       └── package.json     # npm installable
│
└── integration-tests/       # Cross-language tests
    ├── docker-compose.yml   # Spin up relay + 3 clients
    └── test_interop.py      # Python -> Python -> TypeScript
```

### 6.3 Technology Stack

**Relay (Python - Infrastructure):**
- **Language:** Python 3.11+ (asyncio-native)
- **Serialization:** FlatBuffers (flatbuffers Python library)
- **Crypto:** PyNaCl (Ed25519), blake3 (pure Python)
- **Network:** aioquic (QUIC), py-libp2p (gossipsub), websockets for fallback
- **Storage:** SQLite (sqlite3) or optional RocksDB bindings
- **Why:** Zero build dependencies, debuggable by ML engineers, Jupyter-friendly, shared codebase with Python SDK

**Python SDK (Native Python):**
- **Language:** Python 3.11+
- **Core:** Pure Python using existing libraries (shares code with relay)
- **Crypto:** PyNaCl (pure Python, sufficient for 10K+ msg/sec)
- **Network:** `aioquic` (asyncio native), `websockets` for fallback
- **Serialization:** `flatbuffers` Python library
- **Why:** Zero build dependencies, Jupyter-friendly, debuggable, asyncio-native, shared codebase with relay

**TypeScript SDK (Web-First, Node-Native):**
- **Language:** TypeScript (Node 20+)
- **Transport:** Browser: WebSocket or WebTransport (HTTP/3); Node: Native QUIC (node-quic or bindings)
- **Crypto:** WASM bundle (~50KB) for Ed25519/Blake3 (~1µs/verify, optimized performance)
- **Serialization:** `flatbuffers` TypeScript library
- **Types:** Generated from FlatBuffers schema (`npm run generate`)
- **Why:** Works in browser without Web Crypto API limitations, deterministic across platforms

### 6.4 Conformance Guarantee

**Shared Test Vectors:** All implementations must pass 100% of test vectors from `spec/test-vectors/`:
- Event signing/verification
- Event ID computation
- CRDT logic
- Replaceable/Ephemeral semantics

**CI/CD Requirement:**
- Python relay: Passes 100% of test vectors
- Python SDK: Passes 100% of test vectors
- TypeScript SDK: Passes 100% of test vectors

**Interoperability Testing:**
- Weekly "plug-fest": Python client ↔ Python relay ↔ TypeScript client
- Fuzz testing: Random valid/invalid events ensure consistent rejection

---

## 7. Milestones & Timeline

### Phase 1: MVP (Weeks 1-8)
**Goal:** Core protocol working with single relay

**Deliverables:**
- [ ] FlatBuffers schema finalized (`spec/schema.fbs`)
- [ ] Initial test vectors (`spec/test-vectors/valid-events.yaml`)
- [ ] Python relay implementation (basic storage, validation, QUIC server via aioquic)
- [ ] Python SDK (pure Python, publish/subscribe, asyncio, shares code with relay)
- [ ] CLI tool for testing (`aether-cli`, Python)
- [ ] Docker container for relay
- [ ] Conformance tests: Python SDK passes test vectors

**Success Criteria:** Two Python agents can exchange 10K messages/second locally via Python relay.

### Phase 2: Robustness (Weeks 9-16)
**Goal:** Production-ready reliability + second SDK

**Deliverables:**
- [ ] Relay mesh gossip implementation (py-libp2p gossipsub)
- [ ] CRDT helper libraries (G-Counter, LWW) in Python
- [ ] TypeScript SDK (Node + browser, WASM crypto)
- [ ] CRDT helpers in TypeScript
- [ ] Comprehensive test suite (unit + integration)
- [ ] Benchmarking suite (latency/throughput)
- [ ] Conformance tests: TypeScript SDK passes test vectors
- [ ] Interoperability tests: Python ↔ Python ↔ TypeScript

**Success Criteria:** 100 agents (mix of Python/TypeScript), 3 relays, 50% relay kill test passes.

### Phase 3: Ecosystem (Weeks 17-24)
**Goal:** Developer adoption tools

**Deliverables:**
- [ ] Capability delegation system
- [ ] Performance optimization for Python relay (async I/O, batching, connection pooling)
- [ ] Example applications (chat, sensor network, LLM swarm)
- [ ] LangChain integration example
- [ ] Vercel AI SDK integration example
- [ ] Documentation site (MkDocs, Docusaurus, or similar)
- [ ] Testnet deployment (public relays)

**Success Criteria:** 3 external contributors submit PRs; at least 1 agent framework integration.

### Phase 4: Production (Weeks 25-36)
**Goal:** Enterprise-ready v1.0

**Deliverables:**
- [ ] Security audit (Trail of Bits or similar)
- [ ] Crypto path review and dependency hardening
- [ ] Performance optimization (relay: async I/O, batching, connection pooling; SDKs: async I/O, batching)
- [ ] Kubernetes operator for relay deployment
- [ ] v1.0 release with stability guarantees

**Success Criteria:** Production deployment by 1 enterprise partner.

---

## 8. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Performance shortfall** | Medium | High | Early benchmarking in Phase 1; Python relay optimized with async I/O and batching; sufficient for 100K+ TPS |
| **Cryptographic vulnerability** | Low | Critical | Use only established libraries (PyNaCl, tweetnacl); shared test vectors ensure correctness; third-party audit |
| **Adoption resistance** | Medium | Medium | Native SDKs (`pip install`, `npm install` work immediately); provide HTTP bridge; emphasize SDK simplicity |
| **Implementation drift** | Medium | High | Spec-first approach; shared test vectors; CI/CD conformance tests; weekly interoperability plug-fests |
| **Network partition issues** | Medium | High | Extensive chaos engineering in Phase 2 |
| **Regulatory issues** (crypto payments) | Low | Medium | Separate payment layer from core protocol; keep core non-financial |
| **Contributor burnout** | Medium | Medium | Clear governance model; paid maintainers from Phase 2 |

---

## 9. Open Questions

1. **Storage Economics:** Should relays charge for storage (pay-to-pin immutable events)?
2. **Content Moderation:** How do public relays handle illegal content without becoming liable?
3. **Mobile Background:** How to maintain connections on iOS/Android with background restrictions?
4. **Quantum Resistance:** Do we need post-quantum signatures now or is Ed25519 sufficient for 5-year horizon?

---

## 10. Appendix

### A. Glossary
- **Agent:** Autonomous software entity
- **Event:** Signed message in the protocol
- **Relay:** Server storing and forwarding events
- **Kind:** Event type determining storage semantics
- **Tag:** Key-value routing metadata

### B. Reference Implementations
- NOSTR: nip-01 (baseline for semantics)
- QUIC: RFC 9000
- Noise Protocol: noiseprotocol.org

### C. Related Work
- MQTT v5.0 (comparison baseline)
- IPFS (content-addressing inspiration)
- Matrix (federated alternative)
- libp2p (gossipsub transport)

### D. Migration Path for Agent Frameworks

**LangChain Integration:**
```python
# langchain-aether package
from langchain_aether import AetherAgent

agent = AetherAgent(
    private_key="nsec1...",  # NOSTR-style bech32
    relays=["wss://relay.aether.network"],
    capabilities=["llm:generation:gpt4"]
)

# Agents auto-discover each other via tags
other_agent = await agent.discover(capability="vision:analysis")
response = await other_agent.task("analyze this image", image_bytes)
```

**Vercel AI SDK Integration:**
```typescript
// ai-sdk-aether
import { AetherAgent } from 'ai-sdk-aether';

const agent = new AetherAgent({
  relays: ['wss://relay.aether.network'],
  onMessage: async (event) => {
    // Handle incoming tasks
    const result = await generateText({ model: openai('gpt-4'), prompt: event.content });
    await agent.publishResponse(event, result);
  }
});
```

### E. Trade-off Analysis

| Approach | Install Experience | Performance | Maintenance | Decision |
|----------|-------------------|-------------|-------------|----------|
| **Native Python + TS, Python Relay** | ✅ Excellent | ✅ Excellent (relay: 100K+ TPS; SDKs: 10K+ TPS) | ✅ 2 codebases (Python relay/SDK share code) | **✅ Chosen** |
| **Shared WASM core** | ⚠️ Okay | ✅ Excellent | ✅ Single crypto lib | **Partial** (TypeScript only) |

**Rationale:** Agent developers prioritize developer experience (debugging, installation, familiar APIs) over squeezing out the last 10% of performance. The Python relay handles infrastructure (100K+ TPS, sufficient for agent swarms) and shares code with the Python SDK, reducing maintenance burden. SDKs need to be "fast enough" (10K+ TPS) and "easy enough" (`pip install`, `npm install`).

---

**Next Steps:**
1. Review PRD with stakeholders (Week 1)
2. Finalize FlatBuffers schema (`spec/schema.fbs`) (Week 1)
3. Create initial test vectors (`spec/test-vectors/`) (Week 1)
4. Scaffold monorepo structure (`spec/`, `implementations/relay/`, `implementations/python-sdk/`, `implementations/typescript-sdk/`) (Week 1-2)
5. Begin Python relay implementation (Week 2)
6. Begin Python SDK implementation (Week 2-3, shares code with relay)

**Approval:**
- [ ] Technical Lead
- [ ] Product Manager  
- [ ] Security Advisor

---
