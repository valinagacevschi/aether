# Initial Gateway Benchmark Report

This report compares three surfaces over the same relay core:

- Native Aether (`integration-tests/bench/bench_relay.py`)
- NOSTR gateway (`integration-tests/bench/bench_nostr_gateway.py`)
- HTTP gateway (`integration-tests/bench/bench_http_gateway.py`)

## Repro Commands

```bash
# Terminal 1
cd relay/python
PYTHONPATH=. python -m aether_relay.server \
  --ws-host 127.0.0.1 --ws-port 9000 \
  --gateway nostr,http \
  --nostr-port 7447 --http-port 8081 --http-ws-port 8082

# Terminal 2
python integration-tests/bench/bench_relay.py --url ws://127.0.0.1:9000 --count 1000
python integration-tests/bench/bench_nostr_gateway.py --url ws://127.0.0.1:7447 --count 1000
python integration-tests/bench/bench_http_gateway.py --host 127.0.0.1 --port 8081 --count 1000
python integration-tests/bench/failure_modes.py
```

## Metrics to Capture

- Throughput: events/sec
- Latency: p50/p95/p99
- Resource snapshot: CPU %, RSS MB

## Failure Modes

- Relay restart while gateways enabled
- Gateway startup/shutdown stability
- Invalid message handling during load
- Slow SSE consumer behavior (queue drop counter via `/healthz`)
