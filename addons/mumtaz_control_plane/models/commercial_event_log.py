from odoo import fields, models


class MumtazCommercialEventLog(models.Model):
    _name = "mumtaz.commercial.event.log"
    _description = "Mumtaz Commercial Event Log"
    _order = "event_at desc, id desc"

    tenant_id = fields.Many2one("mumtaz.tenant", required=True, index=True, ondelete="cascade")
    subscription_id = fields.Many2one("mumtaz.subscription", index=True, ondelete="set null")
    operation_id = fields.Many2one("mumtaz.commercial.operation", index=True, ondelete="set null")
    billing_record_id = fields.Many2one("mumtaz.subscription.billing.record", index=True, ondelete="set null")

    event_type = fields.Selection(
        [
            ("operation_status", "Operation Status"),
            ("payment_status", "Payment Status"),
            ("plan_change", "Plan Change"),
            ("renewal", "Renewal"),
            ("upgrade", "Upgrade"),
            ("reactivation", "Reactivation"),
            ("grace", "Grace Action"),
            ("override", "Manual Override"),
            ("note", "Commercial Note"),
        ],
        required=True,
        index=True,
    )
    from_value = fields.Char()
    to_value = fields.Char()
    summary = fields.Char(required=True)
    details = fields.Text()
    event_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, required=True, ondelete="restrict")
