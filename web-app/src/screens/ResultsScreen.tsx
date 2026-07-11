import { memo, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useLanguage } from '../lang-context';
import { resolveText } from '../i18n';
import { getEta, localizeStopName } from '../services/api';
import {
  ApiError,
  EtaAggregate,
  ETA,
  Incident,
  WeatherWarning,
} from '../services/types';
import {
  BusIcon,
  MapPin,
  Thunderstorm,
  WarningTriangle,
  WeatherIcon,
} from '../components/icons';

function formatEta(eta: ETA, lang: string): { primary: string; tag: string } {
  if (eta.minutesRemaining === null || eta.minutesRemaining === undefined) {
    const remark = eta.remark ? resolveText(eta.remark, lang as never) : '';
    return { primary: remark || '—', tag: 'departed' };
  }
  const m = eta.minutesRemaining;
  const primary =
    lang === 'en'
      ? m <= 0
        ? 'Due'
        : `${m} min`
      : m <= 0
        ? '即將到達'
        : `${m} 分鐘`;
  const tag = 'live';
  return { primary, tag };
}

/** Severity → Tailwind palette (icon + badge + accent rule). */
const WEATHER_SEVERITY: Record<
  string,
  { wrap: string; icon: string; rule: string }
> = {
  red: {
    wrap: 'bg-red-50 ring-red-200',
    icon: 'text-red-600',
    rule: 'border-l-red-500',
  },
  black: {
    wrap: 'bg-gray-900 ring-black/40',
    icon: 'text-white',
    rule: 'border-l-black',
  },
  amber: {
    wrap: 'bg-amber-50 ring-amber-200',
    icon: 'text-amber-600',
    rule: 'border-l-amber-400',
  },
  warning: {
    wrap: 'bg-orange-50 ring-orange-200',
    icon: 'text-orange-500',
    rule: 'border-l-orange-400',
  },
};
const WEATHER_DEFAULT = {
  wrap: 'bg-gray-50 ring-gray-200',
  icon: 'text-gray-500',
  rule: 'border-l-gray-300',
};

const INCIDENT_RELEVANCE: Record<
  string,
  { wrap: string; icon: string; label: string }
> = {
  high: {
    wrap: 'bg-red-50 ring-red-200',
    icon: 'text-red-600',
    label: 'HIGH',
  },
  medium: {
    wrap: 'bg-amber-50 ring-amber-200',
    icon: 'text-amber-600',
    label: 'MED',
  },
  low: {
    wrap: 'bg-blue-50 ring-blue-200',
    icon: 'text-blue-600',
    label: 'LOW',
  },
};
const INCIDENT_DEFAULT = {
  wrap: 'bg-gray-50 ring-gray-200',
  icon: 'text-gray-500',
  label: '',
};

const SectionHeader = memo(function SectionHeader({
  icon,
  title,
}: {
  icon: React.ReactNode;
  title: string;
}) {
  return (
    <div className="mb-2 flex items-center gap-2">
      <span className="text-brand">{icon}</span>
      <h2 className="text-sm font-semibold tracking-wide text-gray-700">
        {title}
      </h2>
    </div>
  );
});

