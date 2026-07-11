# Bus ETA — UI/UX Mockups & User-Flow Blueprint

High-fidelity mockups and a user-flow diagram for the Bus ETA mobile app.
These are the design blueprint the frontend implementation is built against.

## Deliverables (rendered PNGs in `design-artifacts/`)
| File | Screen |
|------|--------|
| `00_user_flow.png` | End-to-end user-flow diagram (screens + cross-cutting states) |
| `01_search.png` | ① Route / Stop Search screen |
| `02_eta_list.png` | ② ETA arrivals list (route-scoped board) |
| `03_weather_traffic.png` | ②+③ Integrated weather + traffic alerts (stop-scoped board) |

Editable source for each lives alongside as `mockups/<name>.html` (self-contained,
reuses the real compiled Tailwind stylesheet `web-app/dist/assets/index-*.css`, so
the mockups are pixel-faithful to the shipped app). Re-render with:

    cd web-app && node _render_mockups.mjs

## Design language (matching the real app)
- **Brand**: `#1d4ed8` (dark `#1e3a8a`), used for header, primary button, ETA pills, links.
- **Surface**: gray-50 page, white rounded-xl cards with `ring-1 ring-gray-100` + soft shadow.
- **Layout**: content capped at `max-w-app` = 480px; mobile-first, never scrolls horizontally.
- **Touch targets**: every control ≥ 44px tall (iOS HIG / Material minimum).
- **Type**: system-ui sans; bilingual EN / 繁 / 简 via the top-bar global switcher.
- **Icons**: dependency-free inline SVG (`web-app/src/components/icons.tsx`),
  recolored by `currentColor` so weather/incident cards change hue by severity.

## Key screens

### ① Search (route / stop)
- Sticky brand top bar with EN / 繁 / 简 language switcher.
- Debounced server-backed autocomplete over **routes AND stops** (`GET /api/v1/search`).
- Quick-pick chips for the four most common routes (1, 10, 113, 11K) for zero-typing access.
- Results render as Route rows (blue ROUTE badge) or Stop rows (gray STOP badge, with
  the routes serving that stop as a sublabel). Tapping a route → route board;
  tapping a stop → stop board.

### ② ETA arrivals list
- Brand header card: route/stop name + operator (KMB) + destination.
- Live ETA rows: destination + `co · serviceType` sublabel on the left; a pulsing
  "Due / N min" pill on the right (gray "Scheduled" pill when no live ETA).
- Single-handed bottom nav: thumb-reachable "Back to search" bar pinned to the bottom.

### ③ Integrated weather + traffic (inline, not a separate screen)
- **Weather warnings** render as amber/red/black severity-coded cards (left accent rule
  + matching icon + severity badge), with `line-clamp-3` on the description.
- **Traffic incidents** render as relevance-ranked cards: HIGH (red) → MED (amber) → LOW (blue),
  each with a location line and status. They appear directly above/below the ETA list so the
  rider sees trip context without leaving the board.

## Cross-cutting states (shown in the flow diagram)
- **Language (EN/繁/简)** is global via the top bar and persists across screens.
- **Empty** ("No upcoming departures / 暫無班次") and **Error** ("Failed to load data")
  use the same reserved-height slots as the loaded state.
- **Offline / Demo mode** shows a fixed-height amber banner whose appearance never shifts
  layout — combined with the reserved loading/placeholder heights, this keeps CLS = 0.

## User flow (summary)
open → ① Search (autocomplete / chips) → pick route or stop → ② Arrivals board
(inline weather + traffic alerts) → ← Back to search (bottom bar).
Alerts are never a separate screen; they surface inline on the arrivals board.
