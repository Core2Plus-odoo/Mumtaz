from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models


class MumtazCommercialOperation(models.Model):
    _name = "mumtaz.commercial.operation"
    _description = "Mumtaz Commercial Operation"
    _order = "requested_on desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    operation_type = fields.Selection(
        [
            ("renewal", "Renewal"),
            ("upgrade", "Upgrade"),
            ("reactivation", "Reactivation"),
            ("grace_extension", "Grace Extension"),
        ],
        required=True,
        index=True,
    )
    tenant_id = fields.Many2one("mumtaz.tenant", required=True, index=True, ondelete="cascade")
    subscription_id = fields.Many2one("mumtaz.subscription", required=True, index=True, ondelete="cascade")
    current_plan_id = fields.Many2one("mumtaz.plan", related="subscription_id.plan_id", store=True, readonly=True)
    target_plan_id = fields.Many2one("mumtaz.plan", ondelete="set null")

    status = fields.Selection(
        [
            ("requested", "Requested"),
            ("under_review", "Under Review"),
            ("approved", "Approved"),
            ("denied", "Denied"),
            ("invoiced", "Invoiced"),
            ("paid", "Paid"),
            ("pending_activation", "Pending Activation"),
            ("activated", "Activated"),
            ("cancelled", "Cancelled"),
        ],
        default="requested",
        required=True,
        index=True,
    )

    requested_by = fields.Many2one("res.users", default=lambda self: self.env.user, required=True, ondelete="restrict")
    requested_on = fields.Datetime(default=fields.Datetime.now, required=True)
    approval_user_id = fields.Many2one("res.users", ondelete="set null")
    approval_notes = fields.Text()
    commercial_notes = fields.Text()
    billing_record_id = fields.Many2one("mumtaz.subscription.billing.record", ondelete="set null")

    grace_days_requested = fields.Integer(default=3)
    grace_days_approved = fields.Integer(default=0)
    activated_on = fields.Datetime(readonly=True)

    def _log(self, event_type, summary, from_value=False, to_value=False, details=False):
        for rec in self:
            self.env["mumtaz.commercial.event.log"].sudo().create(
                {
                    "tenant_id": rec.tenant_id.id,
                    "subscription_id": rec.subscription_id.id,
                    "operation_id": rec.id,
                    "billing_record_id": rec.billing_record_id.id,
                    "event_type": event_type,
                    "from_value": from_value or False,
                    "to_value": to_value or False,
                    "summary": summary,
                    "details": details,
                }
            )

    def _update_status(self, new_status, summary):
        for rec in self:
            old = rec.status
            rec.status = new_status
            rec._log("operation_status", summary, from_value=old, to_value=new_status)

    def action_start_review(self):
        for rec in self:
            rec._update_status("under_review", _("Operation moved to review."))
        return True

    def action_approve(self):
        for rec in self:
            rec.approval_user_id = self.env.user.id
            rec._update_status("approved", _("Operation approved."))
            if rec.operation_type in ("renewal", "upgrade"):
                rec.action_create_billing_record()
            else:
                rec._update_status("pending_activation", _("Ready for activation."))
        return True

    def action_deny(self):
        for rec in self:
            rec.approval_user_id = self.env.user.id
            rec._update_status("denied", _("Operation denied."))
        return True

    def action_create_billing_record(self):
        Billing = self.env["mumtaz.subscription.billing.record"]
        for rec in self:
            if rec.billing_record_id:
                continue
            amount = rec.subscription_id.plan_id.list_price or 0.0
            if rec.operation_type == "upgrade" and rec.target_plan_id:
                amount = max((rec.target_plan_id.list_price or 0.0) - (rec.current_plan_id.list_price or 0.0), 0.0)

            bill = Billing.create(
                {
                    "operation_id": rec.id,
                    "subscription_id": rec.subscription_id.id,
                    "record_type": rec.operation_type,
                    "amount_due": amount,
                    "currency_id": rec.subscription_id.currency_id.id,
                    "due_date": fields.Date.context_today(self) + relativedelta(days=14),
                    "payment_status": "under_review",
                    "commercial_notes": rec.commercial_notes,
                }
            )
            rec.billing_record_id = bill.id
            rec._update_status("invoiced", _("Billing record created and operation invoiced."))
        return True

    def action_mark_paid(self):
        for rec in self:
            if rec.status not in ("invoiced", "approved", "under_review"):
                continue
            rec._update_status("paid", _("Payment marked received."))
            rec._update_status("pending_activation", _("Ready for activation after payment."))
        return True

    def action_activate(self):
        for rec in self:
            subscription = rec.subscription_id
            if rec.operation_type == "renewal":
                increment = {"monthly": 1, "quarterly": 3, "yearly": 12}.get(subscription.billing_cycle, 1)
                base_date = subscription.renewal_date or fields.Date.context_today(self)
                subscription.write(
                    {
                        "renewal_date": base_date + relativedelta(months=increment),
                        "payment_status": "paid",
                        "status": "active",
                        "is_current": True,
                    }
                )
                rec._log("renewal", _("Renewal activated."), details=_("Renewal date advanced."))

            elif rec.operation_type == "upgrade" and rec.target_plan_id:
                old_plan = subscription.plan_id.name
                subscription.write({"plan_id": rec.target_plan_id.id, "status": "active", "payment_status": "paid"})
                rec._log("plan_change", _("Plan upgraded."), from_value=old_plan, to_value=rec.target_plan_id.name)

            elif rec.operation_type == "reactivation":
                subscription.write({"status": "active", "payment_status": "paid", "grace_until": False})
                rec._log("reactivation", _("Subscription reactivated."))

            elif rec.operation_type == "grace_extension":
                extra_days = rec.grace_days_approved or rec.grace_days_requested or 3
                current = subscription.grace_until or fields.Date.context_today(self)
                subscription.write({"status": "grace", "grace_until": current + relativedelta(days=extra_days)})
                rec._log("grace", _("Grace extension activated."), details=_("Extended by %(d)s days", d=extra_days))

            rec.activated_on = fields.Datetime.now()
            rec._update_status("activated", _("Operation activated."))
        return True

    def action_cancel(self):
        for rec in self:
            rec._update_status("cancelled", _("Operation cancelled."))
        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.name == "New":
                rec.name = f"OPS-{rec.id:06d}"
            rec._log("operation_status", _("Operation created."), to_value=rec.status)
        return records
