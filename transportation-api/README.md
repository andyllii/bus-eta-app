# transportation-api

Backend server for the Hong Kong transportation aggregation API. It aggregates
**bus arrival times (KMB)**, **weather warnings (HKO)**, and **road traffic
incidents (Transport Department)** into a single endpoint.

Built with **FastAPI** (Python). Configuration is managed via **dotenv** and
logging via the standard library `logging` module (console + `logs/app.log`).

## Project layout

```
transportation-api/
├── app.py              # FastAPI app factory + entrypoint (uvicorn app:app)
├── config/
│   └── settings.py     # dotenv-backed configuration singleton
├── src/
│   ├── logging_config.py  # logging boilerplate (console + file)
│   └── clients/           # external data-source clients
│       ├── kmb.py         # Kowloon Motor Bus ETA client
│       ├── hko.py         # Hong Kong Observatory weather client
│       └── td.py          # Transport Department traffic-news client
├── routes/
│   ├── eta.py          # GET /eta  (route + stop_id -> ETA + weather + traffic)
│   ├── health.py       # GET /health and GET /
│   ├── bus_stops.py    # GET /v1/bus-stops/{stopId}  (PRIMARY combined endpoint, stub)
│   └── incidents.py    # GET /v1/incidents  (TD road-incident news integration)
├── models/
│   ├── __init__.py     # re-exports canonical schemas + legacy response models
│   └── schemas.py      # canonical resource models (BusStop, Route, ETA,
│                      #   Weather, Incident, BusStopCombined, Error, …)
├── logs/               # runtime logs (git-ignored)
├── .env                # local configuration (copy from .env.example)
├── requirements.txt
└── .gitignore
```

## Setup

```bash
# (optional) create/activate a virtualenv
python -m venv .venv && source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env      # then edit as needed
```

## Run

```bash
# Via the packaged start script (creates .venv + installs deps if missing):
./start.sh                       # live mode (real HK feeds)
./start.sh --mock                # offline/demo mode (USE_MOCK_DATA=1)

# or directly with uvicorn (recommended):
uvicorn app:app --host 0.0.0.0 --port 8000

# or directly:
python app.py
```

Interactive API docs are served at `/docs` (Swagger UI) and `/redoc`, and the
machine-readable schema at `/openapi.json`.

## Endpoints

All endpoints live under the canonical `/api/v1` prefix defined in
`bus-eta-openapi.yaml`. Deprecated `/v1/...` aliases are also mounted for
backward compatibility.

| Method | Path    | Description                                                        |
|--------|---------|--------------------------------------------------------------------|
| GET    | `/`     | App metadata (name, version, links).                              |
| GET    | `/health` | Liveness probe — returns `{"status": "ok", ...}`.                |
| GET    | `/api/v1/eta` | **PRIMARY aggregation endpoint** — bus ETA + weather + traffic incidents for a `route` + `stop` in one object. |
| GET    | `/api/v1/bus-stops/{stopId}` | Combined stop view (ETA + weather + incidents). |
| GET    | `/api/v1/weather` | Current HKO weather + active warnings (+ optional 9-day forecast). |
| GET    | `/api/v1/weather/warnings` | Active HKO weather warnings only. |
| GET    | `/api/v1/weather/hk` | Cached HKO weather endpoint (alias of `/api/v1/weather`). |
| GET    | `/api/v1/incidents` | **TD road-incident news** — live Transport Department "Special Traffic News" feed. |
| GET    | `/api/v1/search` | Unified stop + route search (autocomplete). |
| GET    | `/eta`  | Aggregated ETA + weather warnings + traffic incidents (legacy).  |

Legacy aliases (deprecated, kept for compatibility): `/v1/bus-stops/{stopId}`,
`/v1/weather`, `/v1/weather/warnings`, `/v1/incidents`.

### `GET /api/v1/eta` — primary aggregation endpoint (NEW)

The frontend-facing primary endpoint. It takes a bus `route` and `stop` and
returns a single JSON object containing:

1. **`etas`** — the next few bus arrival times for that route at the stop
   (sorted by `eta_seq`, already filtered to the requested `route`).
2. **`weather`** — the current HKO weather + active warnings.
3. **`incidents`** — traffic incidents that might affect the route, each tagged
   with a server-computed `relevance` (`high` / `medium` / `low`), sorted
   high-first. Relevance uses the same geo + district + locality correlation as
   the `/v1/bus-stops` endpoint.

The three providers are fetched **concurrently** (weather + incidents in
parallel via a thread pool) and the whole assembled payload is served from a
**process-wide TTL cache** (`settings.cache_ttl`, default 30s), so the
frontend can poll freely without hammering the upstream feeds. Latency is
bounded by the *slowest* upstream, not the sum.

Query parameters:

- `route` — bus route number, e.g. `1` (required).
- `stop` — bus stop id. KMB = 16-char hex; Citybus/NWFB = 6-digit numeric
  (required).
- `lang` — `en` / `tc` / `sc` (default `tc`).
- `include_weather` — `true`/`false` (default `true`); omit the weather block.
- `include_incidents` — `true`/`false` (default `true`); omit the incidents block.
- `degrade` — `true`/`false` (default `true`). Fail-soft: if a *secondary*
  provider (weather/incidents) fails, return the partial payload with
  `degraded: true` instead of erroring. A *missing stop/route* is never
  degraded — it returns a clean `404`.

