import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { colors, pressOpacity, radius, spacing, touch } from '@/theme';
import type { Incident, Lang } from '@/services/types';
import { resolveText } from '@/services/i18n';

/**
 * Dismissible traffic alert banner shown at the top of the results screen.
 * Mirrors the wireframe's warning-triangle + close (X). Colours by the server
 * computed relevance so high-impact incidents affecting the route stand out,
 * and shows a one-line detail when available.
 */
const RELEVANCE_BG: Record<string, string> = {
  high: '#FFE9E9',
  medium: '#FFF6E5',
  low: '#F2F2F7',
  none: '#F2F2F7',
};
const RELEVANCE_BORDER: Record<string, string> = {
  high: colors.danger,
  medium: colors.warning,
  low: colors.border,
  none: colors.border,
};

export function TrafficAlertBanner({
  incident,
  lang,
  onDismiss,
}: {
  incident: Incident;
  lang: Lang;
  onDismiss: () => void;
}) {
  const heading = resolveText(incident.heading, lang);
  const location = resolveText(incident.location, lang);
  const detail = resolveText(incident.detail, lang);
  const relevance = incident.relevance ?? 'none';

  return (
    <View
      style={[
        styles.banner,
        { backgroundColor: RELEVANCE_BG[relevance], borderColor: RELEVANCE_BORDER[relevance] },
      ]}
    >
      <Text style={styles.icon}>⚠️</Text>
      <View style={styles.body}>
        <View style={styles.headRow}>
          <Text style={styles.heading}>{heading}</Text>
          {relevance === 'high' ? (
            <View style={styles.tagHigh}>
              <Text style={styles.tagText}>Affects route</Text>
            </View>
          ) : null}
        </View>
        {location ? <Text style={styles.location}>{location}</Text> : null}
        {detail ? (
          <Text style={styles.detail} numberOfLines={2}>
            {detail}
          </Text>
        ) : null}
      </View>
      <TouchableOpacity
        accessibilityRole="button"
        accessibilityLabel="Dismiss alert"
        onPress={onDismiss}
        activeOpacity={pressOpacity}
        hitSlop={8}
        style={styles.close}
      >
        <Text style={styles.closeText}>✕</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  icon: { fontSize: 18, marginTop: 1 },
  body: { flex: 1 },
  headRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  heading: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
    flex: 1,
  },
  tagHigh: {
    backgroundColor: colors.danger,
    borderRadius: radius.pill,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  tagText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#fff',
  },
  location: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  detail: {
    fontSize: 12,
    color: colors.text,
    marginTop: 4,
  },
  close: {
    // Visual icon is small; expand the touch area to the 44px guideline.
    minWidth: touch,
    height: touch,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: -spacing.sm,
    marginTop: -spacing.sm,
  },
  closeText: {
    fontSize: 18,
    color: colors.textSecondary,
  },
});
