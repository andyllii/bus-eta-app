import {
  ApiError,
  EtaAggregate,
  ETA,
  Lang,
  MultilingualText,
  SearchHit,
  SearchResponse,
} from './types';

/** Sentinel base used to force mock mode (kept in sync with mock.ts). */
const MOCK_API_BASE = '__mock__';

/**
 * Base URL for the backend.
 *
 * In dev we use a RELATIVE path — Vite proxies /api/* and /v1/* to the running
 * FastAPI backend (see vite.config.ts), so there is no CORS or localhost issue
 * and a production build works same-origin behind any static host / proxy.
 *
 * Override with VITE_API_BASE (e.g. an absolute URL) only when the web bundle
 * is served on a different origin than the backend.
 */
const API_BASE: string =
  (typeof import.meta !== 'undefined' &&
    (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE) ||
  '';

/** When true, the API layer returns mock data instead of hitting the network. */
const USE_MOCK: boolean =
  (typeof import.meta !== 'undefined' &&
    (import.meta as unknown as { env?: Record<string, string> }).env
      ?.VITE_USE_MOCK) === 'true' ||
  API_BASE === MOCK_API_BASE;

const DEFAULT_LANG: Lang = 'tc';

/** Convert a snake_case key to camelCase. */
function camel(key: string): string {
  return key.replace(/_([a-z])/g, (_m, c: string) => c.toUpperCase());
}

/** Deep-map an object/array from snake_case keys to camelCase. */
function toCamel(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(toCamel);
  if (value && typeof value === 'object' && value.constructor === Object) {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[camel(k)] = toCamel(v);
    }
    return out;
  }
  return value;
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { Accept: 'application/json' },
      signal,
    });
  } catch (networkErr) {
    throw new ApiError(0, {
      code: 'NETWORK_ERROR',
      message: 'Cannot reach the transit service. Check your connection.',
      detail: String(networkErr),
    });
  }

  if (!res.ok) {
    let body: { code?: string; message?: string; detail?: string | null } = {};
    try {
      body = await res.json();
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, {
      code: body.code || 'HTTP_ERROR',
      message: body.message || `Request failed (${res.status}).`,
      detail: body.detail ?? null,
    });
  }

  const raw = (await res.json()) as unknown;
  return toCamel(raw) as T;
}

/** Map a raw (camelCased) ETA into our display-friendly shape. */
function normalizeEta(raw: Record<string, unknown>): ETA {
  const remark = (raw.remark as MultilingualText | null | undefined) ?? null;
  return {
    co: (raw.co as string) ?? '',
    route: (raw.route as string) ?? '',
    direction: (raw.direction as 'O' | 'I') ?? 'O',
    serviceType: (raw.serviceType as number) ?? 1,
    seq: (raw.seq as number) ?? 0,
    dest: (raw.dest as ETA['dest']) ?? { en: '', tc: '', sc: '' },
    etaSeq: (raw.etaSeq as number) ?? 0,
    eta: (raw.eta as string) ?? '',
    minutesRemaining:
      raw.minutesRemaining === null || raw.minutesRemaining === undefined
        ? null
        : (raw.minutesRemaining as number),
    remark,
    dataTimestamp: (raw.dataTimestamp as string) ?? '',
    // status is derived at render time from the resolved remark; seed default.
    status: (raw.eta as string) ? 'live' : 'scheduled',
  };
}

/**
 * PRIMARY: combined route/stop board.
 * Calls GET /api/v1/eta?route=<route>&stop=<stop>&lang=<lang> and returns the
 * assembled EtaAggregate (ETAs + weather + route-relevant incidents).
 *
 * Falls back to mock data when the backend is unreachable, so the UI always
 * has something to render in a demo/offline context. Set VITE_USE_MOCK=true
 * to force mock data unconditionally.
 */
export async function getEta(
  route: string,
  stop: string,
  lang: string = DEFAULT_LANG,
  signal?: AbortSignal
): Promise<EtaAggregate> {
  if (USE_MOCK) {
    const { getMockEta } = await import('./mock');
    return getMockEta(route, stop, lang);
  }
  try {
    const data = await request<Record<string, unknown>>(
      `/api/v1/eta?route=${encodeURIComponent(route)}&stop=${encodeURIComponent(
        stop
      )}&lang=${lang}`,
      signal
    );
    const rawEtas = (data.etas as Record<string, unknown>[]) ?? [];
    const rawIncidents = (data.incidents as Record<string, unknown>[]) ?? [];
    return {
      query: (data.query as EtaAggregate['query']) ?? {
        route,
        stopId: stop,
        operator: null,
        lang,
      },
      etas: rawEtas.map(normalizeEta),
      weather: (data.weather as EtaAggregate['weather']) ?? null,
      incidents: rawIncidents as unknown as EtaAggregate['incidents'],
      queryTime: (data.queryTime as string) ?? '',
      degraded: Boolean(data.degraded),
    };
  } catch (err) {
    if (err instanceof ApiError && (err.status === 0 || err.status >= 500)) {
      const { getMockEta } = await import('./mock');
      const mock = getMockEta(route, stop, lang);
      return mock;
    }
    throw err;
  }
}

/** Server-backed autocomplete for the Search screen. */
export async function search(
  q: string,
  lang: string = DEFAULT_LANG,
  signal?: AbortSignal
): Promise<SearchResponse> {
  if (USE_MOCK) {
    const { getMockSearch } = await import('./mock');
    return getMockSearch(q, lang);
  }
  try {
    const data = await request<Record<string, unknown>>(
      `/api/v1/search?q=${encodeURIComponent(q)}&lang=${lang}`,
      signal
    );
    return {
      query: (data.query as string) ?? q,
      lang: (data.lang as string) ?? lang,
      total: (data.total as number) ?? 0,
      stops: (data.stops as SearchHit[]) ?? [],
      routes: (data.routes as SearchHit[]) ?? [],
    };
  } catch (err) {
    if (err instanceof ApiError && (err.status === 0 || err.status >= 500)) {
      const { getMockSearch } = await import('./mock');
      return getMockSearch(q, lang);
    }
    throw err;
  }
}

/** Default route numbers offered as quick-pick chips on the Search screen. */
export const DEFAULT_ROUTES: string[] = ['1', '10', '113', '11K'];

/** Resolve a friendly, localised stop name from a search hit or raw id. */
export function localizeStopName(
  hit: SearchHit | null,
  id: string,
  lang: string
): string {
  if (hit?.name) {
    const n = hit.name as MultilingualText;
    return n[lang as keyof MultilingualText] || n.tc || n.en || n.sc || id;
  }
  return id;
}

export const api = {
  base: API_BASE,
  useMock: USE_MOCK,
  getEta,
  search,
  localizeStopName,
  DEFAULT_ROUTES,
};
