"use client";

import * as React from "react";
import { formatFmbId } from "./fmb";

/**
 * The FMB ID chip — e.g. FMB-000001.
 *
 * Every family member gets a permanent Faizy Member Beneficiary ID. It is a core
 * part of the product's identity and appears in the customer app, the admin CRM,
 * and the worker app, so it gets one component rather than three formatters.
 *
 * Client component because `copyable` needs state. If you only need the string,
 * import `formatFmbId` from "./fmb" instead — that stays server-safe.
 */

export type FmbIdChipProps = {
  /** Either the full `FMB-000001` string or the raw sequence number. */
  id: string | number;
  size?: "sm" | "md";
  /** Show a copy-to-clipboard affordance. Useful in admin, noise in the app. */
  copyable?: boolean;
  className?: string;
};

export function FmbIdChip({ id, size = "md", copyable = false, className }: FmbIdChipProps) {
  const label = formatFmbId(id);
  const [copied, setCopied] = React.useState(false);

  const copy = React.useCallback(async () => {
    try {
      await navigator.clipboard.writeText(label);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard can be unavailable (insecure context, denied permission).
      // The ID is visible either way, so failing quietly is the right call.
    }
  }, [label]);

  const base = [
    "inline-flex items-center gap-1.5 rounded-full font-mono font-medium",
    "bg-orange-100 text-orange-800 ring-1 ring-inset ring-orange-200",
    size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  if (!copyable) return <span className={base}>{label}</span>;

  return (
    <button
      type="button"
      onClick={copy}
      className={`${base} transition-colors hover:bg-orange-200 focus:outline-none focus-visible:shadow-focus`}
      title={copied ? "Copied" : `Copy ${label}`}
    >
      {label}
      <span aria-hidden className="opacity-60">
        {copied ? "✓" : "⧉"}
      </span>
      <span className="sr-only">{copied ? "Copied to clipboard" : "Copy ID"}</span>
    </button>
  );
}
