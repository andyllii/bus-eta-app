# Hong Kong Observatory (HKO) Weather API

Integration reference for the HKO **Open Data `weatherAPI`** endpoint, covering the
three data needs of this project:

1. Current weather conditions (e.g. "Sunny", "Cloudy")
2. Current temperature
3. Active weather warnings (typhoon signals, rainstorm warnings)

All endpoints are **free, keyless, public**, served over HTTPS, and return JSON.
Verified against the live endpoint (July 2026).

- Reference: HKO Open Data API Documentation
  <https://www.hko.gov.hk/en/weatherAPI/doc/files/HKO_Open_Data_API_Documentation.pdf>
- Client implementation in this repo: `src/clients/hko.py`

---

## Base endpoint

```
GET https://data.weather.gov.hk/weatherAPI/opendata/weather.php
```

- **Method:** `GET` (always)
- **Response:** `application/json`
- The *type* of data returned is selected entirely by the `dataType` query
  parameter. There is one URL; you switch feeds via query params.

### Common query parameters

| Param      | Required | Values                     | Notes |
|------------|----------|----------------------------|-------|
| `dataType` | yes      | `rhrread`, `warnsum`, `warningInfo`, `flw`, `fnd`, … | Selects the feed. |
| `lang`     | no       | `en`, `tc`, `sc`           | Response language. Default `en`. `tc` = Traditional Chinese, `sc` = Simplified. |
| `rformat`  | no       | `json`, `csv`              | Some legacy datasets need `rformat=json` or return an HTML error page. The `opendata/weather.php` feeds below default to JSON. |

> **Pitfall:** On some HKO datasets, omitting `rformat=json` yields an HTML error
> page instead of JSON. The project client always sends `rformat=json` defensively.

---

## 1. Current weather report — `dataType=rhrread`

The core "current conditions" feed: temperature, humidity, rainfall, UV index,
the weather-condition icon, and any active warning messages (as prose).

### Request

```
GET https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=en
```

### Response structure (abridged, live sample)

```jsonc
{
  "rainfall": {
    "data": [
      { "unit": "mm", "place": "Central & Western District", "max": 0, "main": "FALSE" }
      // ... one entry per district
    ],
    "startTime": "2026-07-11T06:45:00+08:00",
    "endTime":   "2026-07-11T07:45:00+08:00"
  },
  "icon": [50],                                   // weather condition icon code(s)
  "iconUpdateTime": "2026-07-11T06:00:00+08:00",
  "uvindex": {
    "data": [{ "place": "King's Park", "value": 0.9, "desc": "low" }],
    "recordDesc": "During the past hour"
  },
  "updateTime": "2026-07-11T08:02:00+08:00",
  "temperature": {
    "recordTime": "2026-07-11T08:00:00+08:00",
    "data": [
      { "place": "King's Park",           "value": 29, "unit": "C" },
      { "place": "Hong Kong Observatory", "value": 28, "unit": "C" }
      // ... one entry per station
    ]
  },
  "humidity": {
    "recordTime": "2026-07-11T08:00:00+08:00",
    "data": [{ "unit": "percent", "value": 86, "place": "Hong Kong Observatory" }]
  },
  "warningMessage": [
    "The Very Hot Weather Warning is now in force. ..."   // string[] (may be [] or absent)
  ],
  "tcmessage": "",
  "mintempFrom00To09": { /* ... */ },
  "rainfallFrom00To12": { /* ... */ },
  "rainfallLastMonth": { /* ... */ },
  "rainfallJanuaryToLastMonth": { /* ... */ }
}
```

### Field notes

- **Current temperature:** `temperature.data[]`. Each element has
  `place`, `value` (number, degrees), `unit` (`"C"`). There is **no single
  city-wide value** — pick a reference station. This project uses
  `"Hong Kong Observatory"` (`香港天文台`), falling back to the first element.
