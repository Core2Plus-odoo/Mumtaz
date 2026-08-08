"use client";

import * as React from "react";
import { CARD_PADDINGS, CARD_TONES, type CardProps } from "./Card";

/**
 * Clickable card. Split from Card.tsx so the plain `Card` stays a server
 * component — this one carries "use client" because it takes an onClick.
 *
 * Renders a real <button> rather than a div with a click handler, so keyboard
 * and screen-reader users get the affordance for free.
 */
export function InteractiveCard({
  children,
  tone = "raised",
  padding = "md",
  className,
  ...rest
}: CardProps & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "className" | "children">) {
  return (
    <button
      type="button"
      className={[
        "w-full rounded-xl text-left transition-shadow",
        "focus:outline-none focus-visible:shadow-focus hover:shadow-DEFAULT",
        CARD_TONES[tone],
        CARD_PADDINGS[padding],
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    >
      {children}
    </button>
  );
}
