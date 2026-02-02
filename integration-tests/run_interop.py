import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, env=env)


def run_background(cmd: list[str]) -> subprocess.Popen:
    return subprocess.Popen(cmd)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interop harness")
    parser.add_argument("--url", default="ws://127.0.0.1:9000")
    return parser.parse_args()


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
        run(["pnpm", "-C", str(ROOT / "implementations" / "typescript-sdk"), "build"])
        run([sys.executable, str(ROOT / "integration-tests" / "python" / "publish.py"), "--url", args.url])
        run(["node", str(ROOT / "integration-tests" / "ts" / "subscribe.js"), args.url])

        run(["node", str(ROOT / "integration-tests" / "ts" / "publish.js"), args.url])
        run([sys.executable, str(ROOT / "integration-tests" / "python" / "subscribe.py"), "--url", args.url])
    finally:
        relay.terminate()
        relay.wait(timeout=5)


if __name__ == "__main__":
    main()
