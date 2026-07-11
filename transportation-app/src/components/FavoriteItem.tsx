import React from 'react';
import { StyleSheet, Text, TouchableOpacity } from 'react-native';
import { colors, spacing } from '@/theme';
import type { SearchHit } from '@/services/types';
import { resolveText, useLanguage } from '@/services/i18n';

/** A suggestions list row for a single SearchHit. */
export function FavoriteItem({
  item,
  onPress,
}: {
  item: SearchHit;
  onPress: () => void;
}) {
  const { lang } = useLanguage();
  const title = resolveText(item.name, lang) || item.id;
  const sub = item.kind === 'route' ? item.operator : item.operator;
  return (
    <TouchableOpacity
      accessibilityRole="button"
      onPress={onPress}
      style={styles.row}
    >
      <Text style={styles.label}>{title}</Text>
      {sub ? <Text style={styles.sub}>{sub}</Text> : null}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  label: {
    fontSize: 16,
    fontWeight: '500',
    color: colors.text,
  },
  sub: {
    fontSize: 13,
    color: colors.textSecondary,
  },
});
