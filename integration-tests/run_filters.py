import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Filter interop harness")
    parser.add_argument("--url", default="ws://127.0.0.1:9000")
    return parser.parse_args()


def run_background(cmd: list[str]) -> subprocess.Popen:
    return subprocess.Popen(cmd)


def main() -> None:
    args = parse_args()

    relay = run_background([
        sys.executable,
        str(ROOT / "integration-tests" / "run_relay.py"),
        "--host",
        "127.0.0.1",
        "--port",
        args.url.split(":")[-1],
    ])
    try:
        time.sleep(1.0)
        subprocess.run(["pnpm", "-C", str(ROOT / "implementations" / "typescript-sdk"), "build"], check=True)

        ts_sub = run_background([
            "node",
            str(ROOT / "integration-tests" / "ts" / "subscribe.js"),
            args.url,
            "2",
            "5000",
        ])
        py_sub = run_background([
            sys.executable,
            str(ROOT / "integration-tests" / "python" / "subscribe.py"),
            "--url",
            args.url,
            "--kind",
            "2",
            "--timeout",
            "5",
        ])

        subprocess.run([
            sys.executable,
            str(ROOT / "integration-tests" / "python" / "publish.py"),
            "--url",
            args.url,
            "--kind",
            "1",
            "--content",
            "ignore",
        ], check=True)
        time.sleep(0.5)
        subprocess.run([
            sys.executable,
            str(ROOT / "integration-tests" / "python" / "publish.py"),
            "--url",
            args.url,
            "--kind",
            "2",
            "--content",
            "match",
        ], check=True)

        ts_sub.wait(timeout=6)
        py_sub.wait(timeout=6)
    finally:
        relay.terminate()
        relay.wait(timeout=5)


if __name__ == "__main__":
    main()
