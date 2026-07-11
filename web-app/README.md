# Transportation Web App

Mobile-first web app for the Hong Kong bus ETA service, built with **Vite + React + TypeScript + Tailwind CSS**. This is the dedicated web client (distinct from the React Native / Expo `transportation-app`).

## Features
- Mobile-first responsive layout (phone-width column, safe-area aware).
- Home / Search screen with debounced, server-backed autocomplete (`GET /api/v1/search`).
- Results screen consuming the combined aggregation endpoint (`GET /api/v1/eta`) — ETAs, weather warnings, and route-relevant traffic incidents.
- Trilingual UI (EN / 繁 / 简) resolved from the backend's `{ en, tc, sc }` multilingual fields.
- Real API layer with automatic **mock fallback** when the backend is unreachable, so the UI always renders.

## Getting started
```bash
cd web-app
npm install
npm run dev          # http://localhost:5173 (proxies /api/* to :8000)
```
In dev, Vite proxies `/api` and `/v1` to the FastAPI backend (`http://localhost:8000`). Point it elsewhere with `VITE_API_TARGET`.

Force mock/demo data (no backend needed):
```bash
VITE_USE_MOCK=true npm run dev
```

## Build
```bash
npm run build        # type-checks + bundles to dist/
npm run preview      # serve the production build
```

## API layer
- `src/services/types.ts` — TypeScript projections of the API models.
- `src/services/api.ts` — fetch client; deep-maps snake_case → camelCase, calls `/api/v1/eta` and `/api/v1/search`, falls back to mock on network/5xx errors.
- `src/services/mock.ts` — demo data matching the live payload shapes.
- `src/i18n.ts` — `resolveText()` multilingual resolver.

Wire contract (verified against the live backend):
`GET /api/v1/eta?route=&stop=&lang=` returns `{ query, etas[], weather, incidents[], query_time, degraded }`.

## Tests
```bash
npm run test:api       # validates the mock/data shapes the screens rely on
npm run test:render    # Playwright: Smoke-renders at 390px, loads a results view
npm run test:search    # Playwright: full search→select→navigate flow at 375px
npm run test:ux        # Playwright: mobile UX/perf pass at 375px + 390px + reduced-motion
```

`test:search` is the acceptance test for the Search view: it types a query,
waits for live results from `GET /api/v1/search`, taps a result, and asserts
the app routes to `/results?route=<id>` (or `?stop=<id>`) on a 375px-wide
mobile viewport with no horizontal overflow and no page errors. It needs the
dev server (or `npm run preview`) running and reachable at `BASE`
(default `http://localhost:5173`).

`test:ux` verifies the mobile polish pass against emulated phones:
- every interactive control (search, chips, language switch, ETA pills, back
  buttons) is ≥44px tall (WCAG 2.5.5);
- **cumulative layout shift < 0.05** when the results view swaps its loading
  state for real data;
- no horizontal overflow at 375px / 390px;
- the back-to-search control sits in the lower (thumb) half of the viewport;
- the search form is `role="search"` with an accessible name, results are an
  `aria-live` region, and back controls carry `aria-label`s;
- the live-ETA "pulse" is disabled under `prefers-reduced-motion`.
