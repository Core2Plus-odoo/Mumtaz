from odoo import api, fields, models


class MumtazStripeSettings(models.Model):
    """Non-secret Stripe configuration. The secret key and webhook secret
    are read from the environment (/opt/mumtaz/.env), never stored here."""
    _name = "mumtaz.stripe.settings"
    _description = "Mumtaz Stripe Billing Settings"

    name = fields.Char(default="Stripe Billing Settings", readonly=True)
    auto_charge_enabled = fields.Boolean(
        string="Enable Automatic Charging", default=True,
        help="When enabled, the daily cron charges due subscriptions via Stripe.",
    )
    publishable_key = fields.Char(
        string="Publishable Key",
        help="Stripe publishable key (pk_…). Safe to expose to the browser; "
             "used by the card-collection form.",
    )
    statement_descriptor = fields.Char(
        string="Statement Descriptor", size=22,
        help="Text shown on the customer's card statement (max 22 chars).",
    )
    configured = fields.Boolean(
        string="Secret Key Configured", compute="_compute_configured",
        help="True when STRIPE_SECRET_KEY is present in the environment.",
    )
    webhook_configured = fields.Boolean(
        string="Webhook Secret Configured", compute="_compute_configured",
    )

    _sql_singleton = models.Constraint(
        "unique(name)", "Only one Stripe settings record is allowed."
    )

    def _compute_configured(self):
        client = self.env["mumtaz.stripe.client"]
        secret = bool(client._secret_key())
        webhook = bool(client._webhook_secret())
        for rec in self:
            rec.configured = secret
            rec.webhook_configured = webhook

    @api.model
    def get_singleton(self):
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({})
        return rec

    def action_open_settings(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Stripe Billing Settings",
            "res_model": "mumtaz.stripe.settings",
            "res_id": self.get_singleton().id,
            "view_mode": "form",
            "target": "current",
        }
