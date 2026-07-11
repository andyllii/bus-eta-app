import React from 'react';
import { StyleSheet, Text, TouchableOpacity } from 'react-native';
import { colors, pressOpacity, radius, touch } from '@/theme';

/**
 * Circular back button for the Results screen so users can return to Search.
 * Replaces the missing hardware/OS back affordance on the web SPA build and
 * keeps navigation intuitive on small screens. Touch area meets the 44px
 * guideline via min sizing on the hit target.
 */
export function BackButton({ onPress }: { onPress: () => void }) {
  return (
    <TouchableOpacity
      accessibilityRole="button"
      accessibilityLabel="Back to search"
      onPress={onPress}
      activeOpacity={pressOpacity}
      hitSlop={6}
      style={styles.btn}
    >
      <Text style={styles.glyph}>←</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  btn: {
    // 44×44 touch target (Apple HIG / WCAG 2.5.5).
    width: touch,
    height: touch,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  glyph: {
    fontSize: 22,
    color: colors.text,
    fontWeight: '700',
    // Nudge the glyph so it reads visually centered in the circle.
    marginTop: -1,
  },
});
