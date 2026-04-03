from datetime import timedelta

from odoo import api, fields, models


class MumtazControlPlaneDashboard(models.TransientModel):
    _name = "mumtaz.control.plane.dashboard"
    _description = "Mumtaz Control Plane Dashboard"

    generated_at = fields.Datetime(default=fields.Datetime.now, readonly=True)

    total_tenant_count = fields.Integer(compute="_compute_kpis", readonly=True)
    active_tenant_count = fields.Integer(compute="_compute_kpis", readonly=True)
    trial_tenant_count = fields.Integer(compute="_compute_kpis", readonly=True)
    suspended_tenant_count = fields.Integer(compute="_compute_kpis", readonly=True)
    renewals_next_30_count = fields.Integer(compute="_compute_kpis", readonly=True)
    overdue_subscription_count = fields.Integer(compute="_compute_kpis", readonly=True)
    grace_subscription_count = fields.Integer(compute="_compute_kpis", readonly=True)
    tenant_override_count = fields.Integer(compute="_compute_kpis", readonly=True)
    tenants_without_active_subscription_count = fields.Integer(compute="_compute_kpis", readonly=True)
    quota_nearing_or_exceeded_tenant_count = fields.Integer(compute="_compute_kpis", readonly=True)
    fail_open_tenant_count = fields.Integer(compute="_compute_kpis", readonly=True)

    @api.model
    def action_open_dashboard(self):
        dashboard = self.create({})
        form_view = self.env.ref("mumtaz_control_plane.view_mumtaz_control_plane_dashboard_form")
        return {
            "type": "ir.actions.act_window",
            "name": "Control Plane Dashboard",
            "res_model": self._name,
            "res_id": dashboard.id,
            "view_mode": "form",
            "views": [(form_view.id, "form")],
            "target": "current",
        }

    def action_refresh_dashboard(self):
        self.ensure_one()
        self.generated_at = fields.Datetime.now()
        return self.action_open_dashboard()

    def _count_unique_tenants(self, model_name, domain):
        groups = self.env[model_name].sudo().read_group(domain, ["tenant_id"], ["tenant_id"], lazy=False)
        return len([group for group in groups if group.get("tenant_id")])

    @api.depends_context("uid")
    def _compute_kpis(self):
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()
        renewal_deadline = today + timedelta(days=30)

        Tenant = self.env["mumtaz.tenant"].sudo()
        Subscription = self.env["mumtaz.subscription"].sudo()
        TenantFeature = self.env["mumtaz.tenant.feature"].sudo()
        UsageMetric = self.env["mumtaz.usage.metric"].sudo()

        active_subscription_domain = [
            ("is_current", "=", True),
            ("status", "in", ["trial", "active", "past_due", "grace"]),
        ]

        renewal_domain = [
            ("is_current", "=", True),
            ("renewal_date", ">=", today),
            ("renewal_date", "<=", renewal_deadline),
            ("status", "in", ["active", "trial", "past_due", "grace"]),
        ]

        overdue_domain = [
            ("is_current", "=", True),
            ("payment_status", "=", "overdue"),
            ("status", "in", ["past_due", "grace", "active"]),
        ]

        grace_domain = [
            ("is_current", "=", True),
            ("status", "=", "grace"),
        ]

        active_override_domain = [
            ("override_mode", "!=", "inherit"),
            "|",
            ("effective_from", "=", False),
            ("effective_from", "<=", now),
            "|",
            ("effective_to", "=", False),
            ("effective_to", ">=", now),
        ]

        current_usage_issue_domain = [
            ("value_limit", ">", 0),
            ("utilization_pct", ">=", 80),
            ("period_start", "<=", today),
            ("period_end", ">=", today),
        ]

        active_subscription_tenant_ids = set(
            Subscription.search(active_subscription_domain).mapped("tenant_id").ids
        )
        tenant_ids = set(Tenant.search([]).ids)

        suspended_tenant_ids = set(Tenant.search([("state", "=", "suspended")]).ids)
        suspended_tenant_ids.update(
            Subscription.search(
                [("is_current", "=", True), ("status", "=", "suspended")]
            ).mapped("tenant_id").ids
        )

        for rec in self:
            rec.total_tenant_count = Tenant.search_count([])
            rec.active_tenant_count = Tenant.search_count([("state", "=", "active"), ("active", "=", True)])
            rec.trial_tenant_count = self._count_unique_tenants(
                "mumtaz.subscription",
                [("is_current", "=", True), ("status", "=", "trial")],
            )
            rec.suspended_tenant_count = len(suspended_tenant_ids)
            rec.renewals_next_30_count = Subscription.search_count(renewal_domain)
            rec.overdue_subscription_count = Subscription.search_count(overdue_domain)
            rec.grace_subscription_count = Subscription.search_count(grace_domain)
            rec.tenant_override_count = self._count_unique_tenants(
                "mumtaz.tenant.feature", active_override_domain
            )
            rec.tenants_without_active_subscription_count = len(tenant_ids - active_subscription_tenant_ids)
            rec.quota_nearing_or_exceeded_tenant_count = self._count_unique_tenants(
                "mumtaz.usage.metric", current_usage_issue_domain
            )
            rec.fail_open_tenant_count = Tenant.search_count([("provision_log", "ilike", "fail-open")])

    def _action_open_subscriptions(self, name, domain):
        action = self.env.ref("mumtaz_control_plane.action_mumtaz_subscription").read()[0]
        action["name"] = name
        action["domain"] = domain
        return action

    def action_open_renewals_due(self):
        today = fields.Date.context_today(self)
        renewal_deadline = today + timedelta(days=30)
        return self._action_open_subscriptions(
            "Renewals in Next 30 Days",
            [
                ("is_current", "=", True),
                ("renewal_date", ">=", today),
                ("renewal_date", "<=", renewal_deadline),
                ("status", "in", ["active", "trial", "past_due", "grace"]),
            ],
        )

    def action_open_overdue_subscriptions(self):
        return self._action_open_subscriptions(
            "Overdue Subscriptions",
            [
                ("is_current", "=", True),
                ("payment_status", "=", "overdue"),
                ("status", "in", ["past_due", "grace", "active"]),
            ],
        )

    def action_open_grace_subscriptions(self):
        return self._action_open_subscriptions(
            "Grace Period Subscriptions",
            [("is_current", "=", True), ("status", "=", "grace")],
        )

    def action_open_tenant_overrides(self):
        now = fields.Datetime.now()
        action = self.env.ref("mumtaz_control_plane.action_mumtaz_tenant_feature").read()[0]
        action["name"] = "Tenants with Active Overrides"
        action["domain"] = [
            ("override_mode", "!=", "inherit"),
            "|",
            ("effective_from", "=", False),
            ("effective_from", "<=", now),
            "|",
            ("effective_to", "=", False),
            ("effective_to", ">=", now),
        ]
        return action

    def action_open_quota_issues(self):
        today = fields.Date.context_today(self)
        action = self.env.ref("mumtaz_control_plane.action_mumtaz_usage_metric").read()[0]
        action["name"] = "Quota Nearing / Exceeded"
        action["domain"] = [
            ("value_limit", ">", 0),
            ("utilization_pct", ">=", 80),
            ("period_start", "<=", today),
            ("period_end", ">=", today),
        ]
        return action
