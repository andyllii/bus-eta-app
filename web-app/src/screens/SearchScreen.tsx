import { memo, useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLanguage } from '../lang-context';
import { resolveText } from '../i18n';
import { api, search } from '../services/api';
import { SearchHit, Lang } from '../services/types';

interface Hit extends SearchHit {
  /** client-computed secondary line for the row */
  sublabel?: string;
}

/**
 * A single result row, memoized so the parent re-render (e.g. the typing
 * cursor's `query` state bump) does not rebuild every row. The row only
 * re-renders when its own props change.
 */
const HitRow = memo(function HitRow({
  hit,
  lang,
  onSelect,
}: {
  hit: Hit;
  lang: Lang;
  onSelect: (hit: Hit) => void;
}) {
  return (
    <li key={`${hit.kind}-${hit.id}`}>
      <button
        onClick={() => onSelect(hit)}
        data-testid="search-result"
        data-kind={hit.kind}
        data-id={hit.id}
        className="flex min-h-[44px] w-full items-center justify-between rounded-xl bg-white px-4 py-3 text-left shadow-sm ring-1 ring-gray-100 active:bg-gray-50"
      >
        <span className="min-w-0">
          <span className="block truncate font-medium text-gray-900">
            {hit.kind === 'route'
              ? `路線 ${hit.id}`
              : resolveText(hit.name, lang)}
          </span>
          {hit.sublabel && (
            <span className="block truncate text-xs text-gray-500">
              {hit.sublabel}
            </span>
          )}
        </span>
        <span
          className={`ml-3 shrink-0 rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${
            hit.kind === 'route'
              ? 'bg-brand text-white'
              : 'bg-gray-200 text-gray-600'
          }`}
        >
          {hit.kind === 'route' ? 'Route' : 'Stop'}
        </span>
      </button>
    </li>
  );
});

/**
 * Home / Search screen. Debounced server-backed autocomplete over
 * GET /api/v1/search. Selecting a stop (optionally with a chosen route) or a
 * route navigates into the Results view with the right params.
 *
 * Performance notes:
 *  - The search request is cancelled (AbortController) whenever the query or
 *    language changes, so only the latest keystroke's results land on screen.
 *  - Out-of-order responses are discarded via a generation counter.
 *  - Empty queries short-circuit before any network call / state churn.
 *  - Result rows are memoized (see HitRow) to keep re-renders local.
 */
export function SearchScreen() {
  const { lang } = useLanguage();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<Hit[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounce = useRef<ReturnType<typeof setTimeout>>();
  // Monotonic id so a slow earlier request can never overwrite a newer one.
  const reqId = useRef(0);

  // Reset any stale route context when arriving here fresh.
  useEffect(() => {
    setHits([]);
    setError(null);
  }, [lang]);

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      // Avoid clobbering results with a loading flash when the box is emptied.
      clearTimeout(debounce.current);
      setHits([]);
      setLoading(false);
      setError(null);
      return;
    }
    setLoading(true);
    clearTimeout(debounce.current);
    const mine = ++reqId.current;
    const controller = new AbortController();
    debounce.current = setTimeout(async () => {
      try {
        const res = await search(q, lang, controller.signal);
        if (mine !== reqId.current) return; // a newer keystroke superseded us
        const next: Hit[] = [
          ...res.routes.map((h) => ({
            ...h,
            sublabel: resolveText(h.name, lang),
          })),
          ...res.stops.map((h) => ({
            ...h,
            sublabel: h.routes && h.routes.length ? h.routes.join(' · ') : '',
          })),
        ];
        setHits(next);
        setError(null);
      } catch (e) {
        if (controller.signal.aborted || mine !== reqId.current) return;
        setError(e instanceof Error ? e.message : 'Search failed');
      } finally {
        if (mine === reqId.current) setLoading(false);
      }
    }, 250);
    return () => {
      clearTimeout(debounce.current);
      controller.abort();
    };
  }, [query, lang]);

  const goToResults = useCallback(
    (hit: Hit) => {
      if (hit.kind === 'route') {
        // Route picked with no specific stop yet — go to a route-scoped board.
        navigate(`/results?route=${encodeURIComponent(hit.id)}`);
      } else {
        navigate(`/results?stop=${encodeURIComponent(hit.id)}`);
      }
    },
    [navigate]
  );

  // Warm the lazy ResultsScreen chunk on idle so tapping a search result
  // navigates instantly instead of waiting for the JS to download. This keeps
  // the results code out of the initial bundle (fast first paint) while
  // eliminating the delay on the most common next action.
  useEffect(() => {
    const preload = () => {
      void import('./ResultsScreen').catch(() => {
        /* non-fatal: the real click will attempt the import again */
      });
    };
    const ric = (window as unknown as {
      requestIdleCallback?: (cb: () => void) => number;
    }).requestIdleCallback;
    if (ric) ric(preload);
    else setTimeout(preload, 1200);
  }, []);

  // Chips / quick-picks are static, so memoize to avoid re-creating closures.
  const chips = useMemo(
    () =>
      api.DEFAULT_ROUTES.map((r) => (
        <li key={r}>
          <button
            onClick={() => navigate(`/results?route=${encodeURIComponent(r)}`)}
            className="inline-flex min-h-[44px] items-center rounded-full bg-brand/10 px-4 text-sm font-medium text-brand"
          >
            路線 {r}
          </button>
        </li>
      )),
    [navigate]
  );

  return (
    <div className="mx-auto max-w-app px-4 py-4">
      <div className="mb-4">
        <p className="text-sm text-gray-600">
          搜尋路線或車站 · Search routes or stops
        </p>
      </div>

      <form
        role="search"
        onSubmit={(e) => e.preventDefault()}
        className="relative"
      >
        <input
          type="search"
          inputMode="search"
          autoComplete="off"
          aria-label="Search routes or stops"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. 1 / 長沙灣廣場 / Central"
          data-testid="search-input"
          className="min-h-[44px] w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-base shadow-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/30"
        />
        {loading && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400"
          >
            …
          </span>
        )}
      </form>

      {error && (
        <p
          role="alert"
          className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {error}
        </p>
      )}

      {/* Quick-pick chips for the most common routes (44px touch targets) */}
      <ul className="mt-4 flex flex-wrap gap-2">{chips}</ul>

      <ul
        className="mt-4 space-y-2"
        aria-label="Search results"
        aria-busy={loading}
        aria-live="polite"
      >
        {hits.map((hit) => (
          <HitRow key={`${hit.kind}-${hit.id}`} hit={hit} lang={lang} onSelect={goToResults} />
        ))}
      </ul>

      {query.trim() && !loading && hits.length === 0 && !error && (
        <p className="mt-6 text-center text-sm text-gray-400">
          沒有結果 · No results
        </p>
      )}
    </div>
  );
}
