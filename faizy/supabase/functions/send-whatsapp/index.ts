/**
 * send-whatsapp — drains the `wa_notifications` queue.
 *
 * Invoked on a schedule (pg_cron or an external cron hitting this endpoint).
 * Each run claims a batch of due rows, sends them, and records the outcome.
 *
 * Why a queue drain rather than sending inline from a trigger: an outbound HTTP
 * call inside a database transaction would hold the transaction open on a
 * third-party's latency, and a failure would either roll back the order or
 * vanish silently. Here, the message is durable before anyone tries to send it,
 * and a failure is a visible row with an error and a retry time.
 *
 * Deploy:  supabase functions deploy send-whatsapp
 * Secrets: supabase secrets set WHATSAPP_PROVIDER=meta META_PHONE_NUMBER_ID=... META_ACCESS_TOKEN=...
 */

import { createClient } from "jsr:@supabase/supabase-js@2";
import { providerFromEnv, type TemplateMessage } from "./providers.ts";

const BATCH_SIZE = 25;
const MAX_ATTEMPTS = 5;

/**
 * Positional parameter order for each template. MUST match the {{1}}, {{2}}...
 * order of the template as approved in the Meta console — if they disagree, the
 * customer gets a correctly-delivered but nonsensical message.
 */
const TEMPLATE_PARAMS: Record<string, string[]> = {
  booking_confirmation: ["order_no", "title"],
  faizy_assigned: ["order_no", "faizy_name"],
  worker_assignment: ["order_no", "title", "city", "address"],
  order_status_update: ["order_no", "status"],
  order_receipt: ["order_no", "total", "currency"],
};

/** Exponential backoff: 1, 2, 4, 8, 16 minutes. */
function nextAttemptAt(attempts: number): string {
  const minutes = Math.min(2 ** attempts, 16);
  return new Date(Date.now() + minutes * 60_000).toISOString();
}

Deno.serve(async (req: Request) => {
  // The function runs with the service-role key and can send messages from the
  // business number, so it must never be openly callable.
  const secret = Deno.env.get("DRAIN_SECRET");
  if (secret && req.headers.get("x-drain-secret") !== secret) {
    return new Response("forbidden", { status: 403 });
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false } },
  );

  let provider;
  try {
    provider = providerFromEnv(Deno.env.toObject());
  } catch (err) {
    return Response.json({ error: (err as Error).message }, { status: 500 });
  }

  const { data: rows, error } = await supabase
    .from("wa_notifications")
    .select("*")
    .in("status", ["queued", "failed"])
    .lt("attempts", MAX_ATTEMPTS)
    .lte("next_attempt_at", new Date().toISOString())
    .order("next_attempt_at", { ascending: true })
    .limit(BATCH_SIZE);

  if (error) return Response.json({ error: error.message }, { status: 500 });
  if (!rows?.length) return Response.json({ drained: 0 });

  // Claim the batch before sending so a concurrent run cannot double-send.
  await supabase
    .from("wa_notifications")
    .update({ status: "sending" })
    .in("id", rows.map((r) => r.id));

  let sent = 0;
  let failed = 0;

  for (const row of rows) {
    const templateName: string = row.template_name ?? "";
    const paramOrder = TEMPLATE_PARAMS[templateName] ?? [];
    const params = paramOrder.map((key) => String(row.template_params?.[key] ?? ""));

    const msg: TemplateMessage = {
      to: row.to_phone,
      templateName,
      languageCode: row.language_code === "ur" ? "ur" : "en",
      params,
    };

    const result = await provider.sendTemplate(msg);
    const attempts = (row.attempts ?? 0) + 1;

    if (result.ok) {
      sent++;
      await supabase
        .from("wa_notifications")
        .update({
          status: "sent",
          provider: provider.name,
          provider_msg_id: result.providerMessageId,
          attempts,
          sent_at: new Date().toISOString(),
          error_message: null,
        })
        .eq("id", row.id);
    } else {
      failed++;
      // Non-retryable errors (bad template, malformed request) are parked at the
      // attempt ceiling so they stop consuming batch slots and show up in ops.
      const exhausted = !result.retryable || attempts >= MAX_ATTEMPTS;
      await supabase
        .from("wa_notifications")
        .update({
          status: "failed",
          provider: provider.name,
          attempts: exhausted ? MAX_ATTEMPTS : attempts,
          error_message: result.error,
          next_attempt_at: nextAttemptAt(attempts),
        })
        .eq("id", row.id);
    }
  }

  return Response.json({ drained: rows.length, sent, failed, provider: provider.name });
});
