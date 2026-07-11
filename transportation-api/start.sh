#!/usr/bin/env bash
# Start the transportation-api FastAPI backend.
#
# Usage:
#   ./start.sh                 # serve on HOST/PORT from .env (default 0.0.0.0:8000)
#   ./start.sh --mock          # serve built-in mock data (USE_MOCK_DATA=1)
#   PORT=9000 ./start.sh       # override any setting via env vars
#
# Requires the virtualenv at .venv (create with `python -m venv .venv &&
# pip install -r requirements.txt`). Falls back to a system `python`/`pip` if
# the venv is missing so a fresh clone still runs.
set -euo pipefail

cd "$(dirname "$0")"

# Ensure dependencies are present.
if [ ! -d .venv ]; then
  echo "[start.sh] No .venv found — creating one and installing requirements..."
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi

if [ "${1:-}" = "--mock" ]; then
  export USE_MOCK_DATA=1
fi

echo "[start.sh] Starting transportation-api (USE_MOCK_DATA=${USE_MOCK_DATA:-false})..."
exec .venv/bin/python app.py
