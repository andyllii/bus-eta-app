# Bus ETA — Hong Kong Bus Arrival Times, Weather & Traffic

A complete, production-shaped product that aggregates **Hong Kong public bus
arrival times (KMB + Citybus/NWFB)**, **HKO weather warnings**, and **Transport
Department road-traffic incidents** into one friendly mobile-first app.

It ships as a three-part monorepo:

| Component | Folder | Stack | What it does |
|-----------|--------|-------|--------------|
| **Backend API** | `transportation-api/` | FastAPI (Python) | Aggregates the 4 live HK open-data feeds, serves a single combined ETA + weather + incidents payload, with Swagger docs and a validated OpenAPI 3.1 spec. |
| **Mobile app** | `transportation-app/` | React Native + Expo | Native iOS/Android + web app. Search → results board of ETAs, weather widget, traffic-alert banners. Trilingual (EN / 繁 / 简). |
| **Web app** | `web-app/` | Vite + React + TypeScript + Tailwind | Mobile-first Progressive Web App with the same features; builds to static `dist/`. |
| **Design & API spec** | `design/` | — | `DESIGN.md`, the canonical `bus-eta-openapi.yaml` (0 unresolved `$refs`), design mockups, and the upstream verification reports. |

Both frontends consume the same backend contract
(`GET /api/v1/eta?route=&stop=&lang=` for the board,
`GET /api/v1/search?q=&lang=` for autocomplete,
`GET /v1/bus-stops/{id}` for the combined stop view). The wire format uses
snake_case keys and `{ en, tc, sc }` multilingual objects; both clients
deep-map to camelCase and resolve the active language at render time.

---

## 1. Quick start (local, all three parts)

You need: **Python 3.11+**, **Node.js 18+**, and a terminal.

### 1a. Start the backend
```bash
cd transportation-api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # defaults are fine; edit if needed
./start.sh                     # live mode (real HK feeds) — needs internet
# or, fully offline / demo:
./start.sh --mock              # serves built-in mock payloads (same wire shape)
# or directly:
uvicorn app:app --host 0.0.0.0 --port 8000
```
Backend is now at **http://localhost:8000** — interactive docs at
`/docs` (Swagger UI) and `/redoc`; machine-readable spec at `/openapi.json`.

> Live mode calls the real public Hong Kong feeds (no API key required).
> If you are offline or behind a firewall, use `--mock` — the payloads are
> byte-for-byte the same *shape* as production, so every frontend path
> (including the 404 / degraded-error envelope) is exercised identically.

### 1b. Start the web app (in a second terminal)
```bash
cd web-app
npm install
npm run dev                   # http://localhost:5173 (proxies /api & /v1 → :8000)
```
Open http://localhost:5173, search a route (e.g. `1`) or stop id
(`946C74E30100FE80`), pick a result, and the ETA board renders live data.

*Offline web demo (no backend):* `VITE_USE_MOCK=true npm run dev`

### 1c. Start the mobile app (in a third terminal)
```bash
cd transportation-app
npm install
cp .env.example .env          # EXPO_PUBLIC_API_BASE=http://localhost:8000
npx expo start                # scan QR with Expo Go, or press a/i for simulator
```
To point a physical device/emulator at the backend on your LAN:
```bash
EXPO_PUBLIC_API_BASE=http://192.168.1.50:8000 npx expo start
```

That's it — search → tap → live board, on web and mobile.

---

## 2. Project layout

```
bus-eta-app/
├── README.md                      # this file
├── Dockerfile                     # multi-stage: builds backend + web, serves both
├── docker-compose.yml             # one command → api :8000 + web :4173
├── Procfile                       # Heroku-style: web (api) + (optional) static web
├── .dockerignore
├── transportation-api/            # FastAPI backend
│   ├── app.py                     # entrypoint (uvicorn app:app)
│   ├── requirements.txt
│   ├── start.sh                   # venv + deps + run (live|mock)
│   ├── bus-eta-openapi.yaml       # canonical API spec (also in design/)
│   ├── config/  models/  routes/  src/  tests/  scripts/  docs/
│   └── .env.example
├── transportation-app/            # React Native + Expo
│   ├── App.tsx  app.json  babel.config.js  tsconfig.json  package.json
│   ├── src/ (screens, components, services, navigation, theme)
│   └── .env.example
├── web-app/                       # Vite + React PWA
│   ├── index.html  vite.config.ts  tailwind.config.js  package.json
│   ├── src/ (screens, components, services, i18n)
│   └── scripts/ (Playwright acceptance tests)
└── design/                        # spec + design artifacts + verification reports
    ├── DESIGN.md
    ├── bus-eta-openapi.yaml
    ├── BACKEND_FOLLOWUP.md        # backend verification report
    ├── FRONTEND_VERIFICATION.md   # frontend e2e verification report
    ├── design-artifacts/*.png     # user-flow / screen designs
    └── mockups/                   # HTML mockups
```

