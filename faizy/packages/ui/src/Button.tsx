"use client";

import * as React from "react";

/**
 * Button.
 *
 * The primary variant is orange background / black text. That is the logo
 * pairing, and it is also the only high-contrast way to use brand orange:
 * orange-on-white is ~2.2:1 and fails WCAG for text, while black-on-orange is
 * ~9:1. See the contrast note in packages/brand/src/tokens.ts before adding an
 * orange-text variant.
 *
 * Minimum touch target is 44px on the md/lg sizes — these apps are used on
 * phones, often one-handed, sometimes by workers wearing gloves.
 */

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-orange-500 text-ink-950 hover:bg-orange-400 active:bg-orange-600 shadow-sm font-semibold",
  secondary:
    "bg-white text-content ring-1 ring-inset ring-ink-200 hover:bg-cream-100 active:bg-cream-200 font-medium",
  ghost: "bg-transparent text-content-muted hover:bg-cream-100 hover:text-content font-medium",
  danger: "bg-danger-600 text-white hover:bg-danger-500 active:bg-danger-700 font-semibold",
};

const SIZES: Record<ButtonSize, string> = {
  sm: "h-9 px-3 text-sm rounded-md gap-1.5",
  md: "h-11 px-4 text-base rounded-lg gap-2",
  lg: "h-12 px-6 text-base rounded-lg gap-2",
};

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  fullWidth?: boolean;
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading = false, fullWidth = false, disabled, className, children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      // `loading` must also disable — otherwise a slow network invites the
      // double-submit that creates two orders and two charges.
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={[
        "inline-flex items-center justify-center font-sans transition-colors select-none",
        "focus:outline-none focus-visible:shadow-focus",
        "disabled:opacity-50 disabled:pointer-events-none",
        VARIANTS[variant],
        SIZES[size],
        fullWidth ? "w-full" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    >
      {loading && (
        <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" aria-hidden fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4z"
          />
        </svg>
      )}
      {children}
    </button>
  );
});
