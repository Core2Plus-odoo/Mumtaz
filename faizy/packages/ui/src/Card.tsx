import * as React from "react";

/**
 * Card — the workhorse container across all three apps.
 *
 * Server-component safe (no hooks, no handlers). For a clickable card, use
 * `InteractiveCard`, which lives in its own "use client" module so this one
 * stays out of the client bundle.
 */

export type CardProps = {
  children: React.ReactNode;
  /** `raised` sits on the cream page background; `flat` sits inside another card. */
  tone?: "raised" | "flat" | "brand" | "inverse";
  padding?: "none" | "sm" | "md" | "lg";
  className?: string;
};

/** Exported so InteractiveCard can reuse them without duplicating the scale. */
export const CARD_TONES: Record<NonNullable<CardProps["tone"]>, string> = {
  raised: "bg-white ring-1 ring-ink-100 shadow-sm",
  flat: "bg-cream-100",
  brand: "bg-orange-500 text-ink-950",
  inverse: "bg-ink-950 text-cream-50",
};

export const CARD_PADDINGS: Record<NonNullable<CardProps["padding"]>, string> = {
  none: "",
  sm: "p-3",
  md: "p-4",
  lg: "p-6",
};

export function Card({ children, tone = "raised", padding = "md", className }: CardProps) {
  return (
    <div
      className={["rounded-xl", CARD_TONES[tone], CARD_PADDINGS[padding], className]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-3 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <h3 className="truncate font-sans text-base font-semibold text-content">{title}</h3>
        {subtitle && <p className="mt-0.5 text-sm text-content-muted">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
