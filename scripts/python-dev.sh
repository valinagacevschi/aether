#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-python3}
VENV_DIR=.venv

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Missing Python executable: $PYTHON_BIN" >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install -e relay/python[dev] -e sdk/python[dev]

exec python "$@"
