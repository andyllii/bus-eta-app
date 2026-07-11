# Bus ETA Service — Data Models & API Specification

Status: Design (v1.0.0)
Author: backend-developer
Date: 2026-07-10

This document is the authoritative design for the Bus ETA backend. It defines
the five core data models (`BusStop`, `Route`, `ETA`, `Weather`, `Incident`)
and the REST API surface, including the **primary combined endpoint** that the
mobile client uses to render a stop screen.

The machine-readable contract lives alongside this file in
`bus-eta-openapi.yaml` (OpenAPI 3.0.3). This Markdown is the human-readable
companion and rationale.

---

## 1. Context & Goals

The Bus ETA app shows a rider, for a chosen bus stop, the upcoming bus arrivals
plus the context that affects their trip: weather warnings and traffic
incidents. Data is sourced from three Hong-Kong public providers, already wired
in the existing `transportation-api` package:

| Concern    | Provider / feed                        | Client module        |
|------------|----------------------------------------|----------------------|
| Bus ETA    | KMB `data.etabus.gov.hk` stop-eta      | `kmb_client.py`      |
| Bus ETA    | Citybus/NWFB `rt.data.gov.hk` eta      | `citybus_client.py`  |
| Weather    | HKO OpenData `weatherAPI`              | `hko_client.py`      |
| Incidents  | HK Transport Dept traffic-news XML     | `td_client.py`       |

All four clients share `src/clients/base.py` (`BaseClient`), which provides a
TTL cache, optional API-key auth injection, per-provider outbound rate
limiting, and typed error handling with retry/backoff. See
[`docs/integrations/hk-bus-eta-fetcher.md`](docs/integrations/hk-bus-eta-fetcher.md).

The existing `main.py` already exposes a single `GET /eta?route=&stop_id=`
endpoint that fans out to the three clients and returns a flattened object. The
current React Native client (`transportation-app/api.js`) calls exactly that
endpoint. **This spec formalizes those ad-hoc models into named resources and
introduces a cleaner, resource-oriented API while preserving the legacy
`/eta` shape for backward compatibility.**

### Design principles
- **Combined-by-stop is primary.** The mobile "stop screen" is the dominant
  view, so a single call returns stop + ETAs + weather + incidents.
- **Multilingual by default.** All human-readable text is a `{en, tc, sc}`
  object, because HKO/TD/KMB serve Traditional Chinese, Simplified, and English.
- **Fail-soft aggregation.** If one provider fails, the others still return
  (mirrors the `try/except` behaviour already in `main.py`).
- **Stable types.** Timestamps are ISO-8601 (UTC, `date-time`); coordinates are
  WGS84 `GeoPoint`.

---

## 2. Core Data Models

### 2.1 BusStop
A physical bus stop.

| Field             | Type            | Notes                                        |
|-------------------|-----------------|----------------------------------------------|
| `id`              | string          | KMB stop ID, 16-char hex, e.g. `946C74E30100FE80` (PK) |
| `name`            | `{en,tc,sc}`    | Stop name in three languages                 |
| `location`        | GeoPoint        | Lat/lon                                      |
| `address`         | `{en,tc,sc}`?   | Optional                                     |
| `routes`          | string[]        | Route numbers serving the stop               |
| `data_timestamp`  | date-time?      | Last metadata refresh                        |

### 2.2 Route
A bus route definition.

| Field           | Type        | Notes                                    |
|-----------------|-------------|------------------------------------------|
| `id`            | string      | Route number, uppercase (PK), e.g. `1`   |
| `name`          | `{en,tc,sc}`?| Optional route label                     |
| `operator`      | string      | e.g. `KMB`                               |
| `service_type`  | integer     | KMB service type (1=normal,2=express…)   |
| `directions`    | string[]    | e.g. `["O","I"]`                         |
| `destinations`  | {O,I}       | Terminal name per direction              |
| `stops`         | string[]?   | Ordered stop IDs (optional expansion)    |

### 2.3 ETA
A predicted arrival of a route at a stop. Derived from the KMB stop-eta feed
(the existing `ETA` pydantic model in `kmb_client.py`).

