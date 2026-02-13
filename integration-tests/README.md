# Integration Tests

## Quickstart

1) Start relay (WebSocket-only for tests):

```bash
python integration-tests/run_relay.py --host 127.0.0.1 --port 9000
```

Note: `run_relay.py` adds `relay/python` to `PYTHONPATH`.

2) Build TypeScript SDK:

```bash
pnpm -C sdk/typescript build
```

3) Run interop harness:

```bash
python integration-tests/run_interop.py --url ws://127.0.0.1:9000
```

4) Run filter interop harness:

```bash
python integration-tests/run_filters.py --url ws://127.0.0.1:9000
```

## Environment

- `AETHER_RELAY_URL`: WebSocket relay URL (default `ws://127.0.0.1:9000`).
- `AETHER_RELAY_HOST`: relay host for `run_relay.py` (default `127.0.0.1`).
- `AETHER_RELAY_PORT`: relay port for `run_relay.py` (default `9000`).

## Benchmarks

```bash
python integration-tests/bench/bench_relay.py --url ws://127.0.0.1:9000 --count 1000
python integration-tests/bench/bench_python_sdk.py --url ws://127.0.0.1:9000 --count 1000
node integration-tests/bench/bench_ts_sdk.js ws://127.0.0.1:9000 1000
python integration-tests/bench/bench_nostr_gateway.py --url ws://127.0.0.1:7447 --count 1000
python integration-tests/bench/bench_http_gateway.py --host 127.0.0.1 --port 8081 --count 1000
python integration-tests/bench/failure_modes.py
```

## Notes

- These scripts use the WebSocket relay transport for portability.
- QUIC transport tests can be added once certificates are available.

## Gateway Examples

```bash
PYTHONPATH="$PWD/sdk/python" python integration-tests/examples/nostr_client_min.py
PYTHONPATH="$PWD/sdk/python" python integration-tests/examples/http_publish_sse.py
```
