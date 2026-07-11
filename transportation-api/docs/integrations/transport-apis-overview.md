# Hong Kong Transportation Data APIs — Research & Reference

Consolidated technical reference for the three open-data sources that power the
backend aggregation service:

1. **KMB / LWB** and **Citybus / NWFB** — real-time bus ETAs
2. **Hong Kong Observatory (HKO)** — weather + warnings
3. **Transport Department (TD)** — road traffic incidents

All endpoints were verified live on **2026-07-12** (HTTP 200, sample payloads
captured below). This document is the foundation for the backend service; the
canonical downstream models it must satisfy live in
`models/schemas.py` (`BusStop`, `ETA`, `Weather`, `Incident`, …).

---

## 0. Shared characteristics

| Property | All three sources |
|---|---|
| Transport | HTTPS, plain `GET` (no request body) |
| Authentication | **None required today** — all feeds are public/keyless |
| Content | JSON (KMB/Citybus/HKO) or XML (TD) |
| Rate limiting | No documented per-key quota; be polite (see per-source limits) |
| Encoding | UTF-8; `User-Agent` header required by some gov endpoints (client always sends one) |
| Timezone | All timestamps are **HKT (+08:00)**; ISO-8601 |

The backend wraps every source in `src/clients/base.py`, which adds a shared
TTL cache, an optional auth header (for a future keyed tier), a per-provider
token-bucket rate limiter, and retry/backoff. See
`integrations/hk-bus-eta-fetcher.md` §2–§4 for the auth/rate-limit/retry
design.

---

## 1. KMB / LWB — Real-time Bus ETA

**Source:** data.gov.hk dataset *"Real time Arrival Data of Kowloon Motor Bus
and Long Win Bus (ETAKMB)"* — 9 JSON resources.

**Base URL:** `https://data.etabus.gov.hk/v1/transport/kmb`
(override: `KMB_BASE_URL`)

### 1.1 Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/stop/{stopId}` | Stop metadata (name, coordinates) |
| GET | `/stop-eta/{stopId}` | **All** ETAs for a stop (every route) |
| GET | `/route/{route}` | Route definition |
| GET | `/route-stop/{route}` | Ordered stops on a route |
| GET | `/route-eta/{route}/{stopId}` | ETA for one route at a stop |

(`route`, `route-stop`, `stop` also exist; `stop-eta` is the primary ETA call.)

### 1.2 Stop ID namespace
KMB stop IDs are **16-char hex**, e.g. `946C74E30100FE80`. This disjoint
namespace is how the combined endpoint decides to route a query to KMB vs
Citybus.

### 1.3 Request example
```
GET https://data.etabus.gov.hk/v1/transport/kmb/stop-eta/946C74E30100FE80
```

### 1.4 Response schema — `/stop` (live sample)
```jsonc
{
  "type": "Stop",
  "version": "1.0",
  "generated_timestamp": "2026-07-12T02:27:29+08:00",
  "data": {
    "stop": "946C74E30100FE80",
    "name_en": "KOWLOON WALLED CITY PARK (WT575)",
    "name_tc": "九龍寨城公園 (WT575)",
    "name_sc": "九龙寨城公园 (WT575)",
    "lat": "22.332261",
    "long": "114.187981"
  }
}
```
Unknown stop → `200` with `{"data":{}}` (client must treat empty `data` as
"no stop"). `lat`/`long` are **strings** (cast to float).

### 1.5 Response schema — `/stop-eta` (live sample, first record)
```jsonc
{
  "type": "StopETA",
  "version": "1.0",
  "generated_timestamp": "2026-07-12T02:27:29+08:00",
  "data": [
    {
      "co": "KMB",
      "route": "1",
      "dir": "O",                       // O = outbound, I = inbound
      "service_type": 1,                // 1=normal, 2=express, ...
      "seq": 8,                         // stop sequence on route
      "dest_tc": "尖沙咀碼頭",
      "dest_sc": "尖沙咀码头",
      "dest_en": "STAR FERRY",
      "eta_seq": 1,                     // order among upcoming arrivals
      "eta": null,                      // null = no prediction (end of service)
      "rmk_tc": "", "rmk_sc": "", "rmk_en": "",   // remark, e.g. "KMB staff on board"
      "data_timestamp": "2026-07-12T02:27:00+08:00"
    }
  ]
}
```
`eta` is **null** when no prediction exists — both `null` and empty remark are
normalised by the client.

