import type { ReactNode } from 'react';
import type { WeatherWarning } from '../services/types';

/**
 * Dependency-free inline SVG icon set for the results view.
 *
 * Every icon inherits `currentColor`, so colour is driven entirely by the
 * surrounding Tailwind text-* class — this keeps the bundle tiny and lets the
 * weather/incident cards recolor by severity without extra CSS.
 */

type IconProps = { className?: string };

const base = (className = 'h-6 w-6') =>
  ({
    className,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  });

function Thunderstorm({ className }: IconProps) {
  return (
    <svg {...base(className)} aria-hidden="true">
      <path d="M19 14.5a3.5 3.5 0 0 0-.9-6.88A4.5 4.5 0 0 0 9.9 6.2 3 3 0 0 0 7 14" />
      <path d="M12.5 11.5l-2 3.5h3l-2 3.5" />
    </svg>
  );
}

function Rain({ className }: IconProps) {
  return (
    <svg {...base(className)} aria-hidden="true">
      <path d="M19 14.5a3.5 3.5 0 0 0-.9-6.88A4.5 4.5 0 0 0 9.9 6.2 3 3 0 0 0 7 14" />
      <path d="M8 18l-1 2.5M12 18l-1 2.5M16 18l-1 2.5" />
    </svg>
  );
}

function Hot({ className }: IconProps) {
  return (
    <svg {...base(className)} aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" />
    </svg>
  );
}

function Cold({ className }: IconProps) {
  return (
    <svg {...base(className)} aria-hidden="true">
      <path d="M12 2v20M4.2 7l15.6 10M19.8 7L4.2 17" />
      <path d="M12 5l-2.2-2.2M12 5l2.2-2.2M12 19l-2.2 2.2M12 19l2.2 2.2" />
      <path d="M6.5 9.5L4 8M6.5 9.5L9 8M17.5 14.5L20 16M17.5 14.5L15 16" />
    </svg>
  );
}

function Frost({ className }: IconProps) {
  return (
    <svg {...base(className)} aria-hidden="true">
      <path d="M12 3v18M5 7l14 10M19 7L5 17" />
      <path d="M12 3l-2 2M12 3l2 2M12 21l-2-2M12 21l2-2M5 7l-1.8-1M5 7l1.8-1M19 7l1.8-1M19 7l-1.8-1M5 17l-1.8 1M5 17l1.8 1M19 17l1.8 1M19 17l-1.8 1" />
    </svg>
  );
}

function Fire({ className }: IconProps) {
  return (
    <svg {...base(className)} aria-hidden="true">
      <path d="M12 3c1.5 3 4 4.5 4 8a4 4 0 0 1-8 0c0-1.2.4-2 1-3 .2 1 .8 1.6 1.5 1.8C9.5 6.8 11 4.5 12 3z" />
      <path d="M12 21a4 4 0 0 0 4-4c0-2-1.5-3-2.5-4.5C12.8 13 12.5 14 12 14c-.8 0-1.3-1-1.6-1.8C9 13.5 8 14.7 8 17a4 4 0 0 0 4 4z" />
    </svg>
  );
}

function Wind({ className }: IconProps) {
  return (
    <svg {...base(className)} aria-hidden="true">
      <path d="M3 8h11a2.5 2.5 0 1 0-2.5-2.5" />
      <path d="M3 12h15a2.5 2.5 0 1 1-2.5 2.5" />
      <path d="M3 16h9a2 2 0 1 1-2 2" />
    </svg>
  );
}

function Typhoon({ className }: IconProps) {
  return (
    <svg {...base(className)} aria-hidden="true">
      <path d="M12 12c3-3 8-2 8 2a3.5 3.5 0 0 1-6 2.4" />
      <path d="M12 12c-3 3-8 2-8-2a3.5 3.5 0 0 1 6-2.4" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none" />
    </svg>
  );
}

