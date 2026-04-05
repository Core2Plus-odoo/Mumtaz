from odoo import api, fields, models


class MumtazTenantCommercial(models.Model):
    _inherit = "mumtaz.tenant"

    cp_plan_name = fields.Char(string="Current Plan", compute="_compute_cp_subscription_visibility")
    cp_subscription_status = fields.Selection(
        [
            ("trial", "Trial"),
            ("active", "Active"),
            ("past_due", "Past Due"),
            ("grace", "Grace"),
            ("suspended", "Suspended"),
            ("cancelled", "Cancelled"),
            ("expired", "Expired"),
        ],
        string="Subscription Status",
        compute="_compute_cp_subscription_visibility",
    )
    cp_renewal_date = fields.Date(string="Renewal Date", compute="_compute_cp_subscription_visibility")
    cp_grace_days_remaining = fields.Integer(string="Grace Days Remaining", compute="_compute_cp_subscription_visibility")
    cp_quota_usage_summary = fields.Char(string="Quota Usage", compute="_compute_cp_subscription_visibility")
    cp_subscription_health = fields.Selection(
        [
            ("healthy", "Healthy"),
            ("watch", "Watch"),
            ("risk", "Risk"),
            ("suspended", "Suspended"),
            ("none", "No Subscription"),
        ],
        compute="_compute_cp_subscription_visibility",
    )

    def _current_subscription(self):
        self.ensure_one()
        return self.env["mumtaz.subscription"].sudo().search(
            [
                ("tenant_id", "=", self.id),
                ("is_current", "=", True),
            ],
            order="id desc",
            limit=1,
        )

    def action_open_tenant_subscription(self):
        self.ensure_one()
        action = self.env.ref("mumtaz_control_plane.action_mumtaz_subscription").read()[0]
        action["domain"] = [("tenant_id", "=", self.id)]
        action["context"] = {"default_tenant_id": self.id}
        return action

    def action_quick_reactivate_subscription(self):
        self.ensure_one()
        subscription = self._current_subscription()
        if subscription:
            subscription.action_reactivate_subscription()
        return True

    def action_quick_extend_grace(self):
        self.ensure_one()
        subscription = self._current_subscription()
        if subscription:
            subscription.action_extend_grace()
        return True

    @api.depends("state")
    def _compute_cp_subscription_visibility(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.cp_plan_name = False
            rec.cp_subscription_status = False
            rec.cp_renewal_date = False
            rec.cp_grace_days_remaining = 0
            rec.cp_quota_usage_summary = "No quota telemetry"
            rec.cp_subscription_health = "none"

            if "mumtaz.subscription" not in self.env:
                continue

            subscription = rec._current_subscription()
            if not subscription:
                continue

            rec.cp_plan_name = subscription.plan_id.name
            rec.cp_subscription_status = subscription.status
            rec.cp_renewal_date = subscription.renewal_date
            if subscription.grace_until:
                rec.cp_grace_days_remaining = (subscription.grace_until - today).days

            usage_rows = self.env["mumtaz.usage.metric"].sudo().search(
                [
                    ("tenant_id", "=", rec.id),
                    ("period_start", "<=", today),
                    ("period_end", ">=", today),
                    ("value_limit", ">", 0),
                ]
            )
            if usage_rows:
                peak = max(usage_rows.mapped("utilization_pct") or [0.0])
                rec.cp_quota_usage_summary = f"Peak utilization {peak:.1f}%"

            if subscription.status == "suspended":
                rec.cp_subscription_health = "suspended"
            elif subscription.status in ("past_due", "grace"):
                rec.cp_subscription_health = "risk"
            elif subscription.status == "trial":
                rec.cp_subscription_health = "watch"
            else:
                rec.cp_subscription_health = "healthy"
