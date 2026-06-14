from odoo import fields, models


class MumtazStripeEvent(models.Model):
    """Idempotency + audit log for inbound Stripe webhook events."""
    _name = "mumtaz.stripe.event"
    _description = "Mumtaz Stripe Webhook Event"
    _order = "received_at desc"

    stripe_event_id = fields.Char(string="Stripe Event ID", required=True, index=True)
    event_type = fields.Char(string="Type", index=True)
    received_at = fields.Datetime(default=fields.Datetime.now, readonly=True)
    processed = fields.Boolean(default=False, readonly=True)
    subscription_id = fields.Many2one(
        "mumtaz.subscription", ondelete="set null", readonly=True
    )
    tenant_id = fields.Many2one("mumtaz.tenant", ondelete="set null", readonly=True)
    note = fields.Char(readonly=True)

    _sql_event_unique = models.Constraint(
        "unique(stripe_event_id)",
        "This Stripe event has already been recorded.",
    )
