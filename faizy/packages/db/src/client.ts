import { createBrowserClient, createServerClient, type CookieOptions } from "@supabase/ssr";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { Database } from "./generated/database.types";

export type FaizyClient = SupabaseClient<Database>;

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

/**
 * Browser client. Uses the anon key, which is public by design — every read and
 * write it performs is gated by RLS. See supabase/migrations/..._rls.sql.
 */
export function createFaizyBrowserClient(): FaizyClient {
  return createBrowserClient<Database>(
    requireEnv("NEXT_PUBLIC_SUPABASE_URL"),
    requireEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY"),
  );
}

/**
 * Server client bound to the request's cookies, so RLS still sees the signed-in
 * user. This is what server components and route handlers should use.
 */
export function createFaizyServerClient(cookies: {
  get: (name: string) => string | undefined;
  set: (name: string, value: string, options: CookieOptions) => void;
  remove: (name: string, options: CookieOptions) => void;
}): FaizyClient {
  return createServerClient<Database>(
    requireEnv("NEXT_PUBLIC_SUPABASE_URL"),
    requireEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY"),
    {
      cookies: {
        get: cookies.get,
        set: cookies.set,
        remove: cookies.remove,
      },
    },
  );
}

/**
 * Service-role client. **BYPASSES RLS ENTIRELY.**
 *
 * Only ever construct this in server-only code — route handlers, server actions,
 * Edge Functions. It throws if it detects a browser environment, because the
 * single fastest way to fully compromise a Supabase app is to let this key reach
 * the client bundle. Note the env var has no NEXT_PUBLIC_ prefix, which keeps
 * Next.js from inlining it into client code in the first place.
 *
 * Use it for exactly three things: admin panel privileged reads, billing writes,
 * and the WhatsApp queue drain.
 */
export function createFaizyAdminClient(): FaizyClient {
  if (typeof window !== "undefined") {
    throw new Error(
      "createFaizyAdminClient() was called in the browser. The service-role key " +
        "bypasses RLS and must never leave the server.",
    );
  }
  return createClient<Database>(
    requireEnv("NEXT_PUBLIC_SUPABASE_URL"),
    requireEnv("SUPABASE_SERVICE_ROLE_KEY"),
    { auth: { persistSession: false, autoRefreshToken: false } },
  );
}
