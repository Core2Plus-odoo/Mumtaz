import requests

from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError


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
        string="API Key", password=True, groups="base.group_system",
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
                lambda l: l.level == "error" and str(l.create_date) >= cutoff
            ))

    # ── Constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        ("mumtaz_core_settings_company_unique", "unique(company_id)",
         "Each company can only have one Mumtaz settings record."),
        ("mumtaz_core_settings_tenant_code_unique", "unique(tenant_code)",
         "Tenant Code must be unique across all companies."),
    ]

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
