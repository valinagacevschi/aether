from __future__ import annotations

import argparse
import http.client
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python"))

from aether.crypto import compute_event_id, generate_keypair, sign


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--count", type=int, default=100)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    private_key, pubkey = generate_keypair()

    conn = http.client.HTTPConnection(args.host, args.port, timeout=10)
    conn.request(
        "POST",
        "/v1/subscriptions",
        body=json.dumps({"filters": {"kinds": [1]}}),
        headers={"Content-Type": "application/json"},
    )
    sub = json.loads(conn.getresponse().read().decode("utf-8"))["subscription_id"]
    conn.close()

    latencies: list[float] = []
    for idx in range(args.count):
        event_id = compute_event_id(pubkey=pubkey, created_at=idx + 1, kind=1, tags=[], content=b"bench")
        event = {
            "event_id": event_id.hex(),
            "pubkey": pubkey.hex(),
            "kind": 1,
            "created_at": idx + 1,
            "tags": [],
            "content": "bench",
            "sig": sign(event_id, private_key).hex(),
        }
        start = time.perf_counter()
        conn = http.client.HTTPConnection(args.host, args.port, timeout=10)
        conn.request("POST", "/v1/events", body=json.dumps({"event": event}), headers={"Content-Type": "application/json"})
        conn.getresponse().read()
        conn.close()
        latencies.append(time.perf_counter() - start)

    conn = http.client.HTTPConnection(args.host, args.port, timeout=10)
    conn.request("DELETE", f"/v1/subscriptions/{sub}")
    conn.getresponse().read()
    conn.close()

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    p99 = latencies[int(len(latencies) * 0.99) - 1]
    total = sum(latencies)
    print(
        f"http events={args.count} total={total:.3f}s ev/s={args.count/total:.1f} "
        f"p50={p50*1000:.2f}ms p95={p95*1000:.2f}ms p99={p99*1000:.2f}ms"
    )


if __name__ == "__main__":
    main()
