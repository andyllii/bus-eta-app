/**
 * TypeScript type projections of the Bus ETA API data models.
 *
 * Source of truth: the live `GET /api/v1/eta` aggregation endpoint (see
 * transportation-api/docs/api_v1_eta.md). That endpoint is the PRIMARY
 * endpoint the mobile app calls: it takes a `route` + `stop` and returns one
 * object with `etas`, `weather` and route-relevant `incidents` (each tagged
 * with a server-computed `relevance`), plus an echo of the resolved `query`
 * and a `degraded` flag.
 *
 * IMPORTANT — wire contract (verified against the running API):
 *  * All human-readable text arrives as a multilingual object `{ en, tc, sc }`
 *    (the backend `MultilingualText` model). The server does NOT resolve to a
 *    single scalar on the wire, so we keep the raw object and resolve the
 *    requested language at display time via `resolveText` (see i18n.ts).
 *  * Keys are snake_case (`service_type`, `eta_seq`, `data_timestamp`, …).
 *    The API client (api.ts) deep-maps them to the camelCase display shapes
 *    below, so the rest of the app works in camelCase.
 */

export type Lang = 'en' | 'tc' | 'sc';

/** A multilingual text field as it appears on the wire: { en, tc, sc }. */
export interface MultilingualText {
  en?: string | null;
  tc?: string | null;
  sc?: string | null;
}

/** A physical bus stop (used by the search suggestions). */
export interface BusStop {
  id: string; // KMB stop ID, 16-char hex (or 6-digit Citybus)
  name: MultilingualText; // resolved at display time
  location?: { lat: number; lon: number };
  address?: MultilingualText;
  routes: string[]; // route numbers serving the stop
  dataTimestamp?: string; // ISO-8601
}

/** A predicted arrival of a route at a stop. */
export interface ETA {
  co: string; // company code, e.g. 'KMB'
  route: string;
  direction: 'O' | 'I';
  serviceType: number;
  seq: number;
  dest: MultilingualText; // resolved at display time
  etaSeq: number;
  eta: string; // ISO-8601 predicted arrival (UTC)
  minutesRemaining?: number | null;
  remark?: MultilingualText | null; // resolved at display time
  dataTimestamp: string;
  /** 'live' = real-time GPS, 'scheduled' = timetable. Derived for display. */
  status: 'live' | 'scheduled';
}

export interface WeatherWarning {
  code: string;
  title: MultilingualText;
  severity: 'none' | 'amber' | 'red' | 'black' | 'warning';
  contents?: string;
  issueTime?: string;
}

export interface Weather {
  temperature?: { place: string; value: number; unit: string };
  description?: string;
  humidity?: { value: number; unit: string };
  icon?: number[];
  updateTime?: string;
  warnings: WeatherWarning[];
  forecast?: Array<{
    date?: string;
    week?: string | null;
    weather?: string;
    maxTemp?: number;
    minTemp?: number;
  }>;
}

export interface Incident {
  id: string;
  heading: MultilingualText;
  detail?: MultilingualText | null;
  location: MultilingualText;
  district?: MultilingualText | null;
  status?: MultilingualText | null;
  relevance?: 'high' | 'medium' | 'low' | 'none' | null;
  announcementDate?: string;
  content?: MultilingualText | null;
}

/** Echo of the resolved query params for `GET /api/v1/eta`. */
export interface EtaQuery {
  route: string;
  stopId: string;
  operator?: string | null;
  lang: string;
}

/**
 * Combined view returned by the PRIMARY aggregation endpoint
 * `GET /api/v1/eta?route=&stop=`. This is the single object the results screen
 * consumes to render ETAs + weather + route-relevant traffic incidents.
 */
export interface EtaAggregate {
  query: EtaQuery;
  etas: ETA[];
  weather?: Weather | null;
  incidents: Incident[];
  queryTime: string; // ISO-8601
  /** true when a secondary provider failed and was skipped (partial data). */
  degraded: boolean;
}

/** A server-side search hit (stop or route) from GET /api/v1/search. */
export interface SearchHit {
  id: string; // stop id (16-hex / 6-digit) or route number
  kind: 'route' | 'stop';
  operator?: string | null;
  name?: MultilingualText | null; // route name (optional)
  // stop fields
  address?: MultilingualText | null;
  location?: { lat: number; lon: number } | null;
  routes?: string[]; // routes serving a matched stop
  // route fields
  destinations?: Record<string, MultilingualText | string>;
  sublabel?: string; // client-computed secondary line
  /** True when this hit is a stop that also carries the chosen route. */
  _routeHint?: string;
}

/** Unified autocomplete response from GET /api/v1/search. */
export interface SearchResponse {
  query: string;
  lang: string;
  total: number;
  stops: SearchHit[];
  routes: SearchHit[];
}

/**
 * Flat, UI-agnostic search result. This is the shape `searchBus` resolves the
 * backend payload into so the Search view can render one uniform list (stops
 * mixed with routes) and route the user into the Results view with the correct
 * `id` + `type` on selection. It deliberately carries NO display logic or
 * navigation — just the three fields needed to build an option row.
 */
export interface BusSearchResult {
  /** Stop id (16-hex / 6-digit) or route number. */
  id: string;
  /** Human-friendly display label (resolved stop name, or route number + terminal). */
  label: string;
  /** Whether the hit is a route or a physical stop. */
  type: 'route' | 'stop';
}

/** Structured error envelope returned by the API (see Error schema). */
export interface ApiErrorBody {
  code: string;
  message: string;
  detail?: string | null;
}

export class ApiError extends Error {
  status: number;
  code: string;
  detail?: string | null;
  constructor(status: number, body: ApiErrorBody) {
    super(body.message || `API ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code;
    this.detail = body.detail ?? null;
  }
}
