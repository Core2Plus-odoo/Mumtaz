from odoo import _, api, fields, models


class MumtazSubscriptionBillingRecord(models.Model):

    _name = "mumtaz.subscription.billing.record"
    _description = "Mumtaz Subscription Billing Record"
    _order = "create_date desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    operation_id = fields.Many2one("mumtaz.commercial.operation", ondelete="set null", index=True)
    subscription_id = fields.Many2one("mumtaz.subscription", required=True, ondelete="cascade", index=True)
    tenant_id = fields.Many2one("mumtaz.tenant", related="subscription_id.tenant_id", store=True, readonly=True)
    record_type = fields.Selection(
        [
            ("renewal", "Renewal"),
            ("upgrade", "Upgrade"),
            ("reactivation", "Reactivation"),
            ("grace_extension", "Grace Extension"),
            ("manual", "Manual"),
        ],
        required=True,
        default="manual",
    )
    amount_due = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency", required=True, default=lambda self: self.env.company.currency_id, ondelete="restrict"
    )
    issued_date = fields.Date(default=fields.Date.context_today)
    due_date = fields.Date()
    paid_date = fields.Date()
    payment_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("under_review", "Under Review"),
            ("invoiced", "Invoiced"),
            ("paid", "Paid"),
            ("waived", "Waived"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    external_reference = fields.Char()
    commercial_notes = fields.Text()

    def _log_payment(self, from_value, to_value, summary):
        for rec in self:
            self.env["mumtaz.commercial.event.log"].sudo().create(
                {
                    "tenant_id": rec.tenant_id.id,
                    "subscription_id": rec.subscription_id.id,
                    "operation_id": rec.operation_id.id,
                    "billing_record_id": rec.id,
                    "event_type": "payment_status",
                    "from_value": from_value,
                    "to_value": to_value,
                    "summary": summary,
                }
            )

    def action_mark_under_review(self):
        for rec in self:
            previous = rec.payment_status
            rec.payment_status = "under_review"
            rec._log_payment(previous, rec.payment_status, _("Billing moved to under review."))
        return True

    def action_mark_invoiced(self):
        for rec in self:
            previous = rec.payment_status
            rec.payment_status = "invoiced"
            rec._log_payment(previous, rec.payment_status, _("Billing marked as invoiced."))
            if rec.operation_id:
                rec.operation_id._update_status("invoiced", _("Billing invoiced."))
        return True

    def action_mark_paid(self):
        for rec in self:
            previous = rec.payment_status
            rec.payment_status = "paid"
            rec.paid_date = fields.Date.context_today(self)
            rec._log_payment(previous, rec.payment_status, _("Billing marked as paid."))
            if rec.operation_id:
                rec.operation_id.action_mark_paid()
        return True

    def action_mark_waived(self):
        for rec in self:
            previous = rec.payment_status
            rec.payment_status = "waived"
            rec._log_payment(previous, rec.payment_status, _("Billing waived."))
            if rec.operation_id:
                rec.operation_id.action_mark_paid()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.name == "New":
                rec.name = f"BILL-{rec.id:06d}"
        return records
