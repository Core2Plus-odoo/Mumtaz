from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MumtazCoreSettings(models.Model):
    _name = "mumtaz.core.settings"
    _description = "Mumtaz Core Company Settings"
    _rec_name = "company_id"
    _check_company_auto = True

    company_id = fields.Many2one(
        "res.company", required=True, ondelete="cascade", index=True, check_company=True
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", string="Company Currency", store=False, readonly=True
    )
    tenant_code = fields.Char(
        required=True, copy=False,
        help="Unique tenant identifier used for external routing and integration context.",
    )
    api_key = fields.Char(
        string="Mumtaz API Key", password=True, groups="base.group_system",
        help="Provider API key used by Mumtaz AI integrations (OpenAI or Anthropic).",
    )
    ai_provider = fields.Selection(
        [
            ("none", "No Provider"),
            ("generic", "Generic Provider"),
            ("openai", "OpenAI (GPT-4o / GPT-4o-mini)"),
            ("anthropic", "Anthropic (Claude)"),
        ],
        default="none", required=True,
    )
    openai_model = fields.Selection(
        [
            ("gpt-4o-mini", "GPT-4o Mini (fast, cost-effective)"),
            ("gpt-4o", "GPT-4o (most capable)"),
            ("gpt-4-turbo", "GPT-4 Turbo"),
        ],
        string="OpenAI Model", default="gpt-4o-mini",
        help="Select the OpenAI model. Only used when AI Provider is set to OpenAI.",
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
        string="Voice Language", default="en-US",
        help="Language for voice input recognition and text-to-speech in the CFO Voice Assistant.",
    )
    max_tokens_per_request = fields.Integer(default=600, required=True)
    requests_per_minute_limit = fields.Integer(default=30, required=True)
    feature_ai_chat_enabled = fields.Boolean(default=True)
    feature_financial_insights_enabled = fields.Boolean(default=True)
    feature_crm_insights_enabled = fields.Boolean(default=False)
    feature_sales_insights_enabled = fields.Boolean(default=False)
    feature_voice_enabled = fields.Boolean(
        string="CFO Voice Assistant", default=True,
        help="Enable the Mumtaz CFO Voice Assistant for this company.",
    )
    active = fields.Boolean(default=True)

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

    @api.constrains("max_tokens_per_request", "requests_per_minute_limit")
    def _check_limits(self):
        for record in self:
            if record.max_tokens_per_request <= 0:
                raise ValidationError("Max tokens per request must be greater than zero.")
            if record.requests_per_minute_limit <= 0:
                raise ValidationError("Requests per minute limit must be greater than zero.")
