import * as React from "react";
import { statusColors, type OrderStatusToken } from "@faizy/brand/tokens";

/**
 * Order status badge. The five states match the admin Kanban columns exactly
 * (Pending → Assigned → In Progress → Completed → Cancelled) and the
 * `order_status` enum in the database, so the three surfaces cannot drift.
 *
 * The dot is not decorative: colour alone is not an accessible status signal,
 * so the label always ships with it.
 */

const LABELS: Record<OrderStatusToken, string> = {
  pending: "Pending",
  assigned: "Assigned",
  in_progress: "In Progress",
  completed: "Completed",
  cancelled: "Cancelled",
};

export type StatusBadgeProps = {
  status: OrderStatusToken;
  size?: "sm" | "md";
  /** Pulse the dot for live/in-flight states. */
  pulse?: boolean;
  className?: string;
};

export function StatusBadge({ status, size = "md", pulse = false, className }: StatusBadgeProps) {
  const token = statusColors[status];
  const label = LABELS[status];

  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded-full font-medium whitespace-nowrap",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ backgroundColor: token.bg, color: token.fg }}
    >
      <span className="relative flex h-1.5 w-1.5">
        {pulse && (
          <span
            className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-75"
            style={{ backgroundColor: token.dot }}
          />
        )}
        <span
          className="relative inline-flex h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: token.dot }}
        />
      </span>
      {label}
    </span>
  );
}