### 1.6 Mapping to canonical `ETA` (`models/schemas.py`)
`co, route, dir→direction, service_type, seq, dest_*, eta, eta_seq, rmk_*→remark,
data_timestamp`. `minutes_remaining` is computed server-side from `eta`.

---

## 2. Citybus / NWFB — Real-time Bus ETA

**Source:** data.gov.hk dataset *"Real-time 'Next Bus' arrival time and related
data of Citybus"* — 5 JSON resources. Citybus (CTB) and New World First Bus
(NWFB) share one feed.

**Base URL:** `https://rt.data.gov.hk/v2/transport/citybus`
(override: `CITYBUS_BASE_URL`)

### 2.1 Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/stop/{stopId}` | Stop metadata |
| GET | `/eta/{co}/{route}/{stopId}` | ETA for **one** route at a stop |

> **Critical difference from KMB:** there is **no "all ETAs for a stop"
> endpoint**. Every ETA call requires a `route`. The client fans out to
> `settings.citybus_default_routes` (common-route set) when no specific route is
> requested and merges the results.

### 2.2 Stop ID namespace
Citybus/NWFB stop IDs are **6-digit numeric**, e.g. `001027`. The same feed
serves both companies; the `co` path segment is `CTB` or `NWFB`.

### 2.3 Request example
```
GET https://rt.data.gov.hk/v2/transport/citybus/eta/CTB/1/001027
```

### 2.4 Response schema — `/stop` (live sample)
```jsonc
{
  "type": "Stop",
  "version": "2.0",
  "generated_timestamp": "2026-07-12T02:27:19+08:00",
  "data": {
    "stop": "001027",
    "name_tc": "中環 (港澳碼頭)",
    "name_en": "Central (Macao Ferry)",
    "name_sc": "中环 (港澳码头)",
    "lat": "22.288274152091",
    "long": "114.15042248053",
    "data_timestamp": "2026-07-11T05:00:02+08:00"
  }
}
```

### 2.5 Response schema — `/eta`
```jsonc
{
  "type": "ETA",
  "version": "2.0",
  "generated_timestamp": "2026-07-12T02:27:19+08:00",
  "data": [ /* same record shape as KMB, plus a "stop" field */ ]
}
```
Record fields mirror KMB (`co, route, dir, seq, stop, dest_*, eta, eta_seq,
rmk_*, data_timestamp`). An empty/unknown route simply returns `"data": []`
(HTTP 200) — it never 422s, so it is safe to skip, not fatal.

### 2.6 Mapping to canonical `ETA`
Identical to KMB. `service_type` defaults to `1` (not present in this feed).

---

## 3. Hong Kong Observatory (HKO) — Weather & Warnings

**Source:** HKO Open Data API — *Weather* endpoint.
Reference: <https://www.hko.gov.hk/en/weatherAPI/doc/files/HKO_Open_Data_API_Documentation.pdf>

**Base URL:** `https://data.weather.gov.hk/weatherAPI/opendata/weather.php`
(override: `HKO_BASE_URL`)

### 3.1 Endpoint
A **single URL**; the `dataType` query parameter selects the feed.

```
GET https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=<TYPE>&lang=<en|tc|sc>&rformat=json
```

