import React from 'react';
import {
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { colors, pressOpacity, radius, spacing, touch } from '@/theme';

/** Pill-shaped search bar from the Search screen mockup. */
export function SearchBar({
  value,
  onChangeText,
  placeholder = 'Search for routes or stops…',
  onSubmit,
}: {
  value: string;
  onChangeText: (t: string) => void;
  placeholder?: string;
  onSubmit?: () => void;
}) {
  return (
    <View style={styles.bar}>
      <TextInput
        style={styles.input}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.textSecondary}
        returnKeyType="search"
        onSubmitEditing={onSubmit}
      />
      <TouchableOpacity
        accessibilityRole="button"
        accessibilityLabel="Search"
        onPress={onSubmit}
        activeOpacity={pressOpacity}
        hitSlop={8}
        style={styles.icon}
      >
        <Text style={styles.iconText}>🔍</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    height: 48,
    // Hairline border so the field reads as a tappable control on white bg.
    borderWidth: 1,
    borderColor: colors.border,
  },
  input: {
    flex: 1,
    fontSize: 16,
    color: colors.text,
    paddingVertical: 0,
    // Match the touch-target height so the whole row is tappable text.
    minHeight: touch,
  },
  icon: {
    // Expand the tappable area to the 44px guideline (visual icon is ~26px).
    minWidth: touch,
    height: touch,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconText: { fontSize: 18 },
});