function Tsunami({ className }: IconProps) {
  return (
    <svg {...base(className)} aria-hidden="true">
      <path d="M3 8c1.5 0 1.5 1.5 3 1.5S9 8 10.5 8 12 9.5 13.5 9.5 15 8 16.5 8 18 9.5 19.5 9.5" />
      <path d="M3 13c1.5 0 1.5 1.5 3 1.5S9 13 10.5 13 12 14.5 13.5 14.5 15 13 16.5 13 18 14.5 19.5 14.5" />
      <path d="M3 18c1.5 0 1.5 1.5 3 1.5S9 18 10.5 18 12 19.5 13.5 19.5 15 18 16.5 18 18 19.5 19.5 19.5" />
    </svg>
  );
}

function Landslide({ className }: IconProps) {
  return (
    <svg {...base(className)} aria-hidden="true">
      <path d="M3 20l6-11 4 7 3-4 5 8z" />
      <circle cx="8" cy="10" r="1" fill="currentColor" stroke="none" />
      <circle cx="14" cy="14" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

function Flood({ className }: IconProps) {
  return (
    <svg {...base(className)} aria-hidden="true">
      <path d="M3 7c2 0 2 2 4 2s2-2 4-2 2 2 4 2 2-2 4-2" />
      <path d="M3 12c2 0 2 2 4 2s2-2 4-2 2 2 4 2 2-2 4-2" />
      <path d="M3 17c2 0 2 2 4 2s2-2 4-2 2 2 4 2 2-2 4-2" />
    </svg>
  );
}

function WarningTriangle({ className }: IconProps) {
  return (
    <svg {...base(className)} aria-hidden="true">
      <path d="M12 3l9 16H3z" />
      <path d="M12 10v4M12 17h.01" />
    </svg>
  );
}

function AlertCircle({ className }: IconProps) {
  return (
    <svg {...base(className)} aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v4M12 16h.01" />
    </svg>
  );
}

function MapPin({ className }: IconProps) {
  return (
    <svg {...base(className)} aria-hidden="true">
      <path d="M12 21s7-6.3 7-11a7 7 0 1 0-14 0c0 4.7 7 11 7 11z" />
      <circle cx="12" cy="10" r="2.5" />
    </svg>
  );
}

function BusIcon({ className }: IconProps) {
  return (
    <svg {...base(className)} aria-hidden="true">
      <rect x="4" y="4" width="16" height="13" rx="2" />
      <path d="M4 11h16M8 17v3M16 17v3" />
      <circle cx="8" cy="14" r="1" fill="currentColor" stroke="none" />
      <circle cx="16" cy="14" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** HKO warning codes → icon glyph. Fallback handled by severity. */
const WEATHER_ICON: Record<string, (p: IconProps) => ReactNode> = {
  WTHU: Thunderstorm, // Thunderstorm Warning
  WRAIN: Rain, // Rainstorm Warning (generic)
  WRAINA: Rain, // Amber rainstorm
  WRAINR: Rain, // Red rainstorm
  WRAINW: Rain, // Black rainstorm
  WHOT: Hot, // Very Hot Weather Warning
  WCOLD: Cold, // Cold Weather Warning
  WFRO: Frost, // Frost Warning
  WFIR: Fire, // Fire Danger Warning
  WTMW: Tsunami, // Tsunami Warning
  WTS: Typhoon, // Tropical Cyclone Warning
  WFNT: Wind, // Strong Monsoon Signal
  WSWR: Wind, // Strong Wind Signal
  WNSR: Wind, // Gale / Storm Wind Signal
  WL: Landslide, // Landslip Warning
  WMSG: Flood, // Special Announcement on Flooding
};

/** Resolve the icon for a weather warning, falling back to severity. */
export function WeatherIcon({
  warning,
  className,
}: {
  warning: WeatherWarning;
  className?: string;
}): ReactNode {
  const Glyph = WEATHER_ICON[warning.code] || null;
  if (Glyph) return <Glyph className={className} />;
  if (warning.severity === 'black' || warning.severity === 'red')
    return <WarningTriangle className={className} />;
  return <AlertCircle className={className} />;
}

export {
  AlertCircle,
  BusIcon,
  Flood,
  Frost,
  Hot,
  Landslide,
  MapPin,
  Rain,
  Thunderstorm,
  Typhoon,
  Tsunami,
  WarningTriangle,
  Wind,
  Fire,
};
