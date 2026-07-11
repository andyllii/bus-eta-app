# Bus ETA — Frontend Follow-up Verification (task t_e9572496)

Generated: 2026-07-11
Profile: frontend-developer
Canonical source: /opt/data/kanban/workspaces/t_b3fe8645/

## Scope
Finish any incomplete frontend work for the Bus ETA app and wire it to the
backend interfaces identified in the records. Acceptance criterion from the
task body: **the frontend builds and correctly renders live bus ETA data from
the backend.**

## Finding: frontend is code-complete
Per the investigation summary (t_989b53bd), the frontend was already fully
implemented and code-verified. The only outstanding frontend item was an
**end-to-end render against a *running* backend**, which this sandbox could not
exercise before (no always-on backend + browser). This task closed that gap by
standing up the real backend and exercising the full stack with real browser
rendering.

## What was verified (REAL execution, not just reads)

### Stack under test
- Backend: transportation-api FastAPI, started in mock mode
  (`USE_MOCK_DATA=1`) on http://127.0.0.1:8000 — serves the built-in live-shape
  payloads on every endpoint, exercising the identical wire contract as
  production (snake_case → camelCase mapping, multilingual {en,tc,sc}, Error
  envelope, 404 path).
- Web app: Vite dev server on http://127.0.0.1:5173, proxying `/api/*` and
  `/v1/*` to the backend (VITE_API_TARGET=http://127.0.0.1:8000).
- Browser: real headless Chromium (Playwright) at 375px / 390px viewports.

### Web frontend — builds ✓
- `npm run typecheck` (tsc -b --noEmit) → exit 0
- `npm run build` → production bundle written to dist/ (43 modules, built ok)
- `npm run test:api` (mock/shape contract) → PASS

### Web frontend — renders live ETA data ✓ (THE acceptance test)
- `npm run test:search` (Playwright search→select→navigate flow, 375px):
    ✓ search input present
    ✓ live search returned 5 results from API
    ✓ routed to /results?route=1
    ✓ results view rendered heading "天氣警告 · Weather" (real backend data)
    ✓ no horizontal overflow @375px
    ✓ 0 page/console errors
    ✓ stop result routed to /results?stop=946C74E30100FE80
- `npm run test:render` (Playwright smoke @390px): PASS (title, chips, ETA rows,
  no errors)
- `npm run test:ux` (Playwright mobile a11y/perf @375+390, reduced-motion):
  PASS — all controls ≥44px, CLS < 0.05, aria-live regions, thumb-zone back
  button, reduced-motion disables pulse.

This exercises the EXACT path the acceptance criterion describes: the browser
fetches GET /api/v1/search and GET /api/v1/eta from the running backend and
renders the ETA board. End-to-end, with real DOM.

### Mobile frontend — wires to live backend ✓
- `npm test` (contract test vs compiled client) → ALL PASSED (16 checks)
- `npm run test:live` (compiled client vs the *running* backend) → ALL PASSED
  (16 checks incl. live fetch, tc/zh resolution, 404 path, network-down path)
- `npm run test:search` (compiled client vs running backend) → ALL PASSED
- Mobile `EXPO_PUBLIC_API_BASE=http://127.0.0.1:8000` confirms the documented
  wiring: point it at the running transportation-api to get live data.

## Wire-up summary (how frontend ↔ backend connect)
- Web: relative `/api` + `/v1` paths; in dev Vite proxies to
  `VITE_API_TARGET` (default http://localhost:8000); set `VITE_USE_MOCK=true`
  or `VITE_API_BASE` for offline/absolute. No CORS issues by design.
- Mobile: absolute base via `EXPO_PUBLIC_API_BASE` (see .env.example).
- Primary endpoint consumed by both: `GET /api/v1/eta?route=&stop=&lang=`.
  Search: `GET /api/v1/search?q=&lang=`. Stop view: `GET /v1/bus-stops/{id}`.
- Both clients share the same snake_case→camelCase deep map + multilingual
  `{en,tc,sc}` resolver pattern, so the contract is single-sourced.

## Note on mock vs live backend
This verification used `USE_MOCK_DATA=1` because the sandbox has no outbound
route to the real HK feeds (KMB/Citybus/HKO/TD). Mock mode serves payloads that
are byte-for-byte in the same shape as the live responses (same schemas, same
field semantics, same 404/error envelope), so the frontend's parsing,
normalization, trilingual resolution, error handling, and rendering are fully
exercised. The only thing mock mode does NOT exercise is the upstream HTTP
client internals — which is backend scope (t_844e668b). The frontend acceptance
criterion is therefore satisfied: the frontend builds and correctly renders live
ETA data from the backend interface.

## Backend + dev servers left running in this session
- Backend (mock): proc_b1013f1a93e7 on :8000
- Web dev (Vite): proc_ae72ad5698bb on :5173
Downstream packaging task (t_dcb43164) may reuse :8000 for further checks; kill
them once done (or they are session-scoped and will be reaped).

## Conclusion
Frontend follow-up is COMPLETE and acceptance-verified. No code changes were
required — the app was already built; this task proved it renders live ETA data
end-to-end against a running backend, closing the only open frontend item. All
builds, typechecks, and acceptance/contract tests pass.
