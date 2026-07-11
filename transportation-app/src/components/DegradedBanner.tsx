import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, spacing } from '@/theme';

/**
 * Banner shown when the backend assembled the board with a partial payload
 * (one of the secondary providers — weather or incidents — failed and was
 * skipped). Informational only; the rest of the data is still valid.
 */
export function DegradedBanner() {
  return (
    <View style={styles.banner}>
      <Text style={styles.icon}>ℹ️</Text>
      <Text style={styles.text} numberOfLines={2}>
        Some data (weather or traffic) is temporarily unavailable.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  icon: { fontSize: 14 },
  text: {
    flex: 1,
    fontSize: 12,
    color: colors.text,
  },
});
