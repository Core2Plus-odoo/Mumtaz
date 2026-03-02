from odoo import fields, models


class MumtazCoreSettings(models.Model):
    _name = "mumtaz.core.settings"
    _description = "Mumtaz Core Company Settings"
    _rec_name = "company_id"

    company_id = fields.Many2one("res.company", required=True, ondelete="cascade", index=True)
    api_key = fields.Char(
        string="Mumtaz API Key",
        password=True,
        groups="base.group_system",
        help="Provider API key used by Mumtaz AI integrations.",
    )
    ai_provider = fields.Selection(
        [
            ("none", "No Provider"),
            ("generic", "Generic Provider"),
        ],
        default="none",
        required=True,
    )
    feature_ai_chat_enabled = fields.Boolean(default=True)
    feature_financial_insights_enabled = fields.Boolean(default=True)
    feature_crm_insights_enabled = fields.Boolean(default=False)
    feature_sales_insights_enabled = fields.Boolean(default=False)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "mumtaz_core_settings_company_unique",
            "unique(company_id)",
            "Each company can only have one Mumtaz settings record.",
        )
    ]
