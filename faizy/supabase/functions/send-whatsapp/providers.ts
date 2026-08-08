/**
 * WhatsApp provider adapters.
 *
 * Both Meta Cloud API and Twilio implement the same interface so the choice is a
 * config flag (WHATSAPP_PROVIDER) rather than a rewrite. See
 * docs/00-decisions.md §2 — the recommendation is Meta direct, with Twilio as
 * the launch fallback if Meta business verification has not cleared in time.
 */

export type SendResult =
  | { ok: true; providerMessageId: string }
  | { ok: false; error: string; retryable: boolean };

export type TemplateMessage = {
  to: string;
  templateName: string;
  languageCode: string;
  /**
   * Positional body parameters. WhatsApp templates use {{1}}, {{2}}, ... so
   * ORDER MATTERS and must match the template as approved in Meta's console.
   */
  params: string[];
};

export interface WhatsAppProvider {
  readonly name: "meta" | "twilio";
  sendTemplate(msg: TemplateMessage): Promise<SendResult>;
}

/** 4xx other than 429 means the request itself is wrong — retrying cannot help. */
function isRetryableStatus(status: number): boolean {
  return status === 429 || status >= 500;
}

// ── Meta Cloud API ───────────────────────────────────────────────────────────

export class MetaProvider implements WhatsAppProvider {
  readonly name = "meta" as const;

  constructor(
    private readonly phoneNumberId: string,
    private readonly accessToken: string,
    private readonly apiVersion = "v21.0",
  ) {}

  async sendTemplate(msg: TemplateMessage): Promise<SendResult> {
    const url = `https://graph.facebook.com/${this.apiVersion}/${this.phoneNumberId}/messages`;

    const body = {
      messaging_product: "whatsapp",
      recipient_type: "individual",
      // Meta wants the number without the leading '+'.
      to: msg.to.replace(/^\+/, ""),
      type: "template",
      template: {
        name: msg.templateName,
        language: { code: msg.languageCode },
        components: msg.params.length
          ? [{ type: "body", parameters: msg.params.map((text) => ({ type: "text", text })) }]
          : [],
      },
    };

    try {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      const json = await res.json().catch(() => ({}));

      if (!res.ok) {
        const detail = json?.error?.message ?? `HTTP ${res.status}`;
        return { ok: false, error: `meta: ${detail}`, retryable: isRetryableStatus(res.status) };
      }

      const id = json?.messages?.[0]?.id;
      if (!id) return { ok: false, error: "meta: no message id in response", retryable: true };
      return { ok: true, providerMessageId: id };
    } catch (err) {
      // Network-level failure — always worth retrying.
      return { ok: false, error: `meta: ${(err as Error).message}`, retryable: true };
    }
  }
}

// ── Twilio ───────────────────────────────────────────────────────────────────

export class TwilioProvider implements WhatsAppProvider {
  readonly name = "twilio" as const;

  constructor(
    private readonly accountSid: string,
    private readonly authToken: string,
    /** The WhatsApp-enabled sender, E.164 without the `whatsapp:` prefix. */
    private readonly fromNumber: string,
    /** Content SID map: template name → Twilio Content API SID (HX...). */
    private readonly contentSids: Record<string, string> = {},
  ) {}

  async sendTemplate(msg: TemplateMessage): Promise<SendResult> {
    const url = `https://api.twilio.com/2010-04-01/Accounts/${this.accountSid}/Messages.json`;
    const form = new URLSearchParams();
    form.set("From", `whatsapp:${this.fromNumber}`);
    form.set("To", `whatsapp:${msg.to}`);

    const contentSid = this.contentSids[msg.templateName];
    if (contentSid) {
      form.set("ContentSid", contentSid);
      // Twilio's Content API takes positional variables as a JSON object keyed "1","2",...
      form.set(
        "ContentVariables",
        JSON.stringify(Object.fromEntries(msg.params.map((p, i) => [String(i + 1), p]))),
      );
    } else {
      // No mapped content template. Only valid inside an open 24h session window;
      // surfaced as a non-retryable error so it shows up in ops rather than
      // silently looping.
      return {
        ok: false,
        error: `twilio: no ContentSid mapped for template "${msg.templateName}"`,
        retryable: false,
      };
    }

    try {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          Authorization: `Basic ${btoa(`${this.accountSid}:${this.authToken}`)}`,
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: form,
      });

      const json = await res.json().catch(() => ({}));

      if (!res.ok) {
        return {
          ok: false,
          error: `twilio: ${json?.message ?? `HTTP ${res.status}`}`,
          retryable: isRetryableStatus(res.status),
        };
      }
      return { ok: true, providerMessageId: json.sid };
    } catch (err) {
      return { ok: false, error: `twilio: ${(err as Error).message}`, retryable: true };
    }
  }
}

/** Build the configured provider from the environment. */
export function providerFromEnv(env: Record<string, string | undefined>): WhatsAppProvider {
  const choice = (env.WHATSAPP_PROVIDER ?? "meta").toLowerCase();

  if (choice === "twilio") {
    const sid = env.TWILIO_ACCOUNT_SID;
    const token = env.TWILIO_AUTH_TOKEN;
    const from = env.TWILIO_WHATSAPP_FROM;
    if (!sid || !token || !from) {
      throw new Error("Twilio selected but TWILIO_ACCOUNT_SID / AUTH_TOKEN / WHATSAPP_FROM missing");
    }
    let contentSids: Record<string, string> = {};
    if (env.TWILIO_CONTENT_SIDS) {
      try {
        contentSids = JSON.parse(env.TWILIO_CONTENT_SIDS);
      } catch {
        throw new Error("TWILIO_CONTENT_SIDS is not valid JSON");
      }
    }
    return new TwilioProvider(sid, token, from, contentSids);
  }

  const phoneId = env.META_PHONE_NUMBER_ID;
  const token = env.META_ACCESS_TOKEN;
  if (!phoneId || !token) {
    throw new Error("Meta selected but META_PHONE_NUMBER_ID / META_ACCESS_TOKEN missing");
  }
  return new MetaProvider(phoneId, token, env.META_API_VERSION ?? "v21.0");
}
