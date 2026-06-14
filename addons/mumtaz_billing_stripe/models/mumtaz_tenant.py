import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

from .stripe_client import StripeError

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
        """Create a SetupIntent and return its client_secret so a card can be
        collected. Returns a notification carrying the client_secret; the
        portal/JS layer uses it with Stripe.js to attach the card."""
        self.ensure_one()
        client = self.env["mumtaz.stripe.client"]
        if not client._is_configured():
            raise UserError(
                "Stripe is not configured. Set STRIPE_SECRET_KEY in /opt/mumtaz/.env."
            )
        try:
            customer_id = self._ensure_stripe_customer()
            intent = client.create_setup_intent(customer_id)
        except StripeError as exc:
            raise UserError(exc.user_message)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Setup Intent Created",
                "message": "Use the card-collection page to enter card details. "
                           "Client secret: %s" % intent.get("client_secret", ""),
                "type": "success",
                "sticky": True,
            },
        }

    def _set_default_payment_method(self, payment_method_id, card=None):
        """Persist the off-session payment method (called from the webhook)."""
        self.ensure_one()
        vals = {"stripe_payment_method_id": payment_method_id}
        if card:
            vals["stripe_card_brand"] = card.get("brand")
            vals["stripe_card_last4"] = card.get("last4")
        self.sudo().write(vals)