| Field              | Type           | Notes                                          |
|--------------------|----------------|------------------------------------------------|
| `co`               | string         | Company code, e.g. `KMB`                        |
| `route`            | string         | e.g. `1`                                       |
| `direction`        | string         | `O` outbound / `I` inbound                      |
| `service_type`     | integer        | defaults 1                                      |
| `seq`              | integer        | Stop sequence on route                          |
| `dest`             | `{en,tc,sc}`   | Destination name                                |
| `eta_seq`          | integer        | Ordering among upcoming arrivals                |
| `eta`              | date-time      | Predicted arrival (UTC)                         |
| `minutes_remaining`| integer?       | Server-computed, `>=0` (matches `minutes_remaining` prop) |
| `remark`           | `{en,tc,sc}`?  | e.g. "Scheduled", "KMB staff on board"          |
| `data_timestamp`   | date-time      | When KMB published the prediction               |

> Note: `minutes_remaining` is computed from `eta - now`, exactly as the
> existing `ETA.minutes_remaining` property does. It is nullable when `eta` is
> null (e.g. "No scheduled departure").

### 2.4 Weather
Current weather, warnings, and forecast from HKO.

| Field         | Type              | Notes                              |
|---------------|-------------------|------------------------------------|
| `temperature` | {place,value,unit}?| Current air temperature            |
| `description` | string?          | Human-readable conditions, resolved to `lang` (e.g. "Showers"/"驟雨"/"骤雨"); derived from HKO icon codes |
| `humidity`    | {value,unit}?     | Relative humidity                  |
| `icon`        | integer[]         | HKO weather icon codes             |
| `update_time` | date-time         | Feed update time                   |
| `warnings`    | WeatherWarning[]  | Active warnings                    |
| `forecast`    | ForecastDay[]?    | Short forecast (optional)          |

`WeatherWarning`:

| Field       | Type           | Notes                     |
|-------------|----------------|---------------------------|
| `code`      | string         | HKO warning code, e.g. `WRAINA` |
| `title`     | `{en,tc,sc}`   | Warning title             |
| `severity`  | enum           | none/amber/red/black/warning |
| `contents`  | string         | Full HKO warning text     |
| `issue_time`| date-time?     | When issued               |

### 2.5 Incident
A traffic incident from the HK Transport Department (maps to the existing
`TrafficIncident` model in `td_client.py`).

| Field               | Type            | Notes                                  |
|---------------------|-----------------|----------------------------------------|
| `id`                | string          | TD incident number (PK)                |
| `heading`           | `{en,tc,sc}`    | Short headline                         |
| `detail`            | `{en,tc,sc}`?   | Longer description                     |
| `location`          | `{en,tc,sc}`    | Road / area                            |
| `district`          | `{en,tc,sc}`?   | District                               |
| `direction`         | `{en,tc,sc}`?   | Affected direction                     |
| `road_type`         | `{en,tc,sc}`?   | e.g. highway, road                     |
| `near_landmark`     | `{en,tc,sc}`?   | Nearest landmark                       |
| `status`            | `{en,tc,sc}`    | INCIDENT_STATUS_* value                |
| `announcement_date` | string          | e.g. `2026-07-10 08:30`                |
| `relevance`         | enum?           | high/medium/low/none — set only on combined endpoints |

`relevance` is **not** in the raw TD feed; the API computes it on combined
endpoints to rank incidents by proximity to the queried stop's district/roads.

---

## 3. REST API Surface

Base path: `/v1`. All responses are `application/json`.

### 3.1 PRIMARY — `GET /v1/bus-stops/{stopId}`
Returns the combined view for a stop. This is what the mobile stop screen
calls. Fields: `stop`, `etas`, `weather`, `incidents`, `query_time`.

Query params:
- `lang` (en/tc/sc, default `tc`) — language for text fields.
- `route` (optional) — restrict `etas` to one route (mirrors current `/eta` filter).
- `include_weather` (bool, default true)
- `include_incidents` (bool, default true)

