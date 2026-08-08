import type { Config } from "tailwindcss";
import { colors, fonts, fontSizes, radii, shadows } from "./tokens";

/**
 * Shared Tailwind preset. Every app extends this so the three surfaces
 * (customer, admin, worker) cannot drift apart visually.
 *
 * Usage in an app's tailwind.config.ts:
 *   import { faizyPreset } from "@faizy/brand/tailwind";
 *   export default { presets: [faizyPreset], content: [...] };
 */
export const faizyPreset = {
  content: [],
  theme: {
    extend: {
      colors: {
        orange: colors.orange,
        ink: colors.ink,
        cream: colors.cream,
        success: colors.success,
        warning: colors.warning,
        danger: colors.danger,
        info: colors.info,
        // Semantic aliases — prefer these in app code so a token change
        // propagates without a find-and-replace across three apps.
        brand: colors.orange,
        surface: {
          DEFAULT: colors.cream[50],
          raised: "#FFFFFF",
          sunken: colors.cream[100],
          inverse: colors.ink[950],
        },
        content: {
          DEFAULT: colors.ink[950],
          muted: colors.ink[600],
          subtle: colors.ink[400],
          inverse: colors.cream[50],
          // Text ON brand orange. Black, not white — see the contrast note in tokens.ts.
          onBrand: colors.ink[950],
        },
        border: {
          DEFAULT: colors.ink[100],
          strong: colors.ink[200],
          brand: colors.orange[500],
        },
      },
      fontFamily: {
        sans: [fonts.sans],
        urdu: [fonts.urdu],
        mono: [fonts.mono],
      },
      fontSize: fontSizes,
      borderRadius: radii,
      boxShadow: shadows,
      // Safe-area padding — the customer and worker apps are installed PWAs
      // running full-bleed on phones with notches and home indicators.
      spacing: {
        "safe-top": "env(safe-area-inset-top)",
        "safe-bottom": "env(safe-area-inset-bottom)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "ring-fill": {
          from: { strokeDashoffset: "var(--ring-circumference)" },
          to: { strokeDashoffset: "var(--ring-offset-target)" },
        },
      },
      animation: {
        "fade-in": "fade-in 200ms ease-out",
        "ring-fill": "ring-fill 900ms cubic-bezier(0.22, 1, 0.36, 1) forwards",
      },
    },
  },
  plugins: [],
} satisfies Config;

export default faizyPreset;
