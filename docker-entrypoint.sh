#!/usr/bin/env bash
# Container entrypoint: launch the FastAPI API (uvicorn) and Nginx.
set -euo pipefail

cd /app/transportation-api

# Start the API in the background on PORT (default 8000).
export USE_MOCK_DATA="${USE_MOCK_DATA:-0}"
/opt/venv/bin/uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}" &
API_PID=$!

# Start Nginx in the foreground (master process stays in foreground with -g).
nginx -g 'daemon off;' &

# Forward signals to children.
trap 'kill -TERM $API_PID 2>/dev/null; wait' TERM INT

wait -n
