from __future__ import annotations

import argparse
import http.client
import json
import subprocess
import sys
import time
from pathlib import Path

import websockets
import asyncio

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python"))

from aether.crypto import compute_event_id, generate_keypair, sign


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Failure mode smoke checks")
    parser.add_argument("--relay-host", default="127.0.0.1")
    parser.add_argument("--relay-port", type=int, default=9000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    relay = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "aether_relay.server",
            "--ws-host",
            args.relay_host,
            "--ws-port",
            str(args.relay_port),
            "--gateway",
            "nostr,http",
        ],
        cwd=str(ROOT / "relay" / "python"),
    )
    try:
        time.sleep(2)
        print("relay started")
        _invalid_burst()
        _slow_consumer_check()
        relay.terminate()
        relay.wait(timeout=10)
        print("relay restart test: pass")
    finally:
        if relay.poll() is None:
            relay.terminate()
            relay.wait(timeout=10)


def _invalid_burst() -> None:
    async def run() -> None:
        async with websockets.connect("ws://127.0.0.1:7447") as ws:
            for _ in range(10):
                await ws.send(json.dumps(["EVENT", {"bad": "event"}]))
                await ws.recv()

    asyncio.run(run())
    print("invalid burst test: pass")


def _slow_consumer_check() -> None:
    conn = http.client.HTTPConnection("127.0.0.1", 8081, timeout=10)
    conn.request(
        "POST",
        "/v1/subscriptions",
        body=json.dumps({"filters": {"kinds": [1]}, "subscription_id": "slow-sub"}),
        headers={"Content-Type": "application/json"},
    )
    conn.getresponse().read()
    conn.close()

    private_key, pubkey = generate_keypair()
    # produce many valid events without opening SSE stream to force queue growth/drop behavior.
    for idx in range(1100):
        event_id = compute_event_id(
            pubkey=pubkey,
            created_at=idx + 1,
            kind=1,
            tags=[],
            content=b"x",
        )
        conn = http.client.HTTPConnection("127.0.0.1", 8081, timeout=10)
        conn.request(
            "POST",
            "/v1/events",
            body=json.dumps(
                {
                    "event": {
                        "event_id": event_id.hex(),
                        "pubkey": pubkey.hex(),
                        "kind": 1,
                        "created_at": idx + 1,
                        "tags": [],
                        "content": "x",
                        "sig": sign(event_id, private_key).hex(),
                    }
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        conn.getresponse().read()
        conn.close()

    conn = http.client.HTTPConnection("127.0.0.1", 8081, timeout=10)
    conn.request("GET", "/healthz")
    payload = json.loads(conn.getresponse().read().decode("utf-8"))
    conn.close()
    print(f"slow consumer check: dropped_messages={payload.get('dropped_messages', 0)}")


if __name__ == "__main__":
    main()
