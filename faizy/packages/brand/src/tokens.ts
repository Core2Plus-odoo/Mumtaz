/**
 * Faizy brand tokens — the single source of truth for the visual identity.
 *
 * Confirmed from the live brand (facebook.com/faizy.pk): bold black geometric "F"
 * monogram on a solid orange circle, Poppins throughout, sporty-confident tone.
 *
 * This REPLACES the Royal Blue (#1A3FA5) / Gold (#C49A3C) / Cormorant Garamond
 * identity used in the earlier prototypes. Nothing should ship with those values.
 *
 * Accessibility note that drives several choices below: brand orange on white is
 * ~2.2:1 contrast — it FAILS as body text or as a small-text foreground on light
 * backgrounds. Black on brand orange is ~9:1 and passes comfortably. That is why
 * the primary button is orange-background/black-text (which is also the logo
 * pairing) rather than the more common coloured-text-on-white treatment.
 */

/** Brand orange. The one colour people recognise Faizy by. */
export const ORANGE = "#F69E22" as const;

/** Brand black — deliberately near-black, not pure #000. */
export const BLACK = "#0A0A0A" as const;

export const colors = {
  /** Primary brand ramp, centred on ORANGE at 500. */
  orange: {
    50: "#FEF6EA",
    100: "#FDEACC",
    200: "#FBD79F",
    300: "#F9C069",
    400: "#F7AE41",
    500: ORANGE,
    600: "#E08410",
    700: "#B9670D",
    800: "#925114",
    900: "#764314",
    950: "#422107",
  },
  /** Neutral ramp, bottoming out at brand BLACK. */
  ink: {
    50: "#F7F7F7",
    100: "#E3E3E3",
    200: "#C8C8C8",
    300: "#A4A4A4",
    400: "#818181",
    500: "#666666",
    600: "#515151",
    700: "#434343",
    800: "#383838",
    900: "#1A1A1A",
    950: BLACK,
  },
  /** Warm white / cream — page backgrounds and body copy on dark surfaces. */
  cream: {
    50: "#FDFBF7",
    100: "#FAF6EF",
    200: "#F4EDE0",
    300: "#EADFCB",
  },
  /** Semantic colours. Chosen to sit beside orange without competing with it. */
  success: {
    50: "#ECFDF3",
    100: "#D1FADF",
    500: "#12B76A",
    600: "#039855",
    700: "#027A48",
  },
  warning: {
    50: "#FFFAEB",
    100: "#FEF0C7",
    500: "#F79009",
    600: "#DC6803",
    700: "#B54708",
  },
  danger: {
    50: "#FEF3F2",
    100: "#FEE4E2",
    500: "#F04438",
    600: "#D92D20",
    700: "#B42318",
  },
  info: {
    50: "#EFF8FF",
    100: "#D1E9FF",
    500: "#2E90FA",
    600: "#1570EF",
    700: "#175CD3",
  },
} as const;

/**
 * Order lifecycle → colour. Mirrors the admin Kanban columns
 * (Pending → Assigned → In Progress → Completed → Cancelled).
 */
export const statusColors = {
  pending: { bg: colors.ink[100], fg: colors.ink[700], dot: colors.ink[400] },
  assigned: { bg: colors.info[50], fg: colors.info[700], dot: colors.info[500] },
  in_progress: { bg: colors.orange[100], fg: colors.orange[800], dot: colors.orange[500] },
  completed: { bg: colors.success[50], fg: colors.success[700], dot: colors.success[500] },
  cancelled: { bg: colors.danger[50], fg: colors.danger[700], dot: colors.danger[500] },
} as const;

export type OrderStatusToken = keyof typeof statusColors;

/**
 * Typography. Poppins replaces Cormorant Garamond / Instrument Sans everywhere.
 * Noto Nastaliq Urdu is loaded ONLY for Urdu content — it is a display face for
 * Nastaliq script and must never be used for Latin text.
 */
export const fonts = {
  sans: "var(--font-poppins), ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif",
  urdu: "var(--font-noto-nastaliq), 'Noto Nastaliq Urdu', serif",
  mono: "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, monospace",
} as const;

/** Poppins weights actually used. Bold headlines, medium labels, regular body. */
export const fontWeights = {
  regular: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
} as const;

/**
 * Type scale — mobile-first. Headlines are tight and bold to match the
 * sporty-confident tone; body stays comfortable at small sizes on phones.
 *
 * Deliberately NOT `as const`: Tailwind's config type requires mutable tuples,
 * and a readonly tuple fails to satisfy it.
 */
type FontSizeToken = [size: string, config: { lineHeight: string; letterSpacing?: string }];

export const fontSizes: Record<string, FontSizeToken> = {
  xs: ["0.75rem", { lineHeight: "1rem" }],
  sm: ["0.875rem", { lineHeight: "1.25rem" }],
  base: ["1rem", { lineHeight: "1.5rem" }],
  lg: ["1.125rem", { lineHeight: "1.75rem" }],
  xl: ["1.25rem", { lineHeight: "1.75rem", letterSpacing: "-0.01em" }],
  "2xl": ["1.5rem", { lineHeight: "2rem", letterSpacing: "-0.02em" }],
  "3xl": ["1.875rem", { lineHeight: "2.25rem", letterSpacing: "-0.02em" }],
  "4xl": ["2.25rem", { lineHeight: "2.5rem", letterSpacing: "-0.03em" }],
  "5xl": ["3rem", { lineHeight: "1.1", letterSpacing: "-0.03em" }],
} as const;

export const radii = {
  none: "0",
  sm: "0.25rem",
  DEFAULT: "0.5rem",
  md: "0.625rem",
  lg: "0.875rem",
  xl: "1.125rem",
  "2xl": "1.5rem",
  full: "9999px",
} as const;

/** Warm-tinted shadows — neutral grey shadows read cold against cream. */
export const shadows = {
  xs: "0 1px 2px 0 rgb(10 10 10 / 0.05)",
  sm: "0 1px 3px 0 rgb(10 10 10 / 0.10), 0 1px 2px -1px rgb(10 10 10 / 0.10)",
  DEFAULT: "0 4px 8px -2px rgb(10 10 10 / 0.10), 0 2px 4px -2px rgb(10 10 10 / 0.06)",
  lg: "0 12px 16px -4px rgb(10 10 10 / 0.08), 0 4px 6px -2px rgb(10 10 10 / 0.03)",
  xl: "0 20px 24px -4px rgb(10 10 10 / 0.08), 0 8px 8px -4px rgb(10 10 10 / 0.03)",
  /** Focus ring — orange at low alpha, used with an offset. */
  focus: "0 0 0 4px rgb(246 158 34 / 0.35)",
} as const;

/** The Urdu tagline. ح (bari he), not ہ — the spelling correction is load-bearing. */
export const TAGLINE_UR = "حاضر ہیں۔" as const;
export const TAGLINE_EN = "We're here." as const;

export const brand = {
  name: "Faizy",
  legalEntity: "C2P Consultants FZC LLC",
  taglineUr: TAGLINE_UR,
  taglineEn: TAGLINE_EN,
  colors,
  statusColors,
  fonts,
  fontWeights,
  fontSizes,
  radii,
  shadows,
} as const;
