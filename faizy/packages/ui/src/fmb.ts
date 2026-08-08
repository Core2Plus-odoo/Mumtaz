/**
 * FMB ID formatting. Kept in its own module with no "use client" directive so
 * server components and route handlers can format IDs without pulling the
 * interactive chip component into the client bundle.
 *
 * IDs are allocated server-side from a Postgres sequence (see the
 * `family_members` migration) — never generated on the client, where two devices
 * offline at once would happily mint the same number.
 */

const FMB_PATTERN = /^FMB-\d{6,}$/;

export function formatFmbId(id: string | number): string {
  if (typeof id === "number") return `FMB-${String(id).padStart(6, "0")}`;
  const trimmed = id.trim().toUpperCase();
  if (FMB_PATTERN.test(trimmed)) return trimmed;
  // Tolerate a bare numeric string coming back from an untyped source.
  const digits = trimmed.replace(/\D/g, "");
  return digits ? `FMB-${digits.padStart(6, "0")}` : trimmed;
}
