/**
 * Money helpers.
 *
 * Two representations exist in this system and mixing them up is the classic
 * billing bug:
 *   * MINOR UNITS (integer fils/halalas) — plans, subscriptions, the activity
 *     ledger, wallet, and everything that talks to a payment gateway.
 *   * DECIMAL (numeric(12,2)) — order amounts, because they are summed and
 *     reported on, and Postgres numeric is exact.
 *
 * Anything crossing into a gateway must be minor units. Never use JS floats for
 * either: 0.1 + 0.2 !== 0.3, and that becomes a customer complaint.
 */

export const CURRENCY_MINOR_DIGITS: Record<string, number> = {
  AED: 2,
  SAR: 2,
  PKR: 2,
  USD: 2,
};

export function toMinor(amount: number, currency = "AED"): number {
  const digits = CURRENCY_MINOR_DIGITS[currency] ?? 2;
  // Round rather than truncate — truncating systematically undercharges.
  return Math.round(amount * 10 ** digits);
}

export function fromMinor(minor: number, currency = "AED"): number {
  const digits = CURRENCY_MINOR_DIGITS[currency] ?? 2;
  return minor / 10 ** digits;
}

/**
 * Format for display. Locale defaults to en-AE, which renders "AED 26.50".
 * Pass `ur` for Urdu-language users; the numerals stay Latin, which is what
 * Pakistani users overwhelmingly expect for prices.
 */
export function formatMoney(
  minor: number,
  currency = "AED",
  locale: "en" | "ur" = "en",
): string {
  const value = fromMinor(minor, currency);
  return new Intl.NumberFormat(locale === "ur" ? "ur-PK-u-nu-latn" : "en-AE", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(value);
}

/** The two revenue rates from the business model. Kept here so they are stated once. */
export const PLATFORM_FEE_RATE = 0.05;   // added to the customer invoice
export const VENDOR_COMMISSION_RATE = 0.1; // retained from the vendor

/**
 * Mirror of the database's `recompute_order_totals()` trigger, for previewing a
 * price in the booking UI before the order exists.
 *
 * The DATABASE is authoritative — this is a display convenience only. If the two
 * ever disagree, the database is right and this function is the bug. Rounding is
 * half-up per component to match the SQL exactly.
 */
export function previewOrderTotals(input: {
  purchaseValue: number;
  serviceFee?: number;
  hasVendor?: boolean;
}): {
  purchaseValue: number;
  platformFee: number;
  serviceFee: number;
  vendorCommission: number;
  total: number;
} {
  const round2 = (n: number) => Math.round((n + Number.EPSILON) * 100) / 100;
  const purchaseValue = round2(input.purchaseValue);
  const serviceFee = round2(input.serviceFee ?? 0);
  const platformFee = round2(purchaseValue * PLATFORM_FEE_RATE);
  const vendorCommission = input.hasVendor ? round2(purchaseValue * VENDOR_COMMISSION_RATE) : 0;

  return {
    purchaseValue,
    platformFee,
    serviceFee,
    vendorCommission,
    // Vendor commission is retained from the vendor, not charged to the customer.
    total: round2(purchaseValue + platformFee + serviceFee),
  };
}
