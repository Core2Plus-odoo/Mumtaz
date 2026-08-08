import type { FaizyClient } from "./client";

/**
 * WhatsApp-number OTP auth.
 *
 * There is no email/password path anywhere in Faizy — the phone number IS the
 * account. Supabase Auth's phone provider handles the OTP lifecycle; it is
 * configured to deliver over WhatsApp rather than SMS (supabase/config.toml).
 *
 * Roles (`customer` | `worker` | `admin`) live in the JWT's app_metadata, which
 * only the service role can write. That is deliberate: if the role lived in the
 * profiles table where a user can update their own row, any customer could make
 * themselves an admin.
 */

/**
 * Normalise a user-typed number to E.164, which is what the database CHECK
 * constraints and Supabase Auth both require.
 *
 * Handles the shapes people in this market actually type:
 *   "050 123 4567"    (UAE local)     → +971501234567
 *   "0501234567"      (UAE local)     → +971501234567
 *   "00971501234567"  (intl prefix)   → +971501234567
 *   "0300 1234567"    (PK local)      → +923001234567
 *
 * `defaultCountry` decides what a leading 0 means, so pass the country the form
 * is being filled in from — UAE for customers, PK for the worker app.
 */
export function toE164(input: string, defaultCountry: "AE" | "SA" | "PK" = "AE"): string | null {
  const dialCodes = { AE: "971", SA: "966", PK: "92" } as const;
  let digits = (input ?? "").replace(/[^\d+]/g, "");

  if (digits.startsWith("00")) digits = `+${digits.slice(2)}`;
  if (digits.startsWith("+")) {
    const rest = digits.slice(1).replace(/\D/g, "");
    return /^[1-9]\d{7,14}$/.test(rest) ? `+${rest}` : null;
  }

  digits = digits.replace(/\D/g, "");
  // A leading 0 is the national trunk prefix — strip it and prepend the country.
  if (digits.startsWith("0")) digits = digits.slice(1);
  if (!digits) return null;

  const candidate = `${dialCodes[defaultCountry]}${digits}`;
  return /^[1-9]\d{7,14}$/.test(candidate) ? `+${candidate}` : null;
}

/** Format an E.164 number for display: +971 50 123 4567 */
export function formatPhone(e164: string): string {
  const m = /^\+(\d{1,3})(\d{2,3})(\d+)$/.exec(e164);
  if (!m) return e164;
  const [, cc, area, rest] = m;
  return `+${cc} ${area} ${rest}`;
}

export type OtpChannel = "whatsapp" | "sms";

/**
 * Send the OTP. Returns a normalised phone number to carry into verification —
 * verify must be given exactly the same string that was sent.
 */
export async function sendOtp(
  client: FaizyClient,
  rawPhone: string,
  opts: { country?: "AE" | "SA" | "PK"; channel?: OtpChannel; fullName?: string } = {},
): Promise<{ phone: string } | { error: string }> {
  const phone = toE164(rawPhone, opts.country ?? "AE");
  if (!phone) return { error: "That doesn't look like a valid phone number." };

  const { error } = await client.auth.signInWithOtp({
    phone,
    options: {
      channel: opts.channel ?? "whatsapp",
      // Only used on first sign-in, when the profile row is created by trigger.
      data: opts.fullName ? { full_name: opts.fullName } : undefined,
    },
  });

  if (error) return { error: error.message };
  return { phone };
}

/** Verify the 6-digit code. On success the session is persisted by the client. */
export async function verifyOtp(
  client: FaizyClient,
  phone: string,
  token: string,
): Promise<{ userId: string } | { error: string }> {
  const { data, error } = await client.auth.verifyOtp({ phone, token, type: "sms" });
  if (error) return { error: error.message };
  if (!data.user) return { error: "Verification failed. Please try again." };
  return { userId: data.user.id };
}

/** The signed-in user's role, read from the JWT rather than the database. */
export function roleFromSession(appMetadata: Record<string, unknown> | undefined): "customer" | "worker" | "admin" {
  const role = appMetadata?.["role"];
  return role === "admin" || role === "worker" ? role : "customer";
}
