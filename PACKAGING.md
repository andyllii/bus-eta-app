# Packaging Report — t_dcb43164

Generated: 2026-07-11
Packager: `nata` (kanban profile)
Source workspace: `t_b3fe8645` (canonical, verified builds)
Deliverable: `bus-eta-app-v1.0.0.tar.gz` (root folder `bus-eta-app/`)

## What was delivered

A single self-contained monorepo combining the completed backend (task
t_844e668b) and frontends (tasks t_e9572496 / mobile) into one shippable unit:

- `transportation-api/` — FastAPI backend (9 endpoints, validated OpenAPI 3.1,
  113-test suite, live + mock modes).
- `transportation-app/` — React Native + Expo mobile app (iOS/Android/web).
- `web-app/` — Vite + React + Tailwind PWA build.
- `design/` — `DESIGN.md`, canonical `bus-eta-openapi.yaml`, design mockups,
  and the upstream verification reports (`BACKEND_FOLLOWUP.md`,
  `FRONTEND_VERIFICATION.md`).
- Root: `README.md` (full run/deploy guide), `Dockerfile`, `docker-compose.yml`,
  `nginx.conf`, `docker-entrypoint.sh`, `Procfile`, `.dockerignore`,
  `smoke-test.sh`.

## Packaging decisions

- **Excluded** from the archive: Python `.venv/`, `node_modules/`, build
  output (`dist/`, `web-build/`), runtime logs, `.pytest_cache/`, `.expo/`,
  Playwright/chrome browser dirs, and all ad-hoc developer probe scripts
  (`_*.py` / `_*.cjs` / `_*.js`). Kept all real `__init__.py` modules (the
  import-critical ones — a naive `_*.py` exclude would have dropped them, which
  was caught and fixed during verification).
- **Secrets:** the live `.env` files were **not** shipped — only `.env.example`
  (no credentials) travels with the repo.
- **Deploy config added** (the only outstanding item from the parent tasks):
  multi-stage `Dockerfile` that builds the web bundle and runs API (`:8000`) +
  Nginx-served PWA (`:4173`); `docker-compose.yml` for one-command bring-up;
  `Procfile` for PaaS; `smoke-test.sh` to validate a running server.

## Verification performed (real execution)

1. **Backend imports** from the shipped artifact → OK
   (`香港交通資訊聚合 API v0.2.0`).
2. **Backend test suite** run from a *fresh extraction* of the tarball →
   `113 passed, 1 warning` (mock-isolated).
3. **Live end-to-end smoke test** against the running packaged backend
   (`./smoke-test.sh`) → all 8 checks PASS: `/health`, `/openapi.json`,
   `/api/v1/eta`, `/api/v1/search`, `/api/v1/weather`, `/api/v1/incidents`,
   `/v1/bus-stops/{id}` (200), and the unknown-stop 404 path.
4. **Archive integrity** → 206 entries, tar gzip extracts cleanly; confirmed
   no dev probes, no `.env` secrets, no `node_modules`/`.venv`/cache dirs.

## Size

- Unpacked: ~3.0 MB (source only; deps install on `pip install` / `npm install`).
- Archive: `bus-eta-app-v1.0.0.tar.gz` ≈ 1.7 MB.

## How the user receives it

Deliverable path (on this host):
`/opt/data/kanban/workspaces/t_dcb43164/bus-eta-app-v1.0.0.tar.gz`

To use:
```bash
tar -xzf bus-eta-app-v1.0.0.tar.gz
cd bus-eta-app
# quickest full stack:
cd transportation-api && ./start.sh --mock &   # API on :8000
cd ../web-app && npm install && npm run dev      # web on :5173
# or containerized:
docker compose up --build                        # API :8000 + web :4173
```
Full instructions are in `README.md`.
