import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { colors, pressOpacity, radius, spacing, touch } from '@/theme';

/**
 * Banner shown when a periodic background refresh fails but we still have the
 * last good data. Tells the user the data may be stale and offers a retry.
 */
export function SoftErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <View style={styles.banner}>
      <Text style={styles.icon}>⚠️</Text>
      <Text style={styles.text} numberOfLines={2}>
        {message} — showing last data.
      </Text>
      <TouchableOpacity
        accessibilityRole="button"
        accessibilityLabel="Retry"
        onPress={onRetry}
        activeOpacity={pressOpacity}
        hitSlop={6}
        style={styles.retry}
      >
        <Text style={styles.retryText}>Retry</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#FFF6E5',
    borderBottomWidth: 1,
    borderBottomColor: colors.warning,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  icon: { fontSize: 14 },
  text: {
    flex: 1,
    fontSize: 12,
    color: colors.text,
  },
  retry: {
    // Expand the tappable area to the 44px guideline.
    minHeight: touch,
    paddingHorizontal: 12,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.warning,
  },
  retryText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.warning,
  },
});
