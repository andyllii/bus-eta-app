/**
 * Design tokens for the mobile-first Bus ETA app.
 *
 * Centralised so every screen/component shares one source of truth for color,
 * spacing, and corner radius. Imports go through the `@/theme` alias
 * (configured in tsconfig.json `paths` and babel.config.js `module-resolver`).
 *
 * The palette is tuned for a light, high-contrast mobile UI: a calm slate
 * background, a single brand `primary`, and semantic colors for live/scheduled
 * ETA status, warnings, and danger states.
 */

export const colors = {
  /** App background — near-white slate so cards/surfaces pop. */
  background: '#F5F6F8',
  /** Raised surface behind cards, chips, and inputs. */
  surface: '#FFFFFF',
  /** Default body text. */
  text: '#1A1D21',
  /** Secondary / muted text (labels, hints, timestamps). */
  textSecondary: '#6B7280',
  /** Brand accent — used for primary buttons, active chips, links. */
  primary: '#2563EB',
  /** Hairline borders and dividers. */
  border: '#E2E5EA',
  /** Card background (subtle lift off the surface). */
  card: '#FFFFFF',
  /** Destructive / error text and accents. */
  danger: '#DC2626',
  /** Star / favorite accent. */
  star: '#F5A623',
  /** Warning (e.g. weather / traffic) accent. */
  warning: '#D97706',

  /** "Bus is arriving now" status. */
  liveBg: '#DCFCE7',
  liveText: '#166534',
  /** "Scheduled / upcoming" status. */
  scheduledBg: '#E0E7FF',
  scheduledText: '#3730A3',
} as const;

/** Spacing scale (px). Mobile-first: generous touch targets. */
export const spacing = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
} as const;

/** Corner radius scale. */
export const radius = {
  /** Small controls (inputs, cards). */
  md: 10,
  /** Large controls (primary buttons, big cards). */
  lg: 16,
  /** Fully rounded chips/pills. */
  pill: 999,
} as const;

/**
 * Minimum touch-target size (pt) per Apple HIG / WCAG 2.5.5 (target size 44×44
 * and 24×24 respectively). Every tappable control should be at least this
 * large — we apply it via an invisible hit-area padding so the *visual* control
 * can stay compact while the *touch* area meets the guideline.
 */
export const touch = 44;

/** Shared pressed-state opacity for TouchableOpacity controls. */
export const pressOpacity = 0.6;

export const theme = { colors, spacing, radius, touch, pressOpacity };
export default theme;
