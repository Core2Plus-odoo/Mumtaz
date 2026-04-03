from odoo import api, fields, models


class WhatsAppProvider(models.Model):
    """Provider configuration for WhatsApp outreach."""

    _name = "lead.whatsapp.provider"
    _description = "WhatsApp Provider"
    _order = "name"
    _rec_name = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    is_default = fields.Boolean(string="Default Provider")

    provider_type = fields.Selection(
        [
            ("whatsapp_cloud", "WhatsApp Cloud API (Meta)"),
            ("twilio", "Twilio WhatsApp"),
            ("manual", "Manual / Log Only"),
        ],
        required=True,
        default="manual",
    )

    # ── WhatsApp Cloud API (Meta) ──────────────────────────────────────
    wa_phone_number_id = fields.Char(string="Phone Number ID")
    wa_access_token = fields.Char(string="Access Token")
    wa_api_version = fields.Char(string="API Version", default="v18.0")

    # ── Twilio ────────────────────────────────────────────────────────
    twilio_account_sid = fields.Char(string="Account SID")
    twilio_auth_token = fields.Char(string="Auth Token")
    twilio_from_number = fields.Char(
        string="From Number",
        help="e.g. whatsapp:+14155238886",
    )

    # ── Manual / Webhook ──────────────────────────────────────────────
    webhook_url = fields.Char(string="Webhook URL")
    webhook_token = fields.Char(string="Webhook Token")

    notes = fields.Text()

    @api.model
    def get_default_provider(self):
        """Return the default active provider, or None."""
        return self.search([("is_default", "=", True), ("active", "=", True)], limit=1) or \
               self.search([("active", "=", True)], limit=1)
