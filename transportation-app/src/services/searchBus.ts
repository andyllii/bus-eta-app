/**
 * searchBus — UI-agnostic backend search client for the bus app.
 *
 * This module is intentionally FREE of any React / UI code. It is the single
 * data layer the Search view calls to turn a raw text query into a flat list
 * of `{ id, label, type }` results, ready to render as one uniform
 * autocomplete list (stops mixed with routes). The wire contract, error
 * handling and language resolution all live here so the screen stays thin.
 *
 * Backend endpoint (see transportation-api/routes/search.py):
 *
 *     GET /api/v1/search?q=<text>&lang=<lang>&limit_stops=8&limit_routes=8
 *
 * The backend returns a unified response with two arrays:
 *
 *     { query, lang, total, stops: SearchHit[], routes: SearchHit[] }
 *
 * where each `SearchHit` carries `{ id, kind: 'route' | 'stop', name?,
 * destinations?, operator?, routes? }`. This module flattens both arrays into
 * `BusSearchResult[]`, resolving a display `label` for each kind:
 *
 *   * stop   → the resolved stop name (or the raw id if no name is present)
 *   * route  → `<route> · <outbound terminal>` (terminal resolved from the
 *              `destinations.O` multilingual object; falls back to the raw id)
 *
 * Behaviour guaranteed by the contract:
 *   - Returns a Promise that resolves to `BusSearchResult[]`.
 *   - Resolves to `[]` when the backend returns no hits (HTTP 200, empty).
 *   - Resolves to `[]` when the query is empty/blank (avoids an unnecessary
 *     round-trip; the screen shows the curated default set from elsewhere).
 *   - Rejects with `ApiError` (carrying status + code + message) on any
 *     non-2xx response, so the caller can show its error state distinctly
 *     from the empty-result state.
 *   - Rejects with `ApiError` (status 0) on a network failure.
 *
 * The base URL honours `EXPO_PUBLIC_API_BASE` (defaults to a relative path so
 * a production web build works same-origin behind the proxy, exactly like
 * `api.ts`).
 */

import { ApiError, BusSearchResult } from './types';

/**
 * Base URL for the backend. Mirrors `api.ts`: relative by default (so a
 * same-origin production web build just works) and overridable via
 * EXPO_PUBLIC_API_BASE for native / cross-origin dev.
 */
const API_BASE: string =
  (typeof process !== 'undefined' &&
    process.env &&
    process.env.EXPO_PUBLIC_API_BASE) ||
  '';

const DEFAULT_LANG = 'tc';

/**
 * Resolve the best available string for a multilingual field in the requested
 * language, falling back tc -> en -> sc (so the UI never shows an empty value,
 * even when the backend only carries `en`). Kept local to avoid pulling the
 * React `i18n.tsx` context into this UI-free module — `resolveText` from
 * i18n.tsx has identical semantics but drags in React.
 */
function pickLabel(
  field: { en?: string | null; tc?: string | null; sc?: string | null } | null | undefined
): string {
  if (!field) return '';
  return field.tc || field.en || field.sc || '';
}

/**
 * Map one backend `SearchHit` (already camelCased by the shared `request`
 * helper semantics) into a flat `BusSearchResult`.
 *
 * `hit` is typed loosely as `Record<string, unknown>` because the wire shape
 * arrives as dynamic JSON; we read only the fields we need defensively.
 */
function mapHit(hit: Record<string, unknown>): BusSearchResult | null {
  const id = typeof hit.id === 'string' ? hit.id : '';
  if (!id) return null;

  const type = hit.kind === 'route' ? 'route' : 'stop';

  let label: string;
  if (type === 'route') {
    // Route label: "<route> · <outbound terminal>".
    const dests = (hit.destinations as
      | Record<string, { en?: string | null; tc?: string | null; sc?: string | null } | null>
      | null
      | undefined) || {};
    const terminal = pickLabel(dests.O);
    label = terminal ? `${id} · ${terminal}` : id;
  } else {
    // Stop label: resolved stop name, or the raw id when missing.
    const name = hit.name as
      | { en?: string | null; tc?: string | null; sc?: string | null }
      | null
      | undefined;
    const nameStr = pickLabel(name);
    label = nameStr || id;
  }

  return { id, label, type };
}

/**
 * Public entry point.
 *
 * @param query  Free-text query: stop name, stop id, or route number.
 * @param lang   Active UI language ('en' | 'tc' | 'sc'). Defaults to 'tc'.
 * @param limit  Max hits per kind to request from the backend (default 8).
 * @returns A Promise resolving to the flattened, display-ready result list.
 *          Resolves to `[]` for empty queries or empty backend results.
 *          Rejects with `ApiError` on HTTP error or network failure.
 */
export async function searchBus(
  query: string,
  lang: string = DEFAULT_LANG,
  limit = 8
): Promise<BusSearchResult[]> {
  const q = (query || '').trim();
  if (!q) {
    // Empty query → no results (the screen seeds its own default list set).
    return [];
  }

  const params = new URLSearchParams({
    q,
    lang,
    limit_stops: String(limit),
    limit_routes: String(limit),
  });

  const url = `${API_BASE}/api/v1/search?${params.toString()}`;

  let res: Response;
  try {
    res = await fetch(url, { headers: { Accept: 'application/json' } });
  } catch (networkErr) {
    throw new ApiError(0, {
      code: 'NETWORK_ERROR',
      message: 'Cannot reach the transit search service. Check your connection.',
      detail: String(networkErr),
    });
  }

  if (!res.ok) {
    let body: { code?: string; message?: string; detail?: string | null } = {};
    try {
      body = (await res.json()) as typeof body;
    } catch {
      // non-JSON error body → keep defaults
    }
    throw new ApiError(res.status, {
      code: body.code || 'HTTP_ERROR',
      message: body.message || `Search request failed (${res.status}).`,
      detail: body.detail ?? null,
    });
  }

  // The backend ships snake_case; we camelCase keys here (mirroring api.ts)
  // so the downstream `mapHit` reads `kind`/`destinations`/`name`.
  const raw = (await res.json()) as unknown;
  const camel = toCamel(raw) as Record<string, unknown>;
  const stops = (camel.stops as Record<string, unknown>[]) || [];
  const routes = (camel.routes as Record<string, unknown>[]) || [];

  const results: BusSearchResult[] = [];
  for (const hit of stops) {
    const mapped = mapHit({ ...hit, kind: 'stop' });
    if (mapped) results.push(mapped);
  }
  for (const hit of routes) {
    const mapped = mapHit({ ...hit, kind: 'route' });
    if (mapped) results.push(mapped);
  }

  return results;
}

/** snake_case → camelCase, mirrored verbatim from api.ts (kept local/DOM-safe). */
function toCamel(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(toCamel);
  if (value && typeof value === 'object' && value.constructor === Object) {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k.replace(/_([a-z])/g, (_m, c: string) => c.toUpperCase())] = toCamel(v);
    }
    return out;
  }
  return value;
}

export default searchBus;