const WeatherBadge = memo(function WeatherBadge({
  warning,
}: {
  warning: WeatherWarning;
}) {
  const { lang } = useLanguage();
  const sev = WEATHER_SEVERITY[warning.severity] || WEATHER_DEFAULT;
  const dark = warning.severity === 'black';
  return (
    <div
      className={`flex items-start gap-3 rounded-xl border-l-4 px-4 py-3 ring-1 ${sev.wrap} ${sev.rule}`}
    >
      <span className={`shrink-0 ${sev.icon}`}>
        <WeatherIcon warning={warning} className="h-7 w-7" />
      </span>
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span
            className={`text-sm font-bold ${dark ? 'text-white' : 'text-gray-900'}`}
          >
            {resolveText(warning.title, lang)}
          </span>
          <span
            className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
              dark ? 'bg-white/20 text-white' : 'bg-white/70 text-gray-500'
            }`}
          >
            {warning.severity}
          </span>
        </div>
        {warning.contents && (
          <p
            className={`mt-1 text-xs leading-snug ${
              dark ? 'text-white/90' : 'text-gray-600'
            } line-clamp-3`}
          >
            {warning.contents}
          </p>
        )}
      </div>
    </div>
  );
});

const IncidentCard = memo(function IncidentCard({
  incident,
}: {
  incident: Incident;
}) {
  const { lang } = useLanguage();
  const rel = INCIDENT_RELEVANCE[incident.relevance || ''] || INCIDENT_DEFAULT;
  return (
    <li
      className={`flex items-start gap-3 rounded-xl border-l-4 px-4 py-3 ring-1 ${rel.wrap} ${
        incident.relevance === 'high'
          ? 'border-l-red-500'
          : incident.relevance === 'medium'
            ? 'border-l-amber-400'
            : incident.relevance === 'low'
              ? 'border-l-blue-400'
              : 'border-l-gray-300'
      }`}
    >
      <span className={`mt-0.5 shrink-0 ${rel.icon}`}>
        <WarningTriangle className="h-6 w-6" />
      </span>
      <div className="min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="font-medium text-gray-900">
            {resolveText(incident.heading, lang)}
          </span>
          {rel.label && (
            <span className="shrink-0 rounded bg-white/70 px-2 py-0.5 text-[10px] font-semibold uppercase text-gray-500">
              {rel.label}
            </span>
          )}
        </div>
        <p className="mt-1 flex items-center gap-1 text-xs text-gray-500">
          <MapPin className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">
            {resolveText(incident.location, lang)}
            {incident.status
              ? ` · ${resolveText(incident.status, lang)}`
              : ''}
          </span>
        </p>
        {incident.content && (
          <p className="mt-2 text-sm leading-snug text-gray-700">
            {resolveText(incident.content, lang)}
          </p>
        )}
      </div>
    </li>
  );
});

/**
 * Results screen. Consumes GET /api/v1/eta?route/stop and renders the combined
 * ETA board + weather warnings + route-relevant traffic incidents, each with a
 * clear visual indicator and a mobile-first visual hierarchy.
 *
 * UX-polish notes:
 *  - Child sections are memoized (see SectionHeader/WeatherBadge/IncidentCard)
 *    and the ETA row list is derived with useMemo, so a re-render (e.g. a
 *    language toggle) only touches what actually changed.
 *  - The content area reserves a min-height so swapping the loading spinner for
 *    real data never shifts layout (zero CLS).
 *  - A thumb-reachable back-to-search bar is pinned to the bottom so the view
 *    works single-handed; every interactive control is ≥44px tall.
 */
export function ResultsScreen() {
  const { lang } = useLanguage();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const route = params.get('route') || '';
  const stop = params.get('stop') || '946C74E30100FE80';

  const [data, setData] = useState<EtaAggregate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    getEta(route, stop, lang, controller.signal)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof DOMException && e.name === 'AbortError') return;
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : 'Failed to load data');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [route, stop, lang]);

  const stopName = data
    ? localizeStopName(null, data.query.stopId, lang)
    : stop;

  // Derived ETA rows — recomputed only when the data or language changes.
  const etaRows = useMemo(() => {
    if (!data) return [];
    return data.etas.map((eta, i) => {
      const { primary, tag } = formatEta(eta, lang);
      const departed = tag === 'departed';
      return (
        <li
          key={`${eta.route}-${eta.etaSeq}-${i}`}
          className="flex items-center justify-between rounded-xl bg-white px-4 py-3 shadow-sm ring-1 ring-gray-100"
        >
          <div className="min-w-0">
            <span className="font-medium text-gray-900">
              {resolveText(eta.dest, lang)}
            </span>
            <span className="ml-2 text-xs text-gray-400">
              {eta.co} · {eta.serviceType}
            </span>
          </div>
          <span
            className={`ml-3 inline-flex min-h-[44px] shrink-0 items-center gap-1.5 rounded-lg px-3 py-1 text-sm font-bold ${
              departed ? 'bg-gray-100 text-gray-500' : 'bg-brand/10 text-brand'
            }`}
          >
            {!departed && (
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand/60" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-brand" />
              </span>
            )}
            {primary}
          </span>
        </li>
      );
    });
  }, [data, lang]);

  const weatherWarnings = data?.weather?.warnings ?? [];
  const incidents = data?.incidents ?? [];

  return (
    <div className="mx-auto max-w-app px-4 py-4">
      <button
        onClick={() => navigate('/')}
        data-testid="back-to-search-top"
        aria-label="Back to search"
        className="mb-3 inline-flex min-h-[44px] items-center text-sm text-brand"
      >
        ← 返回 · Back
      </button>

      {/* Demo-data banner. We reserve its exact height in EVERY state (the box
          is always h-[34px] + mb-3; the amber fill + text only appear in mock
          mode) so the banner's appearance never shifts layout (CLS = 0). The
          Suspense fallback reserves the same height. */}
      <div
        className={`mb-3 flex h-[34px] items-center rounded-lg px-3 text-xs ${
          data?.mock ? 'bg-amber-50 text-amber-800' : ''
        }`}
      >
        {data?.mock && '示範數據 · Demo data (backend unavailable)'}
      </div>

      {error && !loading && (
        <p
          role="alert"
          className="mt-6 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {error}
        </p>
      )}

      {/* Reserve vertical space so loading → data swap never shifts layout.
          The wrapper announces busy state to assistive tech. */}
      <div className="min-h-[60dvh]" aria-busy={loading || undefined}>
        {loading && (
          <p
            role="status"
            aria-live="polite"
            className="mt-10 text-center text-sm text-gray-400"
          >
            載入中 · Loading…
          </p>
        )}

        {data && !loading && (
          <>
            {/* Header */}
            <div className="mb-4 flex items-center gap-3 rounded-xl bg-brand px-4 py-3 text-white">
              <span className="shrink-0">
                <BusIcon className="h-8 w-8" />
              </span>
              <div className="min-w-0">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-lg font-bold">
                    {route ? `路線 ${route}` : '車站 · Stop'}
                  </span>
                  <span className="text-xs opacity-80">
                    {data.query.operator || ''}
                  </span>
                </div>
                <p className="mt-0.5 truncate text-sm opacity-90">{stopName}</p>
              </div>
            </div>

            {/* Weather warnings */}
            {weatherWarnings.length > 0 && (
              <div className="mb-5">
                <SectionHeader
                  icon={<Thunderstorm className="h-5 w-5" />}
                  title="天氣警告 · Weather"
                />
                <div className="space-y-2">
                  {weatherWarnings.map((w, i) => (
                    <WeatherBadge key={`${w.code}-${i}`} warning={w} />
                  ))}
                </div>
              </div>
            )}

            {/* ETA board */}
            <div className="mb-5">
              <SectionHeader
                icon={<BusIcon className="h-5 w-5" />}
                title="到站時間 · Arrivals"
              />
              <ul
                className="space-y-2"
                aria-label="Arrival times"
                aria-live="polite"
              >
                {etaRows.length === 0 && (
                  <li className="rounded-xl bg-white px-4 py-3 text-sm text-gray-500 shadow-sm ring-1 ring-gray-100">
                    暫無班次 · No upcoming departures
                  </li>
                )}
                {etaRows}
              </ul>
            </div>

            {/* Incidents */}
            {incidents.length > 0 && (
              <div className="mt-5">
                <SectionHeader
                  icon={<WarningTriangle className="h-5 w-5" />}
                  title="交通意外 · Traffic incidents"
                />
                <ul className="space-y-2">
                  {incidents.map((inc) => (
                    <IncidentCard key={inc.id} incident={inc} />
                  ))}
                </ul>
              </div>
            )}

            {data.degraded && (
              <p className="mt-4 text-center text-xs text-gray-400">
                部分數據未能載入 · Some data degraded
              </p>
            )}
          </>
        )}
      </div>

      {/* Single-handed navigation: thumb-reachable back bar pinned to bottom. */}
      <nav className="sticky bottom-0 z-10 -mx-4 mt-6 border-t border-gray-200 bg-white/95 backdrop-blur">
        <div className="mx-auto max-w-app px-4 py-3">
          <button
            onClick={() => navigate('/')}
            data-testid="back-to-search"
            aria-label="Back to search"
            className="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl bg-brand text-sm font-semibold text-white active:bg-brand-dark"
          >
            ← 返回搜尋 · Back to search
          </button>
        </div>
      </nav>
    </div>
  );
}
