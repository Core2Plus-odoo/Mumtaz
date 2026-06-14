import logging

import requests

from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

_PLATFORM_DEFAULT_URL = "https://app.mumtaz.digital"


class MumtazCoreSettings(models.Model):
    _name = "mumtaz.core.settings"
    _description = "Mumtaz Core Company Settings"
    _rec_name = "company_id"
    _check_company_auto = True

    # ── Identity ──────────────────────────────────────────────────────────
    company_id = fields.Many2one(
        "res.company", required=True, ondelete="cascade", index=True
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", string="Company Currency", store=False, readonly=True
    )
    tenant_code = fields.Char(
        required=True, copy=False,
        help="Unique tenant identifier used for external routing and integration context.",
    )
    active = fields.Boolean(default=True)

    # ── AI Provider ───────────────────────────────────────────────────────
    ai_provider = fields.Selection(
        [
            ("none", "No Provider"),
            ("openai", "OpenAI (GPT-4o / GPT-4o-mini)"),
            ("anthropic", "Anthropic (Claude)"),
        ],
        default="none", required=True, string="AI Provider",
    )
    api_key = fields.Char(
        string="API Key", groups="base.group_system",
        help="OpenAI or Anthropic API key depending on the selected provider.",
    )
    openai_model = fields.Selection(
        [
            ("gpt-4o-mini", "GPT-4o Mini — fast, cost-effective"),
            ("gpt-4o", "GPT-4o — most capable"),
            ("gpt-4-turbo", "GPT-4 Turbo"),
        ],
        string="OpenAI Chat Model", default="gpt-4o-mini",
    )
    anthropic_model = fields.Selection(
        [
            ("claude-haiku-4-5-20251001", "Claude Haiku 4.5 — fast, cost-effective"),
            ("claude-sonnet-4-6", "Claude Sonnet 4.6 — balanced"),
            ("claude-opus-4-6", "Claude Opus 4.6 — most capable"),
        ],
        string="Anthropic Chat Model", default="claude-haiku-4-5-20251001",
    )
    connection_status = fields.Char(
        string="Connection Status", readonly=True, copy=False,
        help="Last API connection test result.",
    )

    # ── Voice & TTS ───────────────────────────────────────────────────────
    tts_provider = fields.Selection(
        [
            ("openai", "OpenAI TTS"),
            ("elevenlabs", "ElevenLabs"),
        ],
        string="TTS Provider", default="openai",
        help="Provider for text-to-speech audio generation.",
    )
    elevenlabs_api_key = fields.Char(
        string="ElevenLabs API Key",
        groups="base.group_system",
        help="API key for ElevenLabs TTS. Obtain from elevenlabs.io/app/speech-synthesis.",
    )
    elevenlabs_voice_id = fields.Char(
        string="ElevenLabs Voice ID",
        default="21m00Tcm4TlvDq8ikWAM",
        help="ElevenLabs voice ID. Default: Rachel (21m00Tcm4TlvDq8ikWAM). "
             "Find IDs at elevenlabs.io/voice-library.",
    )
    elevenlabs_model = fields.Selection(
        [
            ("eleven_multilingual_v2", "Multilingual v2 — best quality"),
            ("eleven_monolingual_v1", "Monolingual v1 — English, faster"),
            ("eleven_turbo_v2_5", "Turbo v2.5 — lowest latency"),
        ],
        string="ElevenLabs Model", default="eleven_multilingual_v2",
    )
    voice_language = fields.Selection(
        [
            ("en-US", "English (US)"),
            ("en-GB", "English (UK)"),
            ("ar-SA", "Arabic (Saudi Arabia)"),
            ("ar-AE", "Arabic (UAE)"),
            ("fr-FR", "French"),
            ("de-DE", "German"),
            ("es-ES", "Spanish"),
        ],
        string="Default Voice Language", default="en-US",
        help="Default speech recognition language for the CFO Voice Assistant.",
    )
    tts_model = fields.Selection(
        [
            ("tts-1", "TTS-1 — standard quality, faster"),
            ("tts-1-hd", "TTS-1 HD — higher quality, slower"),
        ],
        string="TTS Model", default="tts-1",
        help="OpenAI text-to-speech model. TTS-1 HD provides more natural audio.",
    )
    tts_voice = fields.Selection(
        [
            ("nova", "Nova — warm, natural (recommended)"),
            ("alloy", "Alloy — neutral, balanced"),
            ("echo", "Echo — clear, professional"),
            ("fable", "Fable — expressive, storytelling"),
            ("onyx", "Onyx — deep, authoritative"),
            ("shimmer", "Shimmer — soft, friendly"),
        ],
        string="TTS Voice", default="nova",
        help="OpenAI voice character for text-to-speech responses.",
    )

    # ── Limits & Performance ──────────────────────────────────────────────
    max_tokens_per_request = fields.Integer(
        default=600, required=True,
        help="Maximum tokens per AI response. Higher values allow longer answers but cost more.",
    )
    requests_per_minute_limit = fields.Integer(
        default=30, required=True,
        help="Maximum API requests per minute to stay within provider rate limits.",
    )
    conversation_history_depth = fields.Integer(
        default=10, required=True,
        help="Number of previous messages sent as context to the AI (2 per exchange). "
             "Higher values improve continuity but use more tokens.",
    )

    # ── Feature Toggles ───────────────────────────────────────────────────
    feature_voice_enabled = fields.Boolean(
        string="CFO Voice Assistant", default=True,
        help="Enable the Mumtaz CFO Voice Assistant for this company.",
    )
    feature_ai_chat_enabled = fields.Boolean(
        string="AI Chat Sessions", default=True,
        help="Enable the Mumtaz AI Chat (text-based) for this company.",
    )
    feature_financial_insights_enabled = fields.Boolean(
        string="Financial Insights", default=True,
        help="Allow the AI to query and analyse financial data (P&L, cash, AR/AP).",
    )
    feature_crm_insights_enabled = fields.Boolean(
        string="CRM Insights", default=False,
        help="Allow the AI to query CRM data (leads, opportunities, pipeline).",
    )
    feature_sales_insights_enabled = fields.Boolean(
        string="Sales Insights", default=False,
        help="Allow the AI to query sales order data.",
    )

    # ── Platform Link (app.mumtaz.digital) ────────────────────────────────
    platform_url = fields.Char(
        string="Platform URL", default=_PLATFORM_DEFAULT_URL,
        help="Base URL of the Mumtaz platform. Default: https://app.mumtaz.digital",
    )
    platform_token = fields.Char(
        string="Platform Token", groups="base.group_system",
        help="Bearer token issued by app.mumtaz.digital for this tenant. "
             "Obtain from your dashboard under Settings → API Keys.",
    )
    platform_sync_status = fields.Selection(
        [("never", "Never synced"), ("ok", "Synced"), ("error", "Error")],
        string="Platform Sync Status", default="never", readonly=True, copy=False,
    )
    platform_last_sync = fields.Datetime(
        string="Last Synced At", readonly=True, copy=False,
    )

    # ── Computed stats ────────────────────────────────────────────────────
    log_count = fields.Integer(compute="_compute_log_count", string="Total Queries")
    error_count = fields.Integer(compute="_compute_log_count", string="Errors (30 days)")

    def _compute_log_count(self):
        from datetime import datetime, timedelta
        cutoff = fields.Datetime.to_string(datetime.now() - timedelta(days=30))
        for rec in self:
            logs = self.env["mumtaz.core.log"].sudo().search(
                [("company_id", "=", rec.company_id.id)]
            )
            rec.log_count = len(logs)
            rec.error_count = len(logs.filtered(
                lambda log_entry: log_entry.level == "error" and str(log_entry.create_date) >= cutoff
            ))

    # ── Constraints ───────────────────────────────────────────────────────
    _sql_company_unique = models.Constraint("unique(company_id)", "Each company can only have one Mumtaz settings record.")
    _sql_tenant_code_unique = models.Constraint("unique(tenant_code)", "Tenant Code must be unique across all companies.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("tenant_code"):
                vals["tenant_code"] = (self.env.company.name or "tenant").strip().upper().replace(" ", "_")
        return super().create(vals_list)

    @api.constrains("max_tokens_per_request", "requests_per_minute_limit", "conversation_history_depth")
    def _check_limits(self):
        for record in self:
            if record.max_tokens_per_request <= 0:
                raise ValidationError("Max tokens per request must be greater than zero.")
            if record.requests_per_minute_limit <= 0:
                raise ValidationError("Requests per minute limit must be greater than zero.")
            if record.conversation_history_depth < 0:
                raise ValidationError("Conversation history depth cannot be negative.")

    # ── Platform Sync ─────────────────────────────────────────────────────
    def action_sync_from_platform(self):
        """Pull credentials from app.mumtaz.digital and apply them locally."""
        self.ensure_one()
        if not self.platform_token:
            raise UserError(
                "No Platform Token configured. "
                "Obtain it from app.mumtaz.digital under Settings → API Keys."
            )
        base = (self.platform_url or _PLATFORM_DEFAULT_URL).rstrip("/")
        url = f"{base}/api/v1/tenant/{self.tenant_code}/credentials"
        try:
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {self.platform_token}"},
                timeout=15,
            )
            resp.raise_for_status()
            payload = resp.json()
            self.sudo()._apply_platform_credentials(payload)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Platform Sync Successful",
                    "message": f"Credentials updated from {self.platform_url}",
                    "type": "success",
                    "sticky": False,
                },
            }
        except requests.exceptions.Timeout:
            self.sudo().write({
                "platform_sync_status": "error",
                "platform_last_sync": fields.Datetime.now(),
            })
            raise UserError("Platform sync timed out. Check that app.mumtaz.digital is reachable.")
        except requests.exceptions.HTTPError as exc:
            self.sudo().write({
                "platform_sync_status": "error",
                "platform_last_sync": fields.Datetime.now(),
            })
            raise UserError(f"Platform returned HTTP {exc.response.status_code}. Check your Platform Token.")
        except Exception as exc:
            self.sudo().write({
                "platform_sync_status": "error",
                "platform_last_sync": fields.Datetime.now(),
            })
            raise UserError("Platform sync failed. See server logs for details.")

    def _apply_platform_credentials(self, creds):
        """Write platform-provided credentials into this settings record."""
        vals = {
            "platform_sync_status": "ok",
            "platform_last_sync": fields.Datetime.now(),
        }
        # AI provider + key
        new_provider = creds.get("ai_provider")
        if new_provider in ("openai", "anthropic", "none"):
            vals["ai_provider"] = new_provider
        if new_provider == "openai" and creds.get("openai_api_key"):
            vals["api_key"] = creds["openai_api_key"]
        elif new_provider == "anthropic" and creds.get("anthropic_api_key"):
            vals["api_key"] = creds["anthropic_api_key"]
        # Model selections
        _str_fields = [
            ("openai_model", "openai_model"),
            ("anthropic_model", "anthropic_model"),
            ("tts_provider", "tts_provider"),
            ("tts_model", "tts_model"),
            ("tts_voice", "tts_voice"),
            ("elevenlabs_api_key", "elevenlabs_api_key"),
            ("elevenlabs_voice_id", "elevenlabs_voice_id"),
            ("elevenlabs_model", "elevenlabs_model"),
        ]
        for api_key, model_field in _str_fields:
            v = creds.get(api_key)
            if v is not None:
                vals[model_field] = v
        # Integer limits
        for key in ("max_tokens_per_request", "requests_per_minute_limit", "conversation_history_depth"):
            v = creds.get(key)
            if isinstance(v, int) and v > 0:
                vals[key] = v
        self.write(vals)

    @api.model
    def _cron_sync_platform_credentials(self):
        """Daily cron: sync credentials from app.mumtaz.digital for all active tenants."""
        records = self.search([("active", "=", True), ("platform_token", "!=", False)])
        for rec in records:
            try:
                rec.action_sync_from_platform()
            except Exception as exc:
                _logger.warning(
                    "Mumtaz platform credential sync failed for company %s: %s",
                    rec.company_id.name, exc,
                )

    # ── Actions ───────────────────────────────────────────────────────────
    def action_test_connection(self):
        self.ensure_one()
        if self.ai_provider == "none":
            raise UserError("No AI provider selected. Please choose OpenAI or Anthropic.")
        if not self.api_key:
            raise UserError("No API key configured. Please enter your API key first.")

        try:
            if self.ai_provider == "openai":
                status = self._test_openai()
            else:
                status = self._test_anthropic()
            self.connection_status = status
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": "Connection Successful", "message": status,
                           "type": "success", "sticky": False},
            }
        except Exception as exc:
            msg = str(exc)
            self.connection_status = f"Error: {msg}"
            raise UserError(f"Connection failed: {msg}")

    def _test_openai(self):
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.openai_model or "gpt-4o-mini",
                  "messages": [{"role": "user", "content": "Reply with OK only."}],
                  "max_tokens": 5},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        model = data.get("model", self.openai_model)
        return f"OpenAI connected \u2014 model: {model}"

    def _test_anthropic(self):
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                     "Content-Type": "application/json"},
            json={"model": self.anthropic_model or "claude-haiku-4-5-20251001",
                  "max_tokens": 5,
                  "messages": [{"role": "user", "content": "Reply with OK only."}]},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        model = data.get("model", self.anthropic_model)
        return f"Anthropic connected \u2014 model: {model}"

    def action_view_logs(self):
        self.ensure_one()
        return {
            "name": "Mumtaz Logs",
            "type": "ir.actions.act_window",
            "res_model": "mumtaz.core.log",
            "view_mode": "list,form",
            "domain": [("company_id", "=", self.company_id.id)],
        }
