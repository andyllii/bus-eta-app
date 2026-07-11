import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { colors, pressOpacity, radius, touch } from '@/theme';
import type { Lang } from '@/services/types';
import { useLanguage } from '@/services/i18n';

const LANGS: { code: Lang; label: string }[] = [
  { code: 'en', label: 'EN' },
  { code: 'tc', label: '繁' },
  { code: 'sc', label: '简' },
];

/**
 * Compact language switcher (EN / 繁 / 简). Drives the global language used to
 * resolve multilingual text from the API. Lives in the header of each screen.
 */
export function LangToggle() {
  const { lang, setLang } = useLanguage();
  return (
    <View style={styles.group}>
      {LANGS.map((l) => {
        const active = l.code === lang;
        return (
          <TouchableOpacity
            key={l.code}
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
            accessibilityLabel={`Language ${l.label}`}
            onPress={() => setLang(l.code)}
            activeOpacity={pressOpacity}
            hitSlop={4}
            style={[styles.chip, active ? styles.chipActive : null]}
          >
            <Text style={[styles.chipText, active ? styles.chipTextActive : null]}>
              {l.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  group: {
    flexDirection: 'row',
    gap: 2,
    backgroundColor: colors.background,
    borderRadius: radius.pill,
    padding: 3,
    flexShrink: 0,
  },
  chip: {
    minWidth: touch,
    minHeight: touch,
    paddingHorizontal: 4,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.pill,
  },
  chipActive: {
    backgroundColor: colors.surface,
    // Lift the active chip off the group with a soft shadow.
    shadowColor: colors.text,
    shadowOpacity: 0.08,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 1 },
    elevation: 1,
  },
  chipText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  chipTextActive: {
    color: colors.text,
  },
});
