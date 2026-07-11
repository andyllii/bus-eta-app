import React from 'react';
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { colors } from '@/theme';

export function ScreenHeader({
  title,
  subtitle,
  titleNumberOfLines = 1,
}: {
  title: string;
  subtitle?: string;
  /** Max lines for the title before ellipsis (1 = single line, 0/omit = wrap). */
  titleNumberOfLines?: number;
}) {
  return (
    <View style={styles.header}>
      <Text style={styles.title} numberOfLines={titleNumberOfLines}>
        {title}
      </Text>
      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
    </View>
  );
}

/** Format a date as a local "HH:MM" clock (for the "updated at" line). */
export function formatClock(d: Date | null): string {
  if (!d) return '';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <View style={styles.center}>
      <ActivityIndicator color={colors.primary} />
      <Text style={styles.muted}>{label}</Text>
    </View>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <View style={styles.center}>
      <Text style={styles.error}>⚠️ {message}</Text>
    </View>
  );
}

export function EmptyState({ label }: { label: string }) {
  return (
    <View style={styles.center}>
      <Text style={styles.muted}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 12,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
  },
  subtitle: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    gap: 12,
  },
  muted: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  error: {
    fontSize: 14,
    color: colors.danger,
    textAlign: 'center',
  },
});