- **Current humidity:** `humidity.data[0]` → `value` (percent).
- **Condition ("Sunny"/"Cloudy"):** *Not* provided as text here. The
  `rhrread` feed gives an **icon code** in `icon[]` (e.g. `50` = Sunny). Map the
  code to a label via the HKO Weather Icon reference
  (<https://www.hko.gov.hk/textonly/v2/explain/wxicon_e.htm>), or use the `flw`
  feed (§4) for a prose forecast description.
- **`warningMessage`:** array of prose warning sentences currently in force
  (may be empty or absent). Convenient for display, but the **authoritative**
  active-warning source is `warnsum` (§3).
- Timestamps are ISO-8601 with `+08:00` (HKT) offset.

---

## 2. Current temperature

Temperature is delivered inside the **`rhrread`** feed above — there is no
separate temperature-only endpoint. Extract from `temperature.data[]`:

```
GET .../weather.php?dataType=rhrread&lang=en
→ temperature.data[] → { place, value, unit }
```

Recommended: read the entry where `place == "Hong Kong Observatory"` as the
canonical HK reading.

---

## 3. Active weather warnings

Two complementary feeds. Use **both**: `warnsum` says *what is active*,
`warningInfo` gives the *full statement text*.

### 3a. Warning summary — `dataType=warnsum` (authoritative "is it active?")

```
GET https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=warnsum&lang=en
```

Response is an **object keyed by warning code**. Only currently-active warnings
appear (empty `{}` when none in force):

```jsonc
{
  "WHOT": {
    "name": "Very Hot Weather Warning",
    "code": "WHOT",
    "actionCode": "REISSUE",             // ISSUE | REISSUE | CANCEL | EXTEND | UPDATE
    "issueTime":  "2026-07-10T11:30:00+08:00",
    "updateTime": "2026-07-11T06:45:00+08:00"
  }
  // Typhoon signal example key: "WTCSGN": { "name": "...", "code": "TC8NE", ... }
}
```

> **Pitfall:** `warningInfo` alone returns an empty/absent `details` array when
> nothing is in force, so it can *hide* active warnings. Treat `warnsum` as the
> source of truth for whether a warning is active.

### 3b. Warning statement text — `dataType=warningInfo`

```
GET https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=warningInfo&lang=en
```

```jsonc
{
  "details": [
    {
      "warningStatementCode": "WHOT",
      "subtype": "WHOT",
      "contents": [
        "The Very Hot Weather Warning is now in force.",
        "Under the influence of extremely hot weather ..."
      ],
      "updateTime": "2026-07-11T06:45:00+08:00"
    }
  ]
}
```

- `contents` is a `string[]` of paragraphs — join for display.
- Index by `warningStatementCode` (falls back to `code`) to match a `warnsum`
  entry.

### Warning code reference (subset)

| Code    | Warning |
|---------|---------|
| `WRAINA` / `WRAINR` / `WRAINB` | Amber / Red / Black Rainstorm Warning Signal |
| `WTCSGN` | Tropical Cyclone Warning Signal (the `code` field carries the specific signal, e.g. `TC1`, `TC3`, `TC8NE`, `TC9`, `TC10`) |
| `WFIRE`  | Fire Danger Warning |
| `WFROST` | Frost Warning |
| `WHOT`   | Very Hot Weather Warning |
| `WCOLD`  | Cold Weather Warning |
| `WMSGNL` | Strong Monsoon Signal |
| `WTMW`   | Tsunami Warning |
| `WL`     | Landslip Warning |
| `WFNTSA` | Special Announcement on Flooding in the northern New Territories |
| `WTS`    | Thunderstorm Warning |

Full list in the HKO Open Data API PDF. The repo client maps codes → severity
buckets and multilingual titles in `src/clients/hko.py`.

---

## 4. Prose forecast / general situation — `dataType=flw` (optional)

Local weather forecast: general situation, current tropical-cyclone info, and a
human-readable forecast description — useful when you want a text "condition"
string rather than an icon code.

```
GET https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=flw&lang=en
```

```jsonc
{
  "generalSituation": "The outer subsiding air of Severe Typhoon Bavi is bringing mainly fine weather to Guangdong.",
  "tcInfo": "At 8 a.m., Bavi was centred about 330 kilometres east of Taibei ...",
  "fireDangerWarning": "",
  "forecastPeriod": "Weather forecast for today",
  "forecastDesc": "Fine. Extremely hot during the day with a maximum temperature of around 35 degrees ...",
  "outlook": "Extremely hot in some areas with one or two showers tomorrow ...",
  "updateTime": "2026-07-11T07:45:00+08:00"
}
```

---

## 5. 9-day forecast — `dataType=fnd` (optional enrichment)

```
GET https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=en
```

Returns `generalSituation`, `weatherForecast[]` (per-day `forecastDate`, `week`,
`forecastWeather`, `forecastMaxtemp`, `forecastMintemp`, `forecastWind`, `PSR`,
`ForecastIcon`), plus `updateTime`. Consumed opportunistically by the client's
`get_9day_forecast()`.

---

## Summary table

| Need                       | dataType      | Key field(s) | Notes |
|----------------------------|---------------|--------------|-------|
| Current temperature        | `rhrread`     | `temperature.data[]` | Per-station; use "Hong Kong Observatory". |
| Current humidity           | `rhrread`     | `humidity.data[0].value` | Percent. |
| Condition icon             | `rhrread`     | `icon[]` | Map via HKO icon reference. |
| Condition prose            | `flw`         | `forecastDesc` | Human-readable. |
| Active warnings (list)     | `warnsum`     | object keyed by code | Authoritative "is active". |
| Warning statement text     | `warningInfo` | `details[].contents` | Join paragraphs. |
| 9-day forecast             | `fnd`         | `weatherForecast[]` | Optional. |

---

## Operational notes

- **Method:** all `GET`, no auth, no rate-limit key required. Be polite — HKO
  updates roughly every 10 minutes; cache accordingly. This project caches the
  weather feeds with a 30s TTL (`CACHE_TTL_WEATHER`, see `config/settings.py`).
- **Timestamps:** ISO-8601 with `+08:00` (HKT).
- **Fail-soft:** the client logs and returns `None`/`[]` on any network/parse
  error so a partial HKO outage never takes down the combined endpoint.
- **Base URL override:** `HKO_BASE_URL` env var (default
  `https://data.weather.gov.hk/weatherAPI/opendata/weather.php`).
