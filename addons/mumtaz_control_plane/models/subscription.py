from odoo import fields, models


class MumtazSubscription(models.Model):
    _name = "mumtaz.subscription"
    _description = "Mumtaz Subscription"
    _order = "renewal_date, id desc"

    tenant_id = fields.Many2one("mumtaz.tenant", required=True, ondelete="cascade", index=True)
    plan_id = fields.Many2one("mumtaz.plan", required=True, ondelete="restrict", index=True)

    status = fields.Selection(
        [
            ("trial", "Trial"),
            ("active", "Active"),
            ("past_due", "Past Due"),
            ("grace", "Grace"),
            ("suspended", "Suspended"),
            ("cancelled", "Cancelled"),
            ("expired", "Expired"),
        ],
        default="trial",
        required=True,
    )
    billing_cycle = fields.Selection(
        [
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("yearly", "Yearly"),
            ("custom", "Custom"),
        ],
        default="monthly",
        required=True,
    )

    start_date = fields.Date()
    renewal_date = fields.Date(index=True)
    end_date = fields.Date()
    trial_start = fields.Date()
    trial_end = fields.Date()

    payment_status = fields.Selection(
        [
            ("paid", "Paid"),
            ("pending", "Pending"),
            ("overdue", "Overdue"),
            ("waived", "Waived"),
        ],
        default="pending",
        required=True,
    )
    outstanding_amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
        ondelete="restrict",
    )
    grace_until = fields.Date()
    external_billing_ref = fields.Char()
    custom_pricing_notes = fields.Text()
    is_current = fields.Boolean(default=True)

    def name_get(self):
        result = []
        for rec in self:
            label = f"{rec.tenant_id.name} - {rec.plan_id.name}"
            result.append((rec.id, label))
        return result
