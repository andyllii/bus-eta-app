import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing } from '@/theme';
import type { ETA, Lang } from '@/services/types';
import { etaLiveStatus, resolveText } from '@/services/i18n';

/**
 * A single arrival card matching the ETA View mockup:
 *   [route badge] [destination]   [status pill]
 *                                    [ETA] min
 */
export function EtaCard({ eta, lang }: { eta: ETA; lang: Lang }) {
  const dest = resolveText(eta.dest, lang);
  const remark = resolveText(eta.remark, lang);
  const isLive = etaLiveStatus(remark) === 'live';
  const mins =
    eta.minutesRemaining == null ? '—' : String(eta.minutesRemaining);

  return (
    <View style={styles.card}>
      <View style={styles.badge}>
        <Text style={styles.badgeText}>{eta.route}</Text>
      </View>

      <View style={styles.middle}>
        <Text style={styles.dest} numberOfLines={2}>
          {dest}
        </Text>
        {remark ? <Text style={styles.remark}>{remark}</Text> : null}
      </View>

      <View style={styles.right}>
        <View
          style={[
            styles.pill,
            isLive ? styles.pillLive : styles.pillScheduled,
          ]}
        >
          <Text
            style={[
              styles.pillText,
              isLive ? styles.pillTextLive : styles.pillTextScheduled,
            ]}
          >
            {isLive ? 'live' : 'sched'}
          </Text>
        </View>
        <Text style={styles.eta}>
          {mins}
          <Text style={styles.etaUnit}> min</Text>
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.md,
  },
  badge: {
    width: 56,
    height: 56,
    borderRadius: radius.pill,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
  },
  middle: {
    flex: 1,
  },
  dest: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  remark: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  right: {
    alignItems: 'flex-end',
    gap: 4,
  },
  pill: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radius.pill,
  },
  pillLive: { backgroundColor: colors.liveBg },
  pillScheduled: { backgroundColor: colors.scheduledBg },
  pillText: { fontSize: 11, fontWeight: '600' },
  pillTextLive: { color: colors.liveText },
  pillTextScheduled: { color: colors.scheduledText },
  eta: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.text,
  },
  etaUnit: {
    fontSize: 13,
    fontWeight: '500',
    color: colors.textSecondary,
  },
});