| Param | Required | Values | Notes |
|---|---|---|---|
| `dataType` | yes | `rhrread`, `warnsum`, `warningInfo`, `flw`, `fnd`, … | Selects the feed |
| `lang` | no | `en`, `tc`, `sc` | Default `en`. `tc`=Traditional Chinese, `sc`=Simplified |
| `rformat` | no | `json` | Client always sends `json` defensively (some datasets return HTML otherwise) |

### 3.2 Feeds used by this project

| Need | dataType | Key field(s) |
|---|---|---|
| Current temperature | `rhrread` | `temperature.data[]` (per-station; use `"Hong Kong Observatory"`) |
| Current humidity | `rhrread` | `humidity.data[0].value` |
| Condition icon | `rhrread` | `icon[]` (map via HKO icon reference) |
| Condition prose | `flw` | `forecastDesc` |
| Active warnings (list) | `warnsum` | object keyed by warning code — **authoritative** |
| Warning statement | `warningInfo` | `details[].contents` |
| 9-day forecast | `fnd` | `weatherForecast[]` (optional) |

### 3.3 `rhrread` response (abridged, live)
```jsonc
{
  "temperature": { "recordTime": "...", "data": [
    { "place": "Hong Kong Observatory", "value": 28, "unit": "C" } ] },
  "humidity": { "recordTime": "...", "data": [
    { "unit": "percent", "value": 86, "place": "Hong Kong Observatory" } ] },
  "icon": [50],                                  // weather icon code(s)
  "iconUpdateTime": "2026-07-11T06:00:00+08:00",
  "uvindex": { "data": [ { "place": "King's Park", "value": 0.9, "desc": "low" } ] },
  "rainfall": { "data": [ { "place": "...", "max": 0, "main": "FALSE" } ],
                "startTime": "...", "endTime": "..." },
  "warningMessage": [ "The Very Hot Weather Warning is now in force. ..." ],
  "updateTime": "2026-07-12T02:27:00+08:00"
}
```
- No single city-wide temperature — pick a reference station
  (`"Hong Kong Observatory"`).
- Condition is **not** provided as text in `rhrread`; `icon[]` codes map to
  labels, or use `flw`/`forecastDesc` for prose.

### 3.4 `warnsum` response (live)
```jsonc
{
  "WHOT": {
    "name": "Very Hot Weather Warning",
    "code": "WHOT",
    "actionCode": "REISSUE",        // ISSUE | REISSUE | CANCEL | EXTEND | UPDATE
    "issueTime": "2026-07-10T11:30:00+08:00",
    "updateTime": "2026-07-11T18:30:00+08:00"
  }
}
```
Only **currently active** warnings appear; `{}` when none in force. Treat this
as the source of truth for "is a warning active?" (the `warningInfo` feed hides
active warnings when its `details` is empty).

### 3.5 Warning code reference (subset)
| Code | Warning |
|---|---|
| `WRAINA` / `WRAINR` / `WRAINB` | Amber / Red / Black Rainstorm |
| `WTCSGN` | Tropical Cyclone Signal (`code` carries `TC1`…`TC10`) |
| `WHOT` / `WCOLD` | Very Hot / Cold Weather |
| `WTS` | Thunderstorm |
| `WFNTSA` | N. New Territories flooding |
| `WMSGNL` / `WFIRE` / `WFROST` / `WL` / `WTMW` | Monsoon / Fire / Frost / Landslip / Tsunami |

### 3.6 Mapping to canonical `Weather` / `WeatherWarning`
`temperature`, `humidity`, `icon`, `warnings[]` (code, title, severity bucket,
contents, issue_time), optional `forecast[]`.

---

## 4. Transport Department (TD) — Road Traffic Incidents

**Source:** data.gov.hk dataset *"Special Traffic News (2nd Generation)"*.
Single **XML** document (per language) listing all current incidents.

**Base URL template:**
`https://www.td.gov.hk/{lang}/special_news/trafficnews.xml`
(override: `TD_BASE_URL`, where `{lang}` ∈ `en` / `tc` / `sc`; default `tc`)

