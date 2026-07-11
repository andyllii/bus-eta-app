#!/usr/bin/env bash
# Smoke-test the Bus ETA backend against a running server.
# Usage:  ./smoke-test.sh [BASE_URL]   (default http://localhost:8000)
set -euo pipefail

BASE="${1:-http://localhost:8000}"
STOP="946C74E30100FE80"   # Cheung Sha Wan Plaza (KMB) — known-good demo stop
RC=0

check() {
  local name="$1" url="$2" want="$3"
  local code
  code=$(curl -s -o /tmp/smoke.body -w '%{http_code}' -m 10 "$BASE$url" || echo 000)
  if [ "$code" = "$want" ]; then
    echo "PASS  [$code] $name  $url"
  else
    echo "FAIL  [$code] $name  $url  (expected $want)"
    RC=1
  fi
}

echo "== Bus ETA backend smoke test against $BASE =="
check "health"            "/health"                       200
check "openapi"           "/openapi.json"                 200
check "eta (primary)"     "/api/v1/eta?route=1&stop=$STOP" 200
check "search"            "/api/v1/search?q=1&lang=tc"    200
check "weather"           "/api/v1/weather"               200
check "incidents"         "/api/v1/incidents"             200
check "stop view"         "/v1/bus-stops/$STOP"           200
check "unknown stop 404"  "/api/v1/eta?route=1&stop=DEADBEEF" 404

echo "== done =="
exit $RC
