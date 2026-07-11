# `GET /api/v1/eta` — Primary Transportation Aggregation Endpoint

This document describes the public aggregation endpoint built in task
`t_907cc63f`. It is the primary endpoint the frontend calls to render a single
"next bus" board.

## Purpose

Combine the three Hong Kong open-data modules into **one** JSON object:

| Concern    | Provider / feed               | Client module        |
|------------|-------------------------------|----------------------|
| Bus ETA    | KMB `data.etabus.gov.hk`     | `src/clients/kmb.py` |
| Bus ETA    | Citybus/NWFB `rt.data.gov.hk`| `src/clients/citybus.py` |
| Weather    | HKO OpenData                 | `src/clients/hko.py` |
| Incidents  | HK Transport Dept (TD) XML   | `src/clients/td.py`  |

Endpoint: `GET /api/v1/eta?route=<route>&stop=<stop>`

## Request

| Param             | Required | Default | Notes                                               |
|-------------------|----------|---------|-----------------------------------------------------|
| `route`           | yes      | —       | Bus route number, e.g. `1`.                         |
| `stop`            | yes      | —       | Stop id. KMB = 16-char hex; Citybus = 6-digit.      |
| `lang`            | no       | `tc`    | `en` / `tc` / `sc`.                                 |
| `include_weather` | no       | `true`  | Omit the `weather` block when `false`.              |
| `include_incidents`| no      | `true`  | Omit the `incidents` block when `false`.            |
| `degrade`         | no       | `true`  | Fail-soft on partial upstream failure.              |

## Response (`models.EtaAggregate`)

```json
{
  "query":     { "route": "1", "stop_id": "946C74E30100FE80", "operator": "KMB", "lang": "tc" },
  "etas":      [ { "co": "KMB", "route": "1", "eta": "…", "minutes_remaining": 4, … } ],
  "weather":   { "temperature": {…}, "icon": [62], "warnings": [ … ] },
  "incidents": [ { "id": "TD…", "relevance": "low", … } ],
  "query_time": "2026-07-10T08:49:00Z",
  "degraded":  false
}
```

* `etas` — arrivals for the requested `route` at the stop, sorted by `eta_seq`.
* `weather` — current HKO weather + active warnings (`null` only when the
  weather block is omitted or the provider failed *and* degraded).
* `incidents` — TD traffic incidents relevant to the route/stop, each tagged
  with a server-computed `relevance` (`high`/`medium`/`low`) and sorted
  high-first. Correlation is geo-proximity + district/locality text (see
  `src/services/incidents.py`).
* `degraded` — `true` when a secondary provider failed and was skipped.

## Behaviour & guarantees

* **Concurrent fetch.** Weather and incidents are fetched in parallel (thread
  pool); only the ETA call is issued first because its resolved `BusStop` is
  needed for incident geo-correlation. Endpoint latency ≈ the *slowest*
  upstream, not the sum.
* **Caching.** The assembled payload is memoised in a process-wide TTL cache
  (`settings.cache_ttl`, default 30s) keyed by
  `route|stop|lang|include_weather|include_incidents`. Repeat requests (e.g.
  frontend polling every few seconds) hit the cache. Each upstream client also
  keeps its own short TTL cache (`BaseClient`).
* **Fail-soft aggregation.** A *secondary* provider failure (weather or
  incidents) degrades gracefully: the partial payload is returned with
  `degraded: true`. Set `degrade=false` to turn that into a `500`.
* **404 on unknown stop/route.** When *no* operator returns an ETA for the
  `route`+`stop`, the endpoint returns `404 RESOURCE_NOT_FOUND` (never a
  silently empty payload).
* **Mock mode.** With `USE_MOCK_DATA=1` the endpoint serves the built-in mock
  for any id; `DEADBEEF` still exercises the 404 path.

## Source layout

* `routes/eta_aggregate.py` — FastAPI router (`/api/v1/eta`).
* `src/services/eta_aggregate.py` — `EtaAggregateService` (orchestration,
  concurrency, caching, correlation wiring).
* `models/schemas.py` — `EtaAggregate`, `EtaQuery` response models.

## Tests

* `tests/test_eta_aggregate.py` — 13 offline unit tests (service + route):
  happy path & relevance ranking, 404, 422, toggles, route filtering,
  fail-soft degradation, no-degrade 500, cache hit, mock mode.
* `scripts/live_eta_v1_smoke.py` — live end-to-end smoke (skips without
  network).
