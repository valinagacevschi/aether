# Aether Relay

Python relay server implementation for the Aether protocol.

## Install

From repo root:

```bash
git clone https://github.com/valinagacevschi/aether
cd aether
cd relay/python
python -m pip install -e .
```

## Run

```bash
python -m aether_relay.server \
  --ws-port 9000 \
  --quic-port 4433 \
  --gateway nostr,http \
  --nostr-port 7447 \
  --http-port 8081 \
  --http-ws-port 8082 \
  --storage sqlite \
  --storage-path data/relay.db
```

Without install:

```bash
PYTHONPATH="$PWD" python -m aether_relay.server --ws-port 9000
```

## Transport Support

- WebSocket: always enabled (`--ws-port`).
- QUIC: implemented via `aioquic`; starts only when cert/key files exist.

If QUIC certs are missing, relay starts with WebSocket only and logs a warning.

## QUIC Example

From repo root, create self-signed certs:

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout certs/localhost-key.pem \
  -out certs/localhost.pem \
  -subj "/CN=localhost"
```

Run relay with QUIC + WebSocket:

```bash
cd relay/python
python -m aether_relay.server \
  --ws-host 127.0.0.1 \
  --ws-port 9000 \
  --quic-host 127.0.0.1 \
  --quic-port 4433 \
  --quic-cert ../../certs/localhost.pem \
  --quic-key ../../certs/localhost-key.pem \
  --storage sqlite \
  --storage-path ../../data/relay.db
```

### Storage Options

- `--storage sqlite` (default): durable storage in SQLite
- `--storage memory`: in-memory store
- `--storage rocksdb`: RocksDB store (requires `python-rocksdb`)

### Gateway Options

- `--gateway none|nostr|http|nostr,http`
- `--nostr-port 7447` (NIP-01 websocket gateway)
- `--http-port 8081` (REST + SSE)
- `--http-ws-port 8082` (JSON websocket gateway)

HTTP routes:
- `POST /v1/events`
- `POST /v1/subscriptions`
- `DELETE /v1/subscriptions/{id}`
- `GET /v1/stream?subscription_id=...`
- `GET /healthz`

### Notes

- QUIC requires TLS cert/key files. Defaults to `certs/localhost.pem` and `certs/localhost-key.pem`.
- WebSocket is available for browser clients.
