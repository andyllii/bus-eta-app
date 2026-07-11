/**
 * Design tokens for the Bus ETA app.
 * Mirrors the minimalist, high-contrast black-on-white aesthetic seen in the
 * approved UI/UX wireframes (Search, ETA View, Contextual Info).
 */

export const colors = {
  // Surfaces
  background: '#FFFFFF',
  surface: '#F7F7F8',
  card: '#FFFFFF',
  border: '#E5E5EA',

  // Text
  text: '#1C1C1E',
  textSecondary: '#8E8E93',

  // Brand / accent
  primary: '#007AFF',
  star: '#FFB400',
  success: '#34C759',
  warning: '#FF9500',
  danger: '#FF3B30',

  // Status pills
  liveBg: '#E6F7EC',
  liveText: '#1E8E3E',
  scheduledBg: '#EFEFF4',
  scheduledText: '#8E8E93',
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  pill: 999,
} as const;

export const typography = {
  title: 28,
  heading: 20,
  body: 16,
  subhead: 14,
  caption: 12,
} as const;

export const theme = {
  colors,
  spacing,
  radius,
  typography,
} as const;

export type Theme = typeof theme;
