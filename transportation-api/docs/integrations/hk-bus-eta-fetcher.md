# Hong Kong Bus ETA — Upstream APIs, Auth, Rate Limiting & Error Handling

This document covers the backend fetcher for live bus ETA data: which official
Hong Kong feeds it uses, how authentication is handled, how outbound traffic
is rate-limited, and how errors are classified and retried. It complements
`DESIGN.md` (data models / API surface) and `hko-weather-api.md`.

Auto-generated context: written 2026-07-11 after implementing the auth +
rate-limit + retry infrastructure in `src/clients/`.

---

## 1. Upstream APIs (verified live)

| Provider | Feed / base URL | Key resource paths | Format |
|---|---|---|---|
| **KMB / LWB** | `data.etabus.gov.hk/v1/transport/kmb` | `/stop/{id}`, `/stop-eta/{id}` | JSON |
| **Citybus / NWFB** | `rt.data.gov.hk/v2/transport/citybus` | `/stop/{id}`, `/eta/{co}/{route}/{stopId}` | JSON |
| **HKO** (weather) | `data.weather.gov.hk/weatherAPI/opendata/weather.php` | `?dataType=rhrread\|warnsum\|warningInfo\|fnd` | JSON |
| **TD** (incidents) | `td.gov.hk/{lang}/special_news/trafficnews.xml` | — (single XML doc) | XML |

Stop-ID namespaces are disjoint, which is how the combined endpoint decides
which bus company to query:

- **KMB** — 16-char hex, e.g. `946C74E30100FE80`.
- **Citybus / NWFB** — 6-digit numeric, e.g. `001027`. The same feed serves
  both; the `co` path segment is `CTB` or `NWFB`.

### Key behavioural notes
- KMB has a real "all ETAs for a stop" endpoint (`/stop-eta/{id}`) — one call
  returns every route at the stop.
- Citybus/NWFB **require a route on every ETA call** (no "all ETAs" endpoint).
  The client fans out to `settings.citybus_default_routes` (best-effort common
  route set) when no specific route is requested; a 422/empty route is skipped,
  not fatal.
- All feeds currently work **without an API key** (verified: a request with a
  dummy `Authorization: Bearer ...` header still returns `200`). Data.gov.hk
  publishes an optional keyed `api.data.gov` tier, which the client supports
  (see §2).

---

## 2. API authentication (optional, settings-driven)

The shared `BaseClient` can attach an auth header to every upstream request.
Today the feeds are public, so no key is configured and **no auth header is
sent** — behaviour is unchanged from before this work.

To enable a keyed tier, set the per-provider env var:

| Provider | Env var |
|---|---|
| KMB | `KMB_API_KEY` |
| Citybus / NWFB | `CITYBUS_API_KEY` |
| HKO | `HKO_API_KEY` |
| TD | `TD_API_KEY` |

Header shape is configurable:

- `API_AUTH_HEADER` (default `Authorization`)
- `API_AUTH_SCHEME` (default `Bearer`) — set to empty string to send the key
  verbatim (e.g. `X-Api-Key: <key>` by also setting `API_AUTH_HEADER=X-Api-Key`).

Example: `CITYBUS_API_KEY=abc123` → `Authorization: Bearer abc123`.

Secrets are **never** serialised. `settings.as_dict()` reports only
`*_api_key_set` booleans, not the key values.

If a key is rejected (`401`/`403`) the client raises `UpstreamAuthError`, which
is **permanent** — it is *not* retried (retrying with the same bad key just
fails again). The aggregation layer then degrades gracefully or surfaces a 5xx
depending on `settings.degrade_on_upstream_error`.

---

## 3. Outbound rate limiting

We pace *our own* calls with a **per-provider token-bucket limiter**
(`src/clients/ratelimit.py`). This protects the shared public feeds from
flooding and avoids IP-level throttling. One limiter is shared per provider name
across all client instances in a process (thread-safe).

Defaults (requests/second, configurable per provider via env):

| Provider | Env var | Default (req/s) | Burst |
|---|---|---|---|
| KMB | `RATE_LIMIT_KMB` | 20 | `RATE_LIMIT_BURST` (10) |
| Citybus | `RATE_LIMIT_CITYBUS` | 20 | 10 |
| HKO | `RATE_LIMIT_HKO` | 10 | 10 |
| TD | `RATE_LIMIT_TD` | 5 | 10 |

