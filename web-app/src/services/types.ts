/**
 * TypeScript projection of the Bus ETA API data models for the web app.
 *
 * Wire contract (verified live against GET /api/v1/eta on the FastAPI backend):
 *  - Keys arrive snake_case (service_type, eta_seq, data_timestamp, …).
 *  - Human-readable text arrives as a multilingual object { en, tc, sc }.
 * The API client (api.ts) deep-maps snake_case → camelCase and the rest of the
 * app works in camelCase, resolving the active language at render time.
 */

export type Lang = 'en' | 'tc' | 'sc';

/** A multilingual text field as it appears on the wire: { en, tc, sc }. */
export interface MultilingualText {
  en?: string | null;
  tc?: string | null;
  sc?: string | null;
}

/** A predicted arrival of a route at a stop. */
export interface ETA {
  co: string; // company code, e.g. 'KMB'
  route: string;
  direction: 'O' | 'I';
  serviceType: number;
  seq: number;
  dest: MultilingualText;
  etaSeq: number;
  eta: string; // ISO-8601 predicted arrival (UTC) — may be null
  minutesRemaining?: number | null;
  remark?: MultilingualText | null;
  dataTimestamp: string;
  /** 'live' = real-time GPS, 'scheduled' = timetable. Derived at render time. */
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
  }> | null;
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

/** Echo of the resolved query params for GET /api/v1/eta. */
export interface EtaQuery {
  route: string;
  stopId: string;
  operator?: string | null;
  lang: string;
}

/** Combined view returned by the PRIMARY aggregation endpoint. */
export interface EtaAggregate {
  query: EtaQuery;
  etas: ETA[];
  weather?: Weather | null;
  incidents: Incident[];
  queryTime: string;
  /** true when a secondary provider failed and was skipped (partial data). */
  degraded: boolean;
  /** Present only on mock responses, so the UI can flag demo data. */
  mock?: boolean;
}

/** A server-side search hit (stop or route) from GET /api/v1/search. */
export interface SearchHit {
  id: string;
  kind: 'route' | 'stop';
  operator?: string | null;
  name?: MultilingualText | null;
  address?: MultilingualText | null;
  location?: { lat: number; lon: number } | null;
  routes?: string[];
}

/** Unified autocomplete response from GET /api/v1/search. */
export interface SearchResponse {
  query: string;
  lang: string;
  total: number;
  stops: SearchHit[];
  routes: SearchHit[];
}

/** Structured error envelope returned by the API. */
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