Response shape (see `models.EtaAggregate`):

```json
{
  "query": { "route": "1", "stop_id": "946C74E30100FE80", "operator": "KMB", "lang": "tc" },
  "etas": [
    { "co": "KMB", "route": "1", "direction": "O", "seq": 12,
      "dest": { "en": "Central (Macao Ferry)", "tc": "中環（港澳碼頭）", "sc": "中环（港澳码头）" },
      "eta": "2026-07-10T08:49:00Z", "minutes_remaining": 4, "remark": { "tc": "預定" } }
  ],
  "weather": { "temperature": { "value": 28, "unit": "C" }, "icon": [62], "warnings": [ … ] },
  "incidents": [ { "id": "TD…", "relevance": "low", "location": { "tc": "…" }, … } ],
  "query_time": "2026-07-10T08:49:00Z",
  "degraded": false
}
```

Errors:

- `404` `RESOURCE_NOT_FOUND` — the `route`/`stop` combination returned no ETA
  from any operator.
- `422` — missing required `route` or `stop` query param.
- `500` `UPSTREAM_ERROR` — a provider failed *and* `degrade=false`.

Examples:

```bash
curl "http://localhost:8000/api/v1/eta?route=1&stop=946C74E30100FE80"
curl "http://localhost:8000/api/v1/eta?route=1&stop=946C74E30100FE80&lang=en&include_weather=false"
```

For a fully offline / demo run, set `USE_MOCK_DATA=1` and the endpoint serves
the built-in mock payload for any id (with `DEADBEEF` still exercising the 404
path).

### `/v1/bus-stops/{stopId}` — combined stop view

Returns the `BusStopCombined` payload (stop details + all ETAs + weather +
incidents) for a single stop.

Query parameters:

- `lang` — `en` / `tc` / `sc` (default `tc`). Propagated to response text.
- `route` — optional filter; return only ETAs for this route number.
- `include_weather` — `true`/`false` (default `true`); omit the weather block.
- `include_incidents` — `true`/`false` (default `true`); omit the incidents block.

Example:

```bash
curl "http://localhost:8000/v1/bus-stops/946C74E30100FE80"
curl "http://localhost:8000/v1/bus-stops/946C74E30100FE80?route=1"
curl "http://localhost:8000/v1/bus-stops/946C74E30100FE80?include_weather=false"
```

### `/v1/incidents` — Transport Department road-incident news

Fetches the live TD **Special Traffic News** feed
(`https://www.td.gov.hk/{lang}/special_news/trafficnews.xml`), parses each
`<message>`, and returns the canonical `Incident` list. This is the backend
integration for road-incident news: the mobile traffic-alert banner /
Contextual Info screen consumes these incidents.

The feed carries **English + Traditional Chinese** text (`_EN` / `_CN` where
`_CN` is Traditional → our `tc` slot; `sc` requests route the same field into
the `sc` slot). Each `Incident` exposes:

- `id` — TD incident number (e.g. `IN-26-04922`)
- `heading` / `detail` / `location` / `district` / `direction` / `near_landmark` — multilingual text
- `status` — textual status (e.g. `NEW` / `最新情況`)
- `content` — the full impact narrative (`CONTENT_*` field)
- `announcement_date` — ISO timestamp from the feed
- `relevance` — `high` / `medium` / `low`, derived from the status token
  (NEW/UPDATED → high, CLEARED → low, else medium)
- `source_id` — numeric message id (`<ID>` element)
- `geo` — `lat`/`lon` when the feed provides `LATITUDE`/`LONGITUDE`

Query parameters:

- `lang` — `en` / `tc` (default) / `sc`.
- `status` — optional case-insensitive substring filter on the status text
  (e.g. `status=new` returns only newly-reported incidents).

The external call is defensive: if the feed is unreachable or fails to parse,
the endpoint returns `200` with an empty list rather than erroring — the UI
degrades gracefully to "no current incidents".

Example:

```bash
curl "http://localhost:8000/v1/incidents"
curl "http://localhost:8000/v1/incidents?lang=en&status=new"
```

The `/eta` legacy endpoint and `/health` are unchanged.

### `/eta` query parameters

- `route`  — bus route number, e.g. `1`
- `stop_id` — bus stop ID, e.g. `946C74E30100FE80`

Example:

```bash
curl "http://localhost:8000/eta?route=1&stop_id=946C74E30100FE80"
```

Each external data source is fetched defensively; if one source fails the
response still returns the others (partial data) instead of erroring out.

## Core data models

The typed contract from `bus-eta-openapi.yaml` / `DESIGN.md` lives in
`models/schemas.py` (importable via `from models import BusStop, Route, ETA,
Weather, Incident, BusStopCombined, Error, …`). These are plain pydantic models
— no live database required yet — and are what the future `/v1` routes will
serialize. The legacy `HealthStatus`, `EtaItem`, and `EtaResponse` models remain
in `models/__init__.py` for the existing `/health` and `/eta` endpoints.

Shared building blocks:

- `MultilingualText` — the `{en, tc, sc}` text object used across every model.
- `GeoPoint` — WGS84 `{lat, lon}`.
- `Lang` — `en` / `tc` / `sc` enum for language propagation.

## Configuration

All settings are environment-driven and documented in `.env.example`
(server host/port, log level, external API base URLs, request timeout, default
language).
