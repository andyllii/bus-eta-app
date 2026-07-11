/**
 * API client for the Bus ETA backend.
 *
 * PRIMARY endpoint: GET /api/v1/eta?route=<route>&stop=<stop> — the new
 * aggregation endpoint that returns the combined ETA + weather + route-relevant
 * traffic incidents in a single call (see transportation-api/docs/api_v1_eta.md).
 *
 * Wire contract (verified against the running API): keys are snake_case and
 * all human-readable text arrives as multilingual objects `{ en, tc, sc }`.
 * We deep-map the payload into the camelCase display shapes declared in
 * types.ts, and the rest of the UI resolves language at render time via
 * resolveText (i18n.ts). This keeps a clean camelCase app model without
 * leaking the wire format into every component.
 *
 * The base URL is configurable via EXPO_PUBLIC_API_BASE (defaults to the local
 * backend dev server). Point it at the running transportation-api service, e.g.
 * EXPO_PUBLIC_API_BASE=http://192.168.1.50:8000 npx expo start
 *
 * Search is now a real backend call: the Search screen queries
 * GET /api/v1/search?q=<text>&lang=<lang> on every keystroke (debounced),
 * and the suggestions list is replaced by the server's stop + route hits. On
 * selection the screen validates the (route, stop) pair against the primary
 * endpoint before navigating into the Results view.
 */
import {
  ApiError,
  EtaAggregate,
  ETA,
  SearchHit,
  SearchResponse,
} from './types';

/**
 * Base URL for the backend. Defaults to a RELATIVE path so a production web
 * build works same-origin (the bundle is served behind a proxy/static host
 * that forwards /api/* to the backend) without any CORS or localhost issues.
 * For native (Expo Go / device) or a dev web server on a different origin, set
 * EXPO_PUBLIC_API_BASE to the absolute backend URL, e.g.
 * EXPO_PUBLIC_API_BASE=http://192.168.1.50:8000 npx expo start --web
 */
const API_BASE: string =
  (typeof process !== 'undefined' &&
    process.env &&
    process.env.EXPO_PUBLIC_API_BASE) ||
  '';

const DEFAULT_LANG = 'tc';

/** Convert a snake_case key to camelCase (e.g. data_timestamp -> dataTimestamp). */
function camel(key: string): string {
  return key.replace(/_([a-z])/g, (_m, c) => c.toUpperCase());
}

/**
 * Deep-map an object/array from snake_case keys to camelCase. Leaves values
 * untouched (multilingual objects and scalars pass through unchanged).
 */
function toCamel(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(toCamel);
  }
  if (value && typeof value === 'object' && value.constructor === Object) {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[camel(k)] = toCamel(v);
    }
    return out;
  }
  return value;
}

async function request<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { Accept: 'application/json' },
    });
  } catch (networkErr) {
    // Network failure (API down / unreachable). Surface a clear error so the
    // UI can show its error state.
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
      // non-JSON error body
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
  const remarkObj = (raw.remark as Record<string, unknown> | null | undefined) ?? null;
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
    remark: (remarkObj as ETA['remark']) ?? null,
    dataTimestamp: (raw.dataTimestamp as string) ?? '',
    // status is derived at render time from the resolved remark (i18n.etaLiveStatus),
    // but we seed a default here; screens may recompute after language resolution.
    status: 'scheduled',
  };
}

/**
 * PRIMARY: combined route/stop board. Calls
 * GET /api/v1/eta?route=<route>&stop=<stop>&lang=<lang> and returns the
 * assembled EtaAggregate (ETAs + weather + route-relevant incidents).
 */
export async function getEta(
  route: string,
  stop: string,
  lang: string = DEFAULT_LANG
): Promise<EtaAggregate> {
  const data = await request<Record<string, unknown>>(
    `/api/v1/eta?route=${encodeURIComponent(route)}&stop=${encodeURIComponent(
      stop
    )}&lang=${lang}`
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
}

/**
 * Validate a (route, stop) pair by probing the primary endpoint without
 * throwing on a 404. Used by the Search screen so we only navigate to a
 * results view that will actually have data. Returns true on a 2xx response.
 */
export async function checkRouteStop(
  route: string | null,
  stop: string,
  lang: string = DEFAULT_LANG
): Promise<boolean> {
  try {
    if (route) {
      await getEta(route, stop, lang);
    } else {
      // No specific route chosen → just confirm the stop resolves.
      const ok = await checkStop(stop, lang);
      return ok;
    }
    return true;
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.code === 'RESOURCE_NOT_FOUND')) {
      return false;
    }
    // Any other error (network/5xx) — don't block navigation; let the results
    // screen surface it. Treat as "valid" so the user can still try.
    return true;
  }
}

/**
 * Confirm a stop id resolves at all (used when no route is selected).
 * NOTE: the backend's stop-combined endpoint is mounted at `/v1/bus-stops/{id}`
 * (prefix `/v1`, NOT `/api/v1`). We probe it and treat any non-404 as
 * "resolvable" so the user can still open the Results view for that stop.
 */
async function checkStop(stop: string, lang: string): Promise<boolean> {
  let res: Response;
  const url = `${API_BASE}/v1/bus-stops/${encodeURIComponent(stop)}?lang=${lang}`;
  try {
    res = await fetch(url, {
      headers: { Accept: 'application/json' },
    });
  } catch {
    return true; // network error → don't block
  }
  return res.ok || res.status !== 404;
}

/**
 * Server-backed autocomplete for the Search screen. Calls
 * GET /api/v1/search?q=<text>&lang=<lang> and returns the unified stop +
 * route hits. The backend does the multilingual matching, so we just forward
 * the raw query string and the active language.
 */
export async function search(
  q: string,
  lang: string = DEFAULT_LANG
): Promise<SearchResponse> {
  const data = await request<Record<string, unknown>>(
    `/api/v1/search?q=${encodeURIComponent(q)}&lang=${lang}`
  );
  return {
    query: (data.query as string) ?? q,
    lang: (data.lang as string) ?? lang,
    total: (data.total as number) ?? 0,
    stops: (data.stops as SearchHit[]) ?? [],
    routes: (data.routes as SearchHit[]) ?? [],
  };
}

/**
 * Default route numbers offered as quick-pick chips on the Search screen.
 *
 * Anchored to the routes that the live backend actually serves ETAs for at the
 * verified default stop (946C74E30100FE80 / Cheung Sha Wan Plaza): 1, 10, 113,
 * 11K. These all resolve to live arrivals through GET /api/v1/eta, so any chip
 * selection lands on a populated Results view.
 */
export const DEFAULT_ROUTES: string[] = ['1', '10', '113', '11K'];

/**
 * Resolve a friendly, localised stop name for a given stop id from a search hit
 * (preferred) or the raw id. Used to label the Results header in the active
 * language (the ETA API itself does not return a stop name).
 */
export function localizeStopName(hit: SearchHit | null, id: string, lang: string): string {
  if (hit?.name) {
    const n = hit.name as Record<string, string | null | undefined>;
    return n[lang] || n.tc || n.en || n.sc || id;
  }
  return id;
}

export const api = {
  base: API_BASE,
  getEta,
  checkRouteStop,
  search,
  localizeStopName,
  DEFAULT_ROUTES,
};
