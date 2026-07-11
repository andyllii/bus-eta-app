/**
 * useEtaData — data-fetching hook for the combined route/stop board.
 *
 * Responsibilities (per the task): fetch the combined ETA + weather + route-
 * relevant traffic incidents from the PRIMARY endpoint, and keep it fresh:
 *  * Initial load on mount / when route+stop+lang changes.
 *  * Periodic refresh so ETAs/weather/incidents stay current (bus ETAs change
 *    minute-to-minute). Defaults to 30s, overridable.
 *  * Pull-to-refresh (manual) for immediate updates.
 *  * Loading state (first load only) vs. background refresh state.
 *  * Hard error (first load failed) vs. soft error (a periodic refresh failed
 *    but we already have data — keep showing the last good data + a banner).
 *  * `degraded` surfaced so the UI can tell the user some data is partial.
 *
 * The hook does NOT resolve language; it just requests `lang` from the API and
 * the caller/provider supplies the active language. Components resolve text at
 * render time via resolveText. 404s raise a hard error (unknown route/stop).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api';
import { ApiError, EtaAggregate, Lang } from './types';

const DEFAULT_REFRESH_MS = 30_000;

export interface EtaDataState {
  data: EtaAggregate | null;
  loading: boolean; // initial load in progress (no data yet)
  refreshing: boolean; // background / pull-to-refresh in progress
  error: string | null; // hard error (no data to show)
  softError: string | null; // refresh failed but we have stale data
  degraded: boolean; // last successful load was partial
  lastUpdated: Date | null;
  reload: () => void;
  refresh: () => void; // pull-to-refresh
}

export function useEtaData(
  route: string | undefined,
  stop: string | undefined,
  lang: Lang,
  refreshMs: number = DEFAULT_REFRESH_MS
): EtaDataState {
  const [data, setData] = useState<EtaAggregate | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [softError, setSoftError] = useState<string | null>(null);
  const [degraded, setDegraded] = useState<boolean>(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const mounted = useRef(true);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(
    async (isInitial: boolean) => {
      if (!route || !stop) {
        setError('Select a route and a stop first.');
        setLoading(false);
        return;
      }
      if (isInitial) {
        setLoading(true);
        setError(null);
      } else {
        setRefreshing(true);
      }
      setSoftError(null);

      try {
        const res = await api.getEta(route, stop, lang);
        if (!mounted.current) return;
        setData(res);
        setDegraded(res.degraded);
        setLastUpdated(new Date());
        setError(null);
        setSoftError(null);
      } catch (e) {
        if (!mounted.current) return;
        const msg = e instanceof Error ? e.message : String(e);
        if (isInitial) {
          setError(msg);
          setData(null);
          setDegraded(false);
        } else {
          // Background refresh failed: keep stale data, surface a soft error.
          setSoftError(msg);
        }
      } finally {
        if (mounted.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [route, stop, lang]
  );

  // Initial load + re-fetch when the route/stop/language changes.
  useEffect(() => {
    mounted.current = true;
    load(true);
    return () => {
      mounted.current = false;
    };
  }, [load]);

  // Periodic background refresh while we have a valid route+stop.
  useEffect(() => {
    if (!route || !stop || refreshMs <= 0) return;
    timer.current = setInterval(() => {
      if (mounted.current) load(false);
    }, refreshMs);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [load, refreshMs, route, stop]);

  const reload = useCallback(() => {
    load(true);
  }, [load]);

  const refresh = useCallback(() => {
    load(false);
  }, [load]);

  return {
    data,
    loading,
    refreshing,
    error,
    softError,
    degraded,
    lastUpdated,
    reload,
    refresh,
  };
}

export type { ApiError };
