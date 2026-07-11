# Transportation App (React Native + Expo)

Mobile front end for the Hong Kong bus ETA service. Consumes the
`transportation-api` backend and renders live bus arrivals, weather, and
traffic incidents.

## Screens

- **Search** — route/stop search + favourites list. Tapping a favourite opens
  the ETA view for that stop. Hosts the language switcher (EN / 繁 / 简).
- **Arrivals (ETA)** — the combined stop view: stop header with a live
  "updated HH:MM" line, a scrollable list of per-route arrival cards, and a
  pull-to-refresh control.
- **Info (Contextual)** — same data with the weather widget and dismissible
  traffic-alert banners surfaced up front.

All three screens read from the single primary backend endpoint
`GET /v1/bus-stops/{stopId}` (see `bus-eta-openapi.yaml`).

## Live data integration

- `src/services/api.ts` — typed fetch client. Performs a **deep snake_case →
  camelCase** mapping of the wire payload and normalises ETAs. Throws a typed
  `ApiError` (code + message) on non-OK responses and a `NETWORK_ERROR`
  `ApiError` when the request cannot reach the server.
- `src/services/types.ts` — TypeScript models. **All human-readable text is
  multilingual** (`{ en, tc, sc }`), matching the backend `MultilingualText`
  model.
- `src/services/i18n.tsx` — `LanguageProvider` / `useLanguage` plus
  `resolveText` (collapses a multilingual field to the active language, with
  tc → en → sc fallback) and `etaLiveStatus` (derives live/scheduled from the
  remark).
- `src/services/useBusStopData.ts` — data hook handling initial load,
  **periodic refresh (every 30s)**, **pull-to-refresh**, hard-error vs
  soft-error states (a failed background refresh keeps the last good data and
  shows a retry banner), and `lastUpdated`.

### Connecting to the backend

The base URL is read from `EXPO_PUBLIC_API_BASE` (default `http://localhost:8000`).
To run against the real API from a device/emulator, set it to the host's LAN
address, e.g.:

```
EXPO_PUBLIC_API_BASE=http://192.168.1.50:8000 npx expo start
```

The backend must be running (`USE_MOCK_DATA=1` works fully offline):

```
cd ../transportation-api && USE_MOCK_DATA=1 uvicorn app:app --port 8000
```

## Scripts

- `npm run typecheck` — `tsc --noEmit`
- `npm test` — compiles the services and runs the API-contract test against a
  realistic backend payload (`scripts/contract_test.cjs`).
- `npm run test:live` — compiles the services and drives the **real** client
  against a running backend (`scripts/live_contract_test.cjs <baseUrl>`),
  asserting the full fetch → normalize → i18n → error-path chain.
- `npx expo start` — run the app (Metro dev server).

## Note on Metro / Hermes in this environment

`tsc --noEmit` and `expo export --no-bytecode` both succeed (the JS bundle
builds, ~855 modules). The Hermes **bytecode** compile step fails only because
the `hermesc` native binary cannot run in this sandbox (ELF limitation) — it is
not a code defect and works on a normal host/CI.