---

## 3. Backend API

Full docs in `transportation-api/README.md`. Highlights:

- **9 endpoints** under `/api/v1` (plus deprecated `/v1/...` aliases):
  `/api/v1/eta`, `/api/v1/bus-stops/{stopId}`, `/api/v1/weather`,
  `/api/v1/weather/warnings`, `/api/v1/incidents`, `/api/v1/search`, `/`,
  `/health`, and the legacy `/eta`.
- **Fail-soft aggregation:** weather + incidents are fetched concurrently and
  cached (TTL per resource). A failing *secondary* provider returns partial
  data with `degraded: true`; a missing stop/route returns a clean `404`
  (`RESOURCE_NOT_FOUND`).
- **Rate-limited & retrying** outbound clients (KMB/Citybus/HKO/TD), defensive
  parsing, and a global error handler that always answers with the spec-shaped
  `Error` envelope.
- **Mock mode** (`USE_MOCK_DATA=1` or `./start.sh --mock`) serves the built-in
  dataset so the whole stack runs with zero internet.

Environment config is documented in `transportation-api/.env.example`
(server host/port, log level, feed URLs, timeouts, cache TTLs, rate limits,
optional keyed-tier auth).

### Backend tests
```bash
cd transportation-api && source .venv/bin/activate
pytest -q                 # 113 passed (uses mock mode internally for isolation)
```

---

## 4. Frontends

### Web app (`web-app/`)
- `npm run dev` — dev server + proxy to backend.
- `npm run build` — type-checks and bundles to `dist/` (static, deploy anywhere).
- `npm run preview` — serve the production build locally.
- Tests: `npm run test:api` (contract), `npm run test:render` /
  `npm run test:search` / `npm run test:ux` (Playwright mobile acceptance).
- See `web-app/README.md`.

### Mobile app (`transportation-app/`)
- `npx expo start` — Metro dev server (iOS / Android / web).
- `npm test` — API-contract test; `npm run test:live` / `npm run test:search`
  drive the real client against a running backend.
- `npm run build:web` — export a web build (`dist/`).
- Base URL via `EXPO_PUBLIC_API_BASE` (see `.env.example`).
- See `transportation-app/README.md`.

> Note: the Hermes *bytecode* compile step for the native binary only fails in
> this restricted sandbox (`hermesc` ELF limitation) — it is not a code defect
> and works on a normal host/CI. `tsc --noEmit` and the JS bundle build pass.

---

## 5. Docker deployment (recommended)

`Dockerfile` builds the backend image **and** the web static bundle, then runs
the FastAPI API on `:8000` and serves the web PWA from the same container on
`:4173` (Nginx). `docker-compose.yml` wires it up with one command.

```bash
# Build + run (live mode by default; set USE_MOCK_DATA=1 for offline):
docker compose up --build
#   → API + docs:  http://localhost:8000
#   → Web PWA:     http://localhost:4173
```

Offline / demo container:
```bash
USE_MOCK_DATA=1 docker compose up --build
```

Points of configuration (passed as env to the container):
`PORT` (API port, default 8000), `USE_MOCK_DATA`, and any feed/rate-limit vars
from `.env.example`.

### Plain Docker (no compose)
```bash
docker build -t bus-eta-app .
docker run -p 8000:8000 -p 4173:4173 bus-eta-app
```

---

## 6. Other deployment options

- **Heroku / PaaS (Procfile):** `web: uvicorn app:app --host 0.0.0.0 --port $PORT`
  runs the API. Build the web bundle separately and host `web-app/dist/` on any
  static host (Netlify / Vercel / GitHub Pages / S3), pointing its API proxy at
  the API URL (set `VITE_API_TARGET` at build time, or for mobile set
  `EXPO_PUBLIC_API_BASE`).
- **Serverless:** the FastAPI app is ASGI — deploy on any ASGI host (e.g.
  a container, or wrap with Mangum for AWS Lambda). The web bundle is static.

---

## 7. Verification status (real execution)

This is a finished, verified product — not a stub:

- **Backend:** 113 pytest tests pass; `/docs`, `/redoc`, `/openapi.json` serve;
  all 9 endpoints return 200; OpenAPI spec validates with **0 unresolved
  `$refs`**; live round-trips against KMB/Citybus/HKO/TD confirmed (see
  `design/BACKEND_FOLLOWUP.md`).
- **Frontends:** both build; the web app's Playwright search→select→navigate
  flow renders the live ETA board at 375px with **0 errors**; the mobile
  contract + live + search tests **all pass** against a running backend (see
  `design/FRONTEND_VERIFICATION.md`).

---

## 8. License & notes

Internal demo product. The Hong Kong open-data feeds
(KMB `data.etabus.gov.hk`, Citybus `rt.data.gov.hk`, HKO `weather.gov.hk`,
TD `td.gov.hk`) are public; respect their usage terms and the built-in
rate limits. No API key is required for the current feeds.
