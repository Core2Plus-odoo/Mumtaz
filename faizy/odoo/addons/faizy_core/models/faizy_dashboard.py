from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class FaizyDashboard(models.TransientModel):
    """The at-a-glance view the admin prototype opened on.

    Odoo already gives us the admin panel — kanban boards, the CRM, the
    applications pipeline — so this deliberately does not rebuild any of that.
    What Odoo does not give is the one screen that answers "how is the business
    doing this morning" without opening five menus, and that is the only thing
    here.

    A TransientModel with computed fields rather than a custom OWL dashboard:
    the numbers come from `_read_group`, the layout is an ordinary form view,
    and every tile opens the real list behind it. Nothing to keep in sync with
    a JavaScript build, and the drill-through is Odoo's own.
    """

    _name = "faizy.dashboard"
    _description = "Faizy Dashboard"

    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )

    # ── Customers ────────────────────────────────────────────────────────
    active_subscriptions = fields.Integer(compute="_compute_kpis")
    mrr = fields.Monetary(
        string="MRR", compute="_compute_kpis", currency_field="currency_id"
    )
    customers = fields.Integer(compute="_compute_kpis")
    families = fields.Integer(string="Family Members", compute="_compute_kpis")

    # ── Work ─────────────────────────────────────────────────────────────
    orders_open = fields.Integer(string="Open Orders", compute="_compute_kpis")
    orders_unassigned = fields.Integer(compute="_compute_kpis")
    orders_month = fields.Integer(string="Orders This Month", compute="_compute_kpis")
    orders_completed_month = fields.Integer(compute="_compute_kpis")

    # ── Money ────────────────────────────────────────────────────────────
    revenue_month = fields.Monetary(
        compute="_compute_kpis",
        currency_field="currency_id",
        help="Platform fees plus service fees on orders completed this month. "
        "Purchases passed through to the customer are not revenue.",
    )
    commission_month = fields.Monetary(
        compute="_compute_kpis", currency_field="currency_id"
    )

    # ── Network ──────────────────────────────────────────────────────────
    workers_active = fields.Integer(compute="_compute_kpis")
    applications_pending = fields.Integer(compute="_compute_kpis")
    documents_expiring = fields.Integer(compute="_compute_kpis")
    whatsapp_queued = fields.Integer(compute="_compute_kpis")

    @api.depends("currency_id")
    def _compute_kpis(self):
        env = self.env
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        next_month = month_start + relativedelta(months=1)

        Order = env["faizy.order"]
        month_domain = [
            ("create_date", ">=", fields.Datetime.to_datetime(month_start)),
            ("create_date", "<", fields.Datetime.to_datetime(next_month)),
        ]
        completed_month = Order.search(
            [("state", "=", "completed")]
            + [
                ("date_completed", ">=", fields.Datetime.to_datetime(month_start)),
                ("date_completed", "<", fields.Datetime.to_datetime(next_month)),
            ]
        )

        subscriptions = env["faizy.subscription"].search(
            [("state", "in", ("trial", "active", "past_due"))]
        )
        company = env.company

        for record in self:
            record.active_subscriptions = len(subscriptions)
            # Subscriptions bill in their own market's currency, so this is the
            # one place FX is used — an internal comparison figure, never quoted.
            record.mrr = sum(
                sub.currency_id._convert(
                    sub.price, company.currency_id, company, today
                )
                for sub in subscriptions
            )
            record.customers = env["res.partner"].search_count(
                [("is_faizy_customer", "=", True)]
            )
            record.families = env["faizy.family.member"].search_count([])

            record.orders_open = Order.search_count(
                [("state", "in", ("pending", "assigned", "scheduled", "in_progress"))]
            )
            record.orders_unassigned = Order.search_count(
                [("state", "=", "pending"), ("worker_id", "=", False)]
            )
            record.orders_month = Order.search_count(month_domain)
            record.orders_completed_month = len(completed_month)

            # Revenue is what Faizy keeps: the service fee for the errand plus
            # the platform fee. purchase_value belongs to the shop, and counting
            # it would inflate the number by an order of magnitude.
            record.revenue_month = sum(
                completed_month.mapped("service_fee")
            ) + sum(completed_month.mapped("platform_fee"))
            record.commission_month = sum(completed_month.mapped("vendor_commission"))

            record.workers_active = env["faizy.worker"].search_count(
                [("state", "=", "active")]
            )
            record.applications_pending = env["faizy.application"].search_count(
                [("state", "in", ("submitted", "under_review", "interview"))]
            )
            record.documents_expiring = env["faizy.document"].search_count(
                [("expiry_state", "in", ("expiring", "expired"))]
            )
            record.whatsapp_queued = env["faizy.whatsapp.message"].search_count(
                [("state", "=", "queued")]
            )

    # ── Drill-through ────────────────────────────────────────────────────
    # Every tile opens the real records. A dashboard number you cannot click
    # into is a number you cannot check.

    def _open(self, name, model, domain=None, view_mode="list,form"):
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": view_mode,
            "domain": domain or [],
            "target": "current",
        }

    def action_open_subscriptions(self):
        return self._open(
            self.env._("Active Subscriptions"),
            "faizy.subscription",
            [("state", "in", ("trial", "active", "past_due"))],
        )

    def action_open_orders(self):
        return self._open(
            self.env._("Open Orders"),
            "faizy.order",
            [("state", "in", ("pending", "assigned", "scheduled", "in_progress"))],
            view_mode="kanban,list,form",
        )

    def action_open_unassigned(self):
        return self._open(
            self.env._("Waiting for a Faizy"),
            "faizy.order",
            [("state", "=", "pending"), ("worker_id", "=", False)],
            view_mode="kanban,list,form",
        )

    def action_open_applications(self):
        return self._open(
            self.env._("Applications to Review"),
            "faizy.application",
            [("state", "in", ("submitted", "under_review", "interview"))],
            view_mode="kanban,list,form",
        )

    def action_open_documents(self):
        return self._open(
            self.env._("Documents Expiring"),
            "faizy.document",
            [("expiry_state", "in", ("expiring", "expired"))],
        )

    def action_open_whatsapp(self):
        return self._open(
            self.env._("WhatsApp Queue"),
            "faizy.whatsapp.message",
            [("state", "=", "queued")],
        )

    def action_open_customers(self):
        return self._open(
            self.env._("Customers"),
            "res.partner",
            [("is_faizy_customer", "=", True)],
            view_mode="kanban,list,form",
        )

    def action_open_workers(self):
        return self._open(
            self.env._("The Ground Network"),
            "faizy.worker",
            [("state", "=", "active")],
            view_mode="kanban,list,form",
        )

    def action_orders_analysis(self):
        """Where the prototype's charts live now — Odoo's own graph and pivot.

        Service split, city split and orders by month are all one group-by
        away in these views, and they stay correct as the schema changes,
        which a hand-drawn chart would not.
        """
        return self._open(
            self.env._("Order Analysis"), "faizy.order", view_mode="graph,pivot,list"
        )
