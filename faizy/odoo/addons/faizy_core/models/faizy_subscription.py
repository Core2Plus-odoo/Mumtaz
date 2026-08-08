from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class FaizySubscription(models.Model):
    """A customer's recurring plan, and the meter behind the paywall.

    Odoo Community ships no Subscriptions app, so the recurring cycle is
    implemented here: a scheduled action rolls the period, resets the allowance
    and raises the invoice, adding an overage line for whatever was consumed
    beyond the plan.

    The meter is deliberately server-side. `activities_used` is never written by
    a customer-facing flow — orders call :meth:`consume_activity`, which is the
    only supported way to spend one.
    """

    _name = "faizy.subscription"
    _description = "Faizy Subscription"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code("faizy.subscription")
        or "/",
    )
    partner_id = fields.Many2one(
        "res.partner", string="Customer", required=True, index=True, tracking=True
    )
    plan_id = fields.Many2one("faizy.plan", required=True, tracking=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("trial", "Trial"),
            ("active", "Active"),
            ("past_due", "Past Due"),
            ("paused", "Paused"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    currency_id = fields.Many2one(related="plan_id.currency_id", store=True)
    price = fields.Monetary(related="plan_id.price", currency_field="currency_id")

    date_start = fields.Date(default=fields.Date.context_today, required=True)
    period_start = fields.Date(required=True, default=fields.Date.context_today)
    period_end = fields.Date(required=True)
    next_invoice_date = fields.Date(index=True)
    date_cancelled = fields.Date(readonly=True)
    cancel_at_period_end = fields.Boolean(
        help="Stay active until the current period ends, then cancel."
    )

    activities_included = fields.Integer(
        required=True,
        help="Copied from the plan when the period opens, so changing the plan "
        "later never rewrites history.",
    )
    activities_used = fields.Integer(readonly=True, copy=False)
    activities_remaining = fields.Integer(compute="_compute_activities_remaining")
    activity_ids = fields.One2many("faizy.activity.log", "subscription_id")

    invoice_ids = fields.Many2many("account.move", string="Invoices", copy=False)
    invoice_count = fields.Integer(compute="_compute_invoice_count")

    _sql_activities_positive = models.Constraint(
        "CHECK (activities_used >= 0)", "Activities used cannot be negative."
    )

    @api.depends("activities_included", "activities_used")
    def _compute_activities_remaining(self):
        for sub in self:
            sub.activities_remaining = max(
                0, sub.activities_included - sub.activities_used
            )

    @api.depends("invoice_ids")
    def _compute_invoice_count(self):
        for sub in self:
            sub.invoice_count = len(sub.invoice_ids)

    @api.onchange("plan_id")
    def _onchange_plan_id(self):
        if self.plan_id:
            self.activities_included = self.plan_id.activities_included

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            plan = self.env["faizy.plan"].browse(vals.get("plan_id"))
            if plan and not vals.get("activities_included"):
                vals["activities_included"] = plan.activities_included
            start = fields.Date.to_date(vals.get("period_start")) or fields.Date.context_today(self)
            if not vals.get("period_end"):
                vals["period_end"] = start + relativedelta(months=1)
            if not vals.get("next_invoice_date"):
                vals["next_invoice_date"] = vals["period_end"]
        return super().create(vals_list)

    # ── Lifecycle ────────────────────────────────────────────────────────

    def action_start(self):
        """Put the subscription live. Only one may be live per customer."""
        for sub in self:
            other = self.search(
                [
                    ("partner_id", "=", sub.partner_id.id),
                    ("id", "!=", sub.id),
                    ("state", "in", ("trial", "active", "past_due", "paused")),
                ],
                limit=1,
            )
            if other:
                raise UserError(
                    self.env._(
                        "%(customer)s already has a live subscription (%(name)s). "
                        "Cancel it before starting another.",
                        customer=sub.partner_id.display_name,
                        name=other.name,
                    )
                )
            sub.state = "active"

    def action_pause(self):
        self.write({"state": "paused"})

    def action_resume(self):
        self.filtered(lambda s: s.state == "paused").write({"state": "active"})

    def action_cancel(self):
        self.write(
            {"state": "cancelled", "date_cancelled": fields.Date.context_today(self)}
        )

    def action_view_invoices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.invoice_ids.ids)],
        }

    # ── The meter ────────────────────────────────────────────────────────

    def consume_activity(self, order=None):
        """Spend one care activity and record where it came from.

        Consumption order is: the customer's free grant, then the plan's monthly
        allowance, then overage. Returns the source so the caller can tell the
        customer what happened.

        Raises if there is nothing left and no subscription to bill against —
        that is the paywall.
        """
        self.ensure_one()
        partner = self.partner_id

        if partner.faizy_free_activities > 0:
            partner.sudo().faizy_free_activities -= 1
            source, amount = "free", 0.0
        elif self.activities_used < self.activities_included:
            self.sudo().activities_used += 1
            source, amount = "included", 0.0
        else:
            self.sudo().activities_used += 1
            source, amount = "overage", self.plan_id.overage_price

        self.env["faizy.activity.log"].sudo().create(
            {
                "subscription_id": self.id,
                "partner_id": partner.id,
                "order_id": order.id if order else False,
                "source": source,
                "amount": amount,
                "currency_id": self.currency_id.id,
            }
        )
        return source

    # ── Recurring invoicing ──────────────────────────────────────────────

    def _prepare_invoice_lines(self, overage_count):
        """Subscription line, plus one overage line when the meter overran."""
        self.ensure_one()
        plan = self.plan_id
        if not plan.product_id:
            raise UserError(
                self.env._(
                    "Plan %(plan)s has no subscription product set, so it cannot "
                    "be invoiced. Set one on the plan.",
                    plan=plan.name,
                )
            )

        lines = [
            (
                0,
                0,
                {
                    "product_id": plan.product_id.id,
                    "name": self.env._(
                        "%(plan)s — %(start)s to %(end)s",
                        plan=plan.name,
                        start=self.period_start,
                        end=self.period_end,
                    ),
                    "quantity": 1,
                    "price_unit": plan.price,
                },
            )
        ]

        if overage_count > 0 and plan.overage_price:
            if not plan.overage_product_id:
                raise UserError(
                    self.env._(
                        "Plan %(plan)s billed %(n)s extra activities but has no "
                        "overage product set.",
                        plan=plan.name,
                        n=overage_count,
                    )
                )
            lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": plan.overage_product_id.id,
                        "name": self.env._(
                            "Additional care activities (%(n)s)", n=overage_count
                        ),
                        "quantity": overage_count,
                        "price_unit": plan.overage_price,
                    },
                )
            )
        return lines

    def _generate_invoice(self):
        """Raise the invoice for the closing period and roll to the next one."""
        self.ensure_one()
        overage = max(0, self.activities_used - self.activities_included)

        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_id.id,
                "invoice_date": fields.Date.context_today(self),
                "currency_id": self.currency_id.id,
                "invoice_origin": self.name,
                "invoice_line_ids": self._prepare_invoice_lines(overage),
            }
        )
        self.invoice_ids = [(4, invoice.id)]

        # Roll the period: new window, allowance reset, meter back to zero.
        self.write(
            {
                "period_start": self.period_end,
                "period_end": self.period_end + relativedelta(months=1),
                "next_invoice_date": self.period_end + relativedelta(months=1),
                "activities_included": self.plan_id.activities_included,
                "activities_used": 0,
            }
        )
        self.message_post(
            body=self.env._(
                "Invoice %(inv)s raised. %(n)s activity overage billed.",
                inv=invoice.name,
                n=overage,
            )
        )
        return invoice

    @api.model
    def _cron_recurring_invoice(self):
        """Daily: invoice every subscription whose period has closed."""
        today = fields.Date.context_today(self)
        due = self.search(
            [
                ("state", "in", ("trial", "active", "past_due")),
                ("next_invoice_date", "<=", today),
            ]
        )
        for sub in due:
            if sub.cancel_at_period_end:
                sub.action_cancel()
                continue
            try:
                sub._generate_invoice()
            except UserError as err:
                # One misconfigured plan must not stop the whole run.
                sub.message_post(
                    body=self.env._("Recurring invoice failed: %(err)s", err=err)
                )
        return True


class FaizyActivityLog(models.Model):
    """Append-only record of every care activity consumed.

    This is the audit trail behind each invoice line. Nothing rewrites these
    rows — if a correction is needed, add another row.
    """

    _name = "faizy.activity.log"
    _description = "Faizy Activity Log"
    _order = "create_date desc"

    subscription_id = fields.Many2one("faizy.subscription", ondelete="set null", index=True)
    partner_id = fields.Many2one("res.partner", required=True, index=True)
    order_id = fields.Many2one("faizy.order", ondelete="set null", index=True)
    source = fields.Selection(
        [
            ("free", "Free Grant"),
            ("included", "Plan Allowance"),
            ("overage", "Overage"),
        ],
        required=True,
    )
    currency_id = fields.Many2one("res.currency")
    amount = fields.Monetary(currency_field="currency_id")
