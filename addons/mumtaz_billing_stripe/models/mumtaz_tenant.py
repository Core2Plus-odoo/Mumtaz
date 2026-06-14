import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MumtazTenant(models.Model):
    _inherit = "mumtaz.tenant"

    stripe_customer_id = fields.Char(
        string="Stripe Customer ID", copy=False, readonly=True,
        groups="mumtaz_control_plane.group_mumtaz_billing_admin,"
               "mumtaz_control_plane.group_mumtaz_super_admin",
    )
    stripe_payment_method_id = fields.Char(
        string="Default Payment Method", copy=False, readonly=True,
        groups="mumtaz_control_plane.group_mumtaz_billing_admin,"
               "mumtaz_control_plane.group_mumtaz_super_admin",
    )
    stripe_card_brand = fields.Char(string="Card Brand", copy=False, readonly=True)
    stripe_card_last4 = fields.Char(string="Card Last 4", copy=False, readonly=True)
    stripe_has_card = fields.Boolean(
        string="Card on File", compute="_compute_stripe_has_card", store=True,
    )

    @api.depends("stripe_payment_method_id")
    def _compute_stripe_has_card(self):
        for tenant in self:
            tenant.stripe_has_card = bool(tenant.stripe_payment_method_id)

    # ── Customer provisioning ─────────────────────────────────────────────
    def _ensure_stripe_customer(self):
        """Return the Stripe customer id, creating it on first use."""
        self.ensure_one()
        if self.stripe_customer_id:
            return self.stripe_customer_id
        client = self.env["mumtaz.stripe.client"]
        email = self.admin_email or (self.partner_id.email if self.partner_id else "")
        customer = client.create_customer(
            name=self.name, email=email,
            metadata={"tenant_code": self.code or "", "tenant_id": str(self.id)},
        )
        self.sudo().stripe_customer_id = customer.get("id")
        return self.stripe_customer_id

    def action_setup_payment_method(self):
        """Open the Stripe Elements card-collection page in a new tab."""
        self.ensure_one()
        client = self.env["mumtaz.stripe.client"]
        if not client._is_configured():
            raise UserError(
                "Stripe is not configured. Set STRIPE_SECRET_KEY in /opt/mumtaz/.env."
            )
        settings = self.env["mumtaz.stripe.settings"].sudo().get_singleton()
        if not settings.publishable_key:
            raise UserError(
                "No Stripe publishable key set. Add it in Control Plane → Stripe Settings."
            )
        return {
            "type": "ir.actions.act_url",
            "url": "/mumtaz/stripe/card/%s" % self.id,
            "target": "new",
        }

    def _set_default_payment_method(self, payment_method_id, card=None):
        """Persist the off-session payment method (called from the webhook)."""
        self.ensure_one()
        vals = {"stripe_payment_method_id": payment_method_id}
        if card:
            vals["stripe_card_brand"] = card.get("brand")
            vals["stripe_card_last4"] = card.get("last4")
        self.sudo().write(vals)