Example response:
```json
{
  "stop": {
    "id": "946C74E30100FE80",
    "name": { "en": "Cheung Sha Wan Plaza", "tc": "長沙灣廣場", "sc": "长沙湾广场" },
    "location": { "lat": 22.333, "lon": 114.161 },
    "routes": ["1", "2", "6"]
  },
  "etas": [
    {
      "co": "KMB", "route": "1", "direction": "O", "service_type": 1,
      "seq": 12, "dest": { "en": "Central (Macao Ferry)", "tc": "中環（港澳碼頭）", "sc": "中环（港澳码头）" },
      "eta_seq": 1, "eta": "2026-07-10T08:42:00Z", "minutes_remaining": 4,
      "remark": { "tc": "預定班次" }, "data_timestamp": "2026-07-10T08:37:55Z"
    }
  ],
  "weather": {
    "temperature": { "place": "Hong Kong Observatory", "value": 28, "unit": "C" },
    "humidity": { "value": 84, "unit": "%" },
    "icon": [63],
    "update_time": "2026-07-10T08:30:00Z",
    "warnings": [
      { "code": "WRAINA", "title": { "en": "Amber Rainstorm Warning Signal", "tc": "黃色暴雨警告信號" }, "severity": "amber", "contents": "…", "issue_time": "2026-07-10T07:15:00Z" }
    ]
  },
  "incidents": [
    { "id": "TD20260710-00123", "heading": { "tc": "因交通意外道路封閉" }, "location": { "tc": "屯門公路" }, "district": { "tc": "屯門" }, "status": { "tc": "生效中" }, "relevance": "low", "announcement_date": "2026-07-10 08:30" }
  ],
  "query_time": "2026-07-10T08:38:00Z"
}
```

### 3.2 Other endpoints
| Method & Path                         | Purpose                                            |
|---------------------------------------|----------------------------------------------------|
| `GET /api/v1/eta`                     | **PRIMARY aggregation** — bus ETA + weather + traffic incidents for a `route` + `stop` in one object (see `docs/api_v1_eta.md`). |
| `GET /v1/bus-stops`                   | Search/list stops (by `q`, proximity `lat/lon/radius_m`) |
| `GET /v1/bus-stops/{stopId}`          | Stop static details                                |
| `GET /v1/bus-stops/{stopId}/etas`     | ETAs for a stop (optional `route` filter)          |
| `GET /v1/routes`                      | Search/list routes                                 |
| `GET /v1/routes/{routeId}`            | Route details                                       |
| `GET /v1/routes/{routeId}/etas`       | ETAs grouped by stop for a route                   |
| `GET /v1/weather`                     | Current weather + warnings + forecast             |
| `GET /v1/weather/warnings`            | Active warnings only                               |
| `GET /v1/incidents`                   | List incidents (filter `district`, `status`)       |

All list endpoints are paginated (`page`, `page_size` ≤ 100).

### 3.3 LEGACY — `GET /eta`
```http
GET /eta?route=1&stop_id=946C74E30100FE80
```
Flattened shape consumed by the current React Native client
(`transportation-app/api.js`):
```json
{
  "query_time": "2026-07-10T08:38:00Z",
  "bus_eta": [
    { "route": "1", "dest": "中環（港澳碼頭）", "minutes_remaining": 4,
      "eta_time": "2026-07-10T08:42:00Z", "remark": "預定班次" }
  ],
  "weather_warnings": ["黃色暴雨警告信號 …"],
  "traffic_incidents": [ { "…": "TrafficIncident fields…" } ]
}
```
Marked `x-legacy: true` in the spec. New clients should use
`GET /v1/bus-stops/{stopId}`. Keep it until the mobile app is migrated.

---

## 4. Error Model

All errors return `application/json`:
```json
{ "code": "RESOURCE_NOT_FOUND", "message": "Bus stop 946C… not found.", "detail": null }
```
- `404` → `RESOURCE_NOT_FOUND`
- `500` → `SERVER_ERROR` (e.g. all upstream clients failed to initialise, or a
  single provider raised — aggregation is fail-soft so partial data is still
  returned with `200` and empty arrays, matching current `main.py`).

---

## 5. Implementation Notes / Migration

1. The existing `main.py` already implements the data-fetch + flatten logic for
   `/eta`. Refactor it to emit the typed `BusStopCombined` schema and add the
   `/v1/...` resource routes.
2. Reuse the pydantic models in `kmb_client.py`, `hko_client.py`, `td_client.py`
   directly; the API schemas above are thin, language-wrapped projections of them.
3. `minutes_remaining` and incident `relevance` are computed server-side.
4. Add `lang` propagation to `HKOClient(lang=...)` and `TDClient(lang=...)`.
5. Serve `bus-eta-openapi.yaml` at `/openapi.json` and `/docs` (FastAPI
   `app.openapi()` + Swagger UI) once the routes exist.

---

## 6. Files
- `bus-eta-openapi.yaml` — OpenAPI 3.0.3 spec (validated, 42 `$ref`s resolve).
- `DESIGN.md` — this document.
