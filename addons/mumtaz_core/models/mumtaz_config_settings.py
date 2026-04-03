from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Extends Odoo's native Settings page with Mumtaz AI configuration."""
    _inherit = "res.config.settings"

    # ── AI Provider ───────────────────────────────────────────────────────
    mumtaz_ai_provider = fields.Selection(
        [("none", "Disabled"), ("openai", "OpenAI (GPT-4o)"), ("anthropic", "Anthropic (Claude)")],
        string="AI Provider",
        compute="_compute_mumtaz", inverse="_set_mumtaz",
    )
    mumtaz_api_key = fields.Char(
        string="API Key",
        compute="_compute_mumtaz", inverse="_set_mumtaz",
    )
    mumtaz_openai_model = fields.Selection(
        [("gpt-4o-mini", "GPT-4o Mini (fast)"),
         ("gpt-4o", "GPT-4o (most capable)"),
         ("gpt-4-turbo", "GPT-4 Turbo")],
        string="OpenAI Chat Model",
        compute="_compute_mumtaz", inverse="_set_mumtaz",
    )
    mumtaz_anthropic_model = fields.Selection(
        [("claude-haiku-4-5-20251001", "Claude Haiku 4.5 (fast)"),
         ("claude-sonnet-4-6", "Claude Sonnet 4.6 (balanced)"),
         ("claude-opus-4-6", "Claude Opus 4.6 (most capable)")],
        string="Anthropic Chat Model",
        compute="_compute_mumtaz", inverse="_set_mumtaz",
    )

    # ── Voice & TTS ───────────────────────────────────────────────────────
    mumtaz_tts_model = fields.Selection(
        [("tts-1", "Standard (faster)"), ("tts-1-hd", "HD (more natural)")],
        string="TTS Quality",
        compute="_compute_mumtaz", inverse="_set_mumtaz",
    )
    mumtaz_tts_voice = fields.Selection(
        [("nova", "Nova — warm, natural"),
         ("alloy", "Alloy — neutral"),
         ("echo", "Echo — clear"),
         ("onyx", "Onyx — deep, authoritative"),
         ("shimmer", "Shimmer — soft")],
        string="TTS Voice",
        compute="_compute_mumtaz", inverse="_set_mumtaz",
    )
    mumtaz_voice_language = fields.Selection(
        [("en-US", "English (US)"), ("en-GB", "English (UK)"),
         ("ar-SA", "Arabic (Saudi Arabia)"), ("ar-AE", "Arabic (UAE)"),
         ("fr-FR", "French"), ("de-DE", "German"), ("es-ES", "Spanish")],
        string="Default Voice Language",
        compute="_compute_mumtaz", inverse="_set_mumtaz",
    )

    # ── Limits ────────────────────────────────────────────────────────────
    mumtaz_max_tokens = fields.Integer(
        string="Max Tokens / Response",
        compute="_compute_mumtaz", inverse="_set_mumtaz",
    )
    mumtaz_history_depth = fields.Integer(
        string="Conversation Memory (messages)",
        compute="_compute_mumtaz", inverse="_set_mumtaz",
    )

    # ── Feature toggles ───────────────────────────────────────────────────
    mumtaz_feature_voice = fields.Boolean(
        string="CFO Voice Assistant",
        compute="_compute_mumtaz", inverse="_set_mumtaz",
    )
    mumtaz_feature_ai_chat = fields.Boolean(
        string="AI Chat Sessions",
        compute="_compute_mumtaz", inverse="_set_mumtaz",
    )
    mumtaz_feature_financial = fields.Boolean(
        string="Financial Insights (P&L, Cash, AR/AP)",
        compute="_compute_mumtaz", inverse="_set_mumtaz",
    )
    mumtaz_feature_sales = fields.Boolean(
        string="Sales Insights",
        compute="_compute_mumtaz", inverse="_set_mumtaz",
    )
    mumtaz_feature_crm = fields.Boolean(
        string="CRM Insights",
        compute="_compute_mumtaz", inverse="_set_mumtaz",
    )

    # ── Helpers ───────────────────────────────────────────────────────────
    def _mumtaz_settings(self):
        """Return the mumtaz.core.settings record for the current company."""
        return self.env["mumtaz.core.settings"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        )

    def _compute_mumtaz(self):
        for rec in self:
            s = rec._mumtaz_settings()
            rec.mumtaz_ai_provider = s.ai_provider if s else "none"
            rec.mumtaz_api_key = s.api_key if s else ""
            rec.mumtaz_openai_model = s.openai_model if s else "gpt-4o-mini"
            rec.mumtaz_anthropic_model = s.anthropic_model if s else "claude-haiku-4-5-20251001"
            rec.mumtaz_tts_model = s.tts_model if s else "tts-1"
            rec.mumtaz_tts_voice = s.tts_voice if s else "nova"
            rec.mumtaz_voice_language = s.voice_language if s else "en-US"
            rec.mumtaz_max_tokens = s.max_tokens_per_request if s else 600
            rec.mumtaz_history_depth = s.conversation_history_depth if s else 10
            rec.mumtaz_feature_voice = s.feature_voice_enabled if s else False
            rec.mumtaz_feature_ai_chat = s.feature_ai_chat_enabled if s else False
            rec.mumtaz_feature_financial = s.feature_financial_insights_enabled if s else False
            rec.mumtaz_feature_sales = s.feature_sales_insights_enabled if s else False
            rec.mumtaz_feature_crm = s.feature_crm_insights_enabled if s else False

    def _set_mumtaz(self):
        for rec in self:
            s = rec._mumtaz_settings()
            vals = {
                "ai_provider": rec.mumtaz_ai_provider,
                "openai_model": rec.mumtaz_openai_model,
                "anthropic_model": rec.mumtaz_anthropic_model,
                "tts_model": rec.mumtaz_tts_model,
                "tts_voice": rec.mumtaz_tts_voice,
                "voice_language": rec.mumtaz_voice_language,
                "max_tokens_per_request": rec.mumtaz_max_tokens,
                "conversation_history_depth": rec.mumtaz_history_depth,
                "feature_voice_enabled": rec.mumtaz_feature_voice,
                "feature_ai_chat_enabled": rec.mumtaz_feature_ai_chat,
                "feature_financial_insights_enabled": rec.mumtaz_feature_financial,
                "feature_sales_insights_enabled": rec.mumtaz_feature_sales,
                "feature_crm_insights_enabled": rec.mumtaz_feature_crm,
            }
            # Only write api_key if the user actually entered something
            if rec.mumtaz_api_key:
                vals["api_key"] = rec.mumtaz_api_key
            if s:
                s.write(vals)
            else:
                vals["company_id"] = self.env.company.id
                self.env["mumtaz.core.settings"].sudo().create(vals)