### 4.1 Request
```
GET https://www.td.gov.hk/tc/special_news/trafficnews.xml
```
XML document; `Content-Type: application/xml`. Parse the `<list>` → `<message>`
elements.

### 4.2 XML schema (one `<message>`)
```xml
<message>
  <INCIDENT_NUMBER>IN-26-04927</INCIDENT_NUMBER>
  <INCIDENT_HEADING_EN>...</INCIDENT_HEADING_EN>
  <INCIDENT_HEADING_CN>...</INCIDENT_HEADING_CN>
  <INCIDENT_DETAIL_EN>...</INCIDENT_DETAIL_EN>
  <INCIDENT_DETAIL_CN>...</INCIDENT_DETAIL_CN>
  <LOCATION_EN>...</LOCATION_EN>
  <LOCATION_CN>...</LOCATION_CN>
  <DISTRICT_EN>...</DISTRICT_EN>
  <DISTRICT_CN>...</DISTRICT_CN>
  <DIRECTION_EN>...</DIRECTION_EN>
  <DIRECTION_CN>...</DIRECTION_CN>
  <INCIDENT_STATUS_EN>NEW</INCIDENT_STATUS_EN>
  <INCIDENT_STATUS_CN>最新情況</INCIDENT_STATUS_CN>
  <ANNOUNCEMENT_DATE>2026-07-11T10:21:00</ANNOUNCEMENT_DATE>
  <NEAR_LANDMARK_EN>...</NEAR_LANDMARK_EN>
  <NEAR_LANDMARK_CN>...</NEAR_LANDMARK_CN>
  <BETWEEN_LANDMARK_EN>...</BETWEEN_LANDMARK_EN>
  <BETWEEN_LANDMARK_CN>...</BETWEEN_LANDMARK_CN>
  <ROAD_TYPE_EN>...</ROAD_TYPE_EN>
  <ROAD_TYPE_CN>...</ROAD_TYPE_CN>
  <ID>141824</ID>                  <!-- optional message id -->
  <CONTENT_EN>...</CONTENT_EN>     <!-- optional full narrative -->
  <CONTENT_CN>...</CONTENT_CN>
  <LATITUDE>22.34</LATITUDE>       <!-- optional -->
  <LONGITUDE>114.16</LONGITUDE>    <!-- optional -->
</message>
```
- `*_CN` fields are **Traditional Chinese** (HK convention). The client exposes
  them as `tc` and derives `sc` via OpenCC (falls back to `tc` if unavailable).
- Absent fields are sent as **empty self-closing tags** — the parser skips
  empty tags rather than recording blanks.
- `ANNOUNCEMENT_DATE` may be ISO `2026-07-11T10:21:00` or bare
  `2026-07-11 10:21`; the client normalises to `YYYY-MM-DD HH:MM`.

### 4.3 Mapping to canonical `Incident` (`models/schemas.py`)
| XML element | Canonical field |
|---|---|
| `INCIDENT_NUMBER` (or `ID`) | `id` |
| `INCIDENT_HEADING_*` | `heading` |
| `INCIDENT_DETAIL_*` | `detail` |
| `CONTENT_*` | `content` (full narrative) |
| `LOCATION_*` | `location` |
| `DISTRICT_*` | `district` |
| `DIRECTION_*` | `direction` |
| `ROAD_TYPE_*` | `road_type` |
| `NEAR_LANDMARK_*` / `BETWEEN_LANDMARK_*` | `near_landmark` |
| `INCIDENT_STATUS_*` | `status` |
| `ANNOUNCEMENT_DATE` | `announcement_date` |
| `ID` | `source_id` (numeric message id) |
| `LATITUDE`+`LONGITUDE` | `geo` (`GeoPoint`) |

The combined endpoint additionally computes a `relevance` (high/medium/low) for
each incident relative to the requested route/stop.

---

## 5. Operational summary (per source)

