import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors } from '@/theme';
import type { Weather, WeatherWarning } from '@/services/types';
import { resolveText } from '@/services/i18n';
import type { Lang } from '@/services/types';

/**
 * Compact weather widget for the results header:
 *   [☀] 28°C   ⛈ 1
 * Maps HKO icon codes to a simple glyph. Full icon set lives in DESIGN.md.
 * Shows an active-warning indicator when any warning is in force, and renders
 * an icon per warning so a thunderstorm warning reads as ⛈.
 */
const ICON_GLYPH: Record<number, string> = {
  60: '☀️', // Sunny
  61: '⛅', // Sunny periods
  62: '☁️', // Cloudy
  63: '🌥️', // Sunny intervals
  64: '🌧️', // Rain
  65: '⛈️', // Thunderstorms
};

/** Severity -> accent colour for the warning chip. */
const SEVERITY_COLOR: Record<string, string> = {
  black: colors.danger,
  red: colors.danger,
  amber: colors.warning,
  warning: colors.warning,
  none: colors.textSecondary,
};

/**
 * HKO weather-warning codes -> a specific glyph so each warning reads at a
 * glance (the task calls out the thunderstorm icon as a visual indicator).
 * Codes are like `WRAINA` (Amber Rainstorm), `WTS` (Thunderstorm), etc., so we
 * match on the stable prefix rather than the trailing severity letter.
 */
const WARNING_GLYPH: Record<string, string> = {
  WTS: '⛈️', // Thunderstorm Warning
  WRAIN: '🌧️', // Rainstorm Warning (Amber/Red/Black)
  WFIRE: '🔥', // Fire Danger Warning
  WCOLD: '❄️', // Cold Weather Warning
  WHOT: '☀️', // Hot Weather Warning
  WSTR: '💨', // Strong Monsoon Signal
  WFROST: '🌨️', // Frost Warning
  WFMO: '🌫️', // Fog Warning
  WL: '⛰️', // Landslip Warning
  WTMW: '🌊', // Tsunami Warning
};

/** Pick a warning glyph from its code (falls back to the generic warning). */
function warningGlyph(code: string | undefined): string {
  const key = (code ?? '').toUpperCase();
  for (const prefix of Object.keys(WARNING_GLYPH)) {
    if (key.startsWith(prefix)) return WARNING_GLYPH[prefix];
  }
  return '⚠️';
}

export function WeatherWidget({
  weather,
}: {
  weather?: Weather | null;
}) {
  const temp = weather?.temperature?.value;
  const unit = weather?.temperature?.unit ?? 'C';
  const glyph = ICON_GLYPH[weather?.icon?.[0] ?? 60] ?? '☀️';
  const warnings: WeatherWarning[] = weather?.warnings ?? [];
  const desc = weather?.description;

  return (
    <View style={styles.row}>
      <Text style={styles.glyph}>{glyph}</Text>
      <Text style={styles.value}>{temp != null ? `${temp}°${unit}` : '—'}</Text>
      {warnings.length > 0 ? (
        <View
          style={[
            styles.warn,
            { borderColor: SEVERITY_COLOR[warnings[0].severity] ?? colors.warning },
          ]}
        >
          <Text
            style={[
              styles.warnText,
              { color: SEVERITY_COLOR[warnings[0].severity] ?? colors.warning },
            ]}
          >
            {warnings.length > 1
              ? `${warningGlyph(warnings[0].code)}${warnings.length}`
              : `${warningGlyph(warnings[0].code)}`}
          </Text>
        </View>
      ) : null}
      {desc ? (
        <Text style={styles.desc} numberOfLines={1}>
          {desc}
        </Text>
      ) : null}
    </View>
  );
}

/** Full-width weather + warnings strip for the top of the results view. */
export function WeatherStrip({
  weather,
  lang,
}: {
  weather?: Weather | null;
  lang: Lang;
}) {
  const warnings: WeatherWarning[] = weather?.warnings ?? [];
  if (!weather && warnings.length === 0) return null;
  const glyph = ICON_GLYPH[weather?.icon?.[0] ?? 60] ?? '☀️';
  const temp = weather?.temperature?.value;

  return (
    <View style={styles.strip}>
      <View style={styles.stripHead}>
        <Text style={styles.stripGlyph}>{glyph}</Text>
        <Text style={styles.stripTemp}>
          {temp != null ? `${temp}°${weather?.temperature?.unit ?? 'C'}` : '—'}
        </Text>
        {weather?.description ? (
          <Text style={styles.stripDesc}>{weather.description}</Text>
        ) : null}
      </View>
      {warnings.map((w) => {
        const color = SEVERITY_COLOR[w.severity] ?? colors.warning;
        return (
          <View key={w.code} style={[styles.warnChip, { borderColor: color }]}>
            <Text style={styles.warnIcon}>{warningGlyph(w.code)}</Text>
            <Text style={[styles.warnTitle, { color }]} numberOfLines={1}>
              {resolveText(w.title, lang)}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    flex: 1,
    flexShrink: 1,
    minWidth: 0,
  },
  glyph: { fontSize: 22 },
  value: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  warn: {
    backgroundColor: '#FFF6E5',
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 6,
    paddingVertical: 1,
  },
  warnText: {
    fontSize: 12,
    fontWeight: '700',
  },
  desc: {
    fontSize: 12,
    color: colors.textSecondary,
    flex: 1,
    flexShrink: 1,
    minWidth: 0,
  },
  // WeatherStrip
  strip: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 12,
    gap: 8,
  },
  stripHead: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  stripGlyph: { fontSize: 26 },
  stripTemp: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
  },
  stripDesc: {
    fontSize: 13,
    color: colors.textSecondary,
    flex: 1,
    flexWrap: 'wrap',
  },
  warnChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#FFF6E5',
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  warnIcon: { fontSize: 14 },
  warnTitle: {
    fontSize: 13,
    fontWeight: '600',
    flex: 1,
  },
});