If the bucket is empty, `BaseClient` raises `UpstreamRateLimitError`
(retryable) **before** spending a network call, instead of hammering the
upstream. The combined endpoint's fail-soft logic then returns partial data or
a typed error.

The HTTP-layer TTL cache (`src/cache.py`) also sharply cuts real upstream
calls: ETAs are cached `cache_ttl_eta` seconds (default 10), weather 30s,
incidents 120s, and the dedicated `/v1/weather/hk` endpoint 10 min.

---

## 4. Error handling & retry

Every provider client subclasses `BaseClient`, which translates raw
`requests` failures and HTTP status codes into a typed exception hierarchy
(`src/clients/exceptions.py`):

| Exception | Trigger | Retryable? |
|---|---|---|
| `UpstreamAuthError` | 401 / 403 | No (permanent) |
| `UpstreamRateLimitError` | 429, or local limiter blocked | Yes |
| `UpstreamServerError` | 5xx | Yes |
| `UpstreamTimeoutError` | request timeout | Yes |
| `UpstreamConnectionError` | DNS / connection refused | Yes |
| `UpstreamError` | other 4xx / unknown | No (permanent) |

### Retry / backoff
Transient errors (retryable ones) are retried with **exponential backoff +
jitter**:

```
sleep = min(RETRY_BACKOFF_MAX, RETRY_BACKOFF_BASE * 2**attempt) * uniform(0.5, 1.0)
```

- `MAX_RETRIES` (default `3`) — total attempts = 1 initial + N retries.
- `RETRY_BACKOFF_BASE` (default `0.25`s), `RETRY_BACKOFF_MAX` (default `4`s).

A `Retry-After` header on a `429` is captured on the exception
(`exc.retry_after`) for callers that want to honour it. Permanent errors
(`UpstreamAuthError`, other 4xx) are raised immediately without retry.

### How callers use it
- **`BusStopService`** (combined endpoint) wraps each provider in `_safe()` and,
  with `degrade_on_upstream_error=True` (default), logs the typed error and
  returns partial data (empty ETAs / `None` weather) with HTTP `200`. With it
  `False`, the typed error propagates to the route, which answers `500` with
  the standard `Error` envelope.
- The app's global exception handler (`app.py`) catches any unhandled
  `Exception` and returns the spec-shaped `Error` envelope (code
  `INTERNAL_ERROR`), so a provider crash never leaks a raw trace.

---

## 5. Module map

| File | Responsibility |
|---|---|
| `src/clients/base.py` | `BaseClient`: cache + auth header + rate-limit gate + retry/backoff + status→typed-error. |
| `src/clients/exceptions.py` | Typed upstream exception hierarchy. |
| `src/clients/ratelimit.py` | Thread-safe token-bucket `RateLimiter`. |
| `src/clients/kmb.py` | KMB ETA + stop client (`provider="kmb"`). |
| `src/clients/citybus.py` | Citybus/NWFB client (`provider="citybus"`, `co` CTB/NWFB). |
| `src/clients/hko.py` | HKO weather client (`provider="hko"`). |
| `src/clients/td.py` | TD traffic-incident client (`provider="td"`). |
| `src/cache.py` | In-memory TTL cache. |
| `config/settings.py` | All auth / rate-limit / retry tunables (env-driven). |
| `src/services/bus_stop.py` | `BusStopService` aggregation (fail-soft). |

---

## 6. Testing

- `tests/test_clients_infra.py` — offline unit tests for auth-header injection,
  the rate limiter (capacity/blocking, cache bypass), status→typed-error
  mapping, retry-then-success, retry exhaustion, no-retry-on-auth, connection/
  timeout wrapping, and `Cache-Control: max-age` TTL honouring. All stub
  `requests.get`, so they run without network.
- `tests/test_backend_integration.py` — live end-to-end tests that hit the real
  feeds (skipped automatically when there is no network egress).
- `tests/test_clients.py` / `tests/test_clients_eta.py` — offline transform
  tests against recorded fixtures.