| Source | Base URL | Format | Auth | Default rate limit (req/s) | Cache TTL |
|---|---|---|---|---|---|
| KMB | `data.etabus.gov.hk/v1/transport/kmb` | JSON | none | 20 (`RATE_LIMIT_KMB`) | 10s (`CACHE_TTL_ETA`) |
| Citybus | `rt.data.gov.hk/v2/transport/citybus` | JSON | none | 20 (`RATE_LIMIT_CITYBUS`) | 10s |
| HKO | `data.weather.gov.hk/.../weather.php` | JSON | none | 10 (`RATE_LIMIT_HKO`) | 30s (`CACHE_TTL_WEATHER`) |
| TD | `www.td.gov.hk/{lang}/special_news/trafficnews.xml` | XML | none | 5 (`RATE_LIMIT_TD`) | 120s (`CACHE_TTL_INCIDENTS`) |

**Auth (optional, future-proof):** all feeds are public today. The client can
attach `Authorization: Bearer <key>` (or `X-Api-Key: <key>` via
`API_AUTH_HEADER`/`API_AUTH_SCHEME`) when a key is set per provider
(`KMB_API_KEY`, `CITYBUS_API_KEY`, `HKO_API_KEY`, `TD_API_KEY`). A `401`/`403`
is treated as permanent (`UpstreamAuthError`, not retried).

**Retry/backoff:** transient errors (429, 5xx, timeout, connection) retry up to
`MAX_RETRIES` (3) with exponential backoff + jitter
(`RETRY_BACKOFF_BASE` 0.25s → `RETRY_BACKOFF_MAX` 4s). `Retry-After` on 429 is
honoured. Permanent errors propagate; the combined endpoint degrades gracefully
(`degrade_on_upstream_error=true`, default) returning partial data + `degraded:true`.

---

## 6. Known pitfalls (learned from live integration)

1. **Citybus has no "all ETAs" endpoint** — always supply a `route` (or the
   configured default-route set). Don't expect KMB-style bulk behaviour.
2. **KMB `eta` can be null** — never assume a prediction exists.
3. **KMB/Citybus `lat`/`long` are strings** — cast before storing as float.
4. **HKO `rhrread` gives an icon code, not a text condition** — map `icon[]` to
   a label, or use `flw`/`forecastDesc` for prose.
5. **HKO `warnsum` is the authoritative "active?" source** — `warningInfo`
   hides active warnings when its `details` is empty.
6. **TD XML uses `tc` (Traditional Chinese) in `*_CN`**, empty tags for absent
   fields, and a `YYYY-MM-DD HH:MM` date shape — all handled in `td.py`.
7. **Some HKO datasets need `rformat=json`** or they return HTML — always send
   it.
8. **Send a `User-Agent`** — some gov endpoints reject empty UAs.

---

## 7. Module map (backend implementation)

| File | Responsibility |
|---|---|
| `src/clients/base.py` | `BaseClient`: cache + auth + rate-limit gate + retry/backoff + status→typed-error |
| `src/clients/exceptions.py` | Typed upstream exception hierarchy |
| `src/clients/ratelimit.py` | Thread-safe token-bucket `RateLimiter` |
| `src/clients/kmb.py` | KMB ETA + stop client (`provider="kmb"`) |
| `src/clients/citybus.py` | Citybus/NWFB client (`provider="citybus"`) |
| `src/clients/hko.py` | HKO weather client (`provider="hko"`) |
| `src/clients/td.py` | TD traffic-incident client (`provider="td"`) |
| `models/schemas.py` | Canonical `BusStop`, `ETA`, `Weather`, `Incident`, aggregation/error models |
| `config/settings.py` | All base URLs, auth, rate-limit, retry, cache tunables (env-driven) |
| `src/cache.py` | In-memory TTL cache |

### Existing deeper dives
- `integrations/hk-bus-eta-fetcher.md` — bus fetcher auth / rate-limit / error-handling design
- `integrations/hko-weather-api.md` — HKO feed-by-feed walkthrough with full schema notes
