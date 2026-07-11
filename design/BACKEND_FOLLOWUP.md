# Backend Follow-up Completion — t_844e668b (backend-developer)

Date: 2026-07-11
Workspace: /opt/data/kanban/workspaces/t_b3fe8645/transportation-api (canonical)

## Summary
The Bus ETA backend was already substantially built and verified at code level.
This follow-up (1) closed a real test-isolation regression that hid 6 failing
tests, (2) confirmed the server actually serves /docs + /openapi.json, (3)
performed a genuine live internet round-trip against the real Hong Kong feeds
(KMB, Citybus, HKO, TD), and (4) validated the OpenAPI spec has zero unresolved
$refs. The backend is COMPLETE and verified.

## What was verified (REAL execution, not just README claims)

### 1. Test suite — 113 passed (was silently 6 failing)
Full suite: `pytest -q` -> 113 passed, 1 warning (deprecation).
Two root causes of the 6 failures were real TEST bugs (backend code was correct):
  * `tests/test_canonical_paths.py` set `settings.use_mock_data = True` at import
    time and via a non-scoped autouse fixture, leaking the global flag into
    `test_eta_aggregate.py` service tests (which inject stub clients and rely on
    mock mode being OFF). Stubs were bypassed -> wrong payloads, no raises,
    0 eta_calls.
      FIX: scoped the mock flag to the fixture via `monkeypatch.setattr` so it
      never leaks across modules.
  * `test_openapi_lists_canonical_and_alias_paths` asserted the concrete path
    `/api/v1/bus-stops/946C74E30100FE80` against the schema, but the OpenAPI
    document keys it as the templated `/api/v1/bus-stops/{stopId}`.
      FIX: added a `_path_present()` helper that also matches `{stopId}` template.

### 2. /docs + /openapi.json wiring — CONFIRMED
Running `python app.py` (USE_MOCK_DATA=1) and curling:
  /docs          -> 200 text/html  (Swagger UI)
  /redoc         -> 200 text/html
  /openapi.json  -> 200, 34 KB, parses as JSON, openapi 3.1.0, 15 paths,
                    templated `/api/v1/bus-stops/{stopId}` present.

### 3. All 9 endpoints smoke-tested -> 200 (mock mode)
/, /health, /eta, /api/v1/eta, /api/v1/bus-stops/{id}, /api/v1/weather,
/api/v1/weather/warnings, /api/v1/incidents, /api/v1/search -> all 200.

### 4. LIVE internet round-trip (real HK feeds) — CONFIRMED
Started the server in LIVE mode (no USE_MOCK_DATA; default in .env = false).
  * GET /api/v1/eta?route=1&stop=946C74E30100FE80  -> 200
      real KMB ETA: route 1 -> dest 尖沙咀碼頭 (Tsim Sha Tsui Pier), operator KMB,
      real HKO weather (29C, 香港天文台), 1 live TD incident, degraded=false.
  * GET /api/v1/weather   -> 200, real HKO current weather + 1 warning.
  * GET /api/v1/incidents -> 200, 1 live TD Special Traffic News item.
  * GET /api/v1/eta?route=1&stop=001027 (Citybus) -> 404 RESOURCE_NOT_FOUND
      (live Citybus feed returned 200 with empty data at 03:13 HK local time —
      route 1 not running at 3 AM; client correctly fails-soft and the aggregate
      answers a clean 404, exactly as designed. Verified the client URL
      `https://rt.data.gov.hk/v2/transport/citybus/eta/CTB/1/001027` returns 200
      with `data: []` live.)
  * Unknown stop 0000000000000000 -> 404 RESOURCE_NOT_FOUND (correct).
All four providers (KMB, Citybus/NWFB, HKO, TD) exercised against live data.
Note: ETAs show as null at this hour because it is ~03:00 in Hong Kong — the
KMB/Citybus feeds genuinely return `eta: null` (end-of-service). The clients
handle this faithfully (Optional[datetime]=None, minutes_remaining None). This is
real data, not a defect.

### 5. OpenAPI spec ref-integrity — 0 unresolved $refs
Added `scripts/validate_openapi_refs.py` (checks schemas + parameters +
examples across #/components). Ran against bus-eta-openapi.yaml:
  26 $ref mentions, 0 unresolved.

## Changed files (in canonical workspace)
  * transportation-api/tests/test_canonical_paths.py
      - Removed module-level `settings.use_mock_data = True`.
      - Scoped the autouse fixture to monkeypatch (no global leak).
      - Added `_path_present()` to match templated `{stopId}` paths in the
        OpenAPI assertion.
  * transportation-api/scripts/validate_openapi_refs.py  (NEW — ref validator)

## Notes for downstream (t_dcb43164 packaging / t_e9572496 frontend)
  * Production default is LIVE (USE_MOCK_DATA not set in .env). For offline/demo
    use `./start.sh --mock` or `USE_MOCK_DATA=1`.
  * Root-level `_*.py` files in transportation-api/ are ad-hoc developer probe
    scripts (e.g. `_probe2.py`, `_smoke_live.py`). They are NOT imported by the
    app or collected by pytest (pattern test_*.py), so they do not affect builds
    or tests. Recommend archiving/removing them during packaging for tidiness.
  * Server runs via `python app.py` (host/port from .env) or
    `uvicorn app:app --host 0.0.0.0 --port 8000`. Dockerfile/Procfile is the
    remaining packaging item (out of this task's scope).

## Acceptance status
  [x] Backend complete          [x] Builds/runs cleanly
  [x] Documented                [x] Tested (113 pytest + live + OpenAPI)
  [x] /docs + /openapi.json serve
  [x] Live HK feeds round-trip verified
