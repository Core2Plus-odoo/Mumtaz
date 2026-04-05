from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models


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

    last_lifecycle_check_at = fields.Datetime(readonly=True)
    lifecycle_log_ids = fields.One2many(
        "mumtaz.subscription.lifecycle.log", "subscription_id", string="Lifecycle Logs", readonly=True
    )
    lifecycle_log_count = fields.Integer(compute="_compute_lifecycle_log_count")

    grace_days_remaining = fields.Integer(compute="_compute_commercial_health")
    quota_usage_summary = fields.Char(compute="_compute_commercial_health")
    subscription_risk_level = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        compute="_compute_commercial_health",
    )
    recommended_plan_id = fields.Many2one("mumtaz.plan", compute="_compute_recommended_plan")
    recommended_plan_note = fields.Char(compute="_compute_recommended_plan")

    def name_get(self):
        result = []
        for rec in self:
            label = f"{rec.tenant_id.name} - {rec.plan_id.name}"
            result.append((rec.id, label))
        return result

    @api.depends("lifecycle_log_ids")
    def _compute_lifecycle_log_count(self):
        counts = self.env["mumtaz.subscription.lifecycle.log"].read_group(
            [("subscription_id", "in", self.ids)], ["subscription_id"], ["subscription_id"], lazy=False
        )
        mapped = {item["subscription_id"][0]: item["subscription_id_count"] for item in counts}
        for rec in self:
            rec.lifecycle_log_count = mapped.get(rec.id, 0)

    def _compute_commercial_health(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.status == "suspended":
                rec.subscription_risk_level = "high"
            elif rec.status in ("grace", "past_due"):
                rec.subscription_risk_level = "high"
            elif rec.status == "trial":
                rec.subscription_risk_level = "medium"
            else:
                rec.subscription_risk_level = "low"

            if rec.grace_until:
                rec.grace_days_remaining = (rec.grace_until - today).days
            else:
                rec.grace_days_remaining = 0

            usage_rows = self.env["mumtaz.usage.metric"].sudo().search(
                [
                    ("tenant_id", "=", rec.tenant_id.id),
                    ("period_start", "<=", today),
                    ("period_end", ">=", today),
                    ("value_limit", ">", 0),
                ]
            )
            if not usage_rows:
                rec.quota_usage_summary = "No quota telemetry"
                continue

            peak = max(usage_rows.mapped("utilization_pct") or [0.0])
            rec.quota_usage_summary = f"Peak utilization {peak:.1f}%"

    def _compute_recommended_plan(self):
        for rec in self:
            rec.recommended_plan_id = False
            rec.recommended_plan_note = False
            candidate_plans = self.env["mumtaz.plan"].search(
                [
                    ("active", "=", True),
                    ("sequence", ">", rec.plan_id.sequence),
                ],
                order="sequence asc",
            )
            if not candidate_plans:
                continue

            preferred = candidate_plans[0]
            if rec.subscription_risk_level == "high":
                preferred = candidate_plans[:1]
            rec.recommended_plan_id = preferred.id
            rec.recommended_plan_note = _(
                "Recommended upgrade path based on current risk/quota profile."
            )

    def _apply_tenant_impact(self, to_status, tenant_impact_mode):
        self.ensure_one()
        tenant = self.tenant_id.sudo()
        if not tenant:
            return "none"

        if to_status == "suspended":
            if tenant_impact_mode == "enforce" and tenant.state != "suspended":
                tenant.action_suspend()
                return "suspend"
            if tenant_impact_mode == "warn":
                tenant.message_post(
                    body=_(
                        "Subscription %(sub)s is suspended. Tenant suspension is recommended by policy.",
                        sub=self.display_name,
                    )
                )
                return "warn_suspend"

        if to_status == "active":
            if tenant_impact_mode == "enforce" and tenant.state == "suspended":
                tenant.action_mark_active()
                return "reactivate"
            if tenant_impact_mode == "warn" and tenant.state == "suspended":
                tenant.message_post(
                    body=_(
                        "Subscription %(sub)s reactivated. Tenant can be reactivated based on policy.",
                        sub=self.display_name,
                    )
                )
                return "warn_reactivate"

        return "none"

    def _create_lifecycle_log(self, from_status, decision, policy, source, applied, tenant_action="none"):
        self.ensure_one()
        self.env["mumtaz.subscription.lifecycle.log"].sudo().create(
            {
                "subscription_id": self.id,
                "tenant_id": self.tenant_id.id,
                "from_status": from_status,
                "to_status": decision["to_status"],
                "reason": decision["reason"],
                "policy_mode": policy["subscription_enforcement_mode"],
                "tenant_impact_mode": policy["tenant_impact_mode"],
                "tenant_action": tenant_action,
                "applied": applied,
                "source": source,
            }
        )

    def _apply_transition_decision(self, decision, policy, source):
        self.ensure_one()
        from_status = self.status
        applied = False
        tenant_action = "none"

        if policy["subscription_enforcement_mode"] == "enforce":
            vals = {"status": decision["to_status"], "last_lifecycle_check_at": fields.Datetime.now()}

            if decision.get("set_grace_until"):
                vals["grace_until"] = decision["set_grace_until"]
            if decision.get("clear_grace_until"):
                vals["grace_until"] = False
            if decision.get("set_is_current") is not None:
                vals["is_current"] = decision["set_is_current"]

            self.write(vals)
            tenant_action = self._apply_tenant_impact(decision["to_status"], policy["tenant_impact_mode"])
            applied = True
        else:
            self.write({"last_lifecycle_check_at": fields.Datetime.now()})

        self._create_lifecycle_log(
            from_status=from_status,
            decision=decision,
            policy=policy,
            source=source,
            applied=applied,
            tenant_action=tenant_action,
        )
        self.env["mumtaz.subscription.notification.service"].notify_transition(
            self, from_status, decision["to_status"], source=source
        )

    def action_open_lifecycle_logs(self):
        self.ensure_one()
        action = self.env.ref("mumtaz_control_plane.action_mumtaz_subscription_lifecycle_log").read()[0]
        action["domain"] = [("subscription_id", "=", self.id)]
        action["context"] = {"default_subscription_id": self.id}
        return action

    def action_open_upgrade_plans(self):
        self.ensure_one()
        action = self.env.ref("mumtaz_control_plane.action_mumtaz_plan_comparison").read()[0]
        action["domain"] = [("active", "=", True), ("sequence", ">=", self.plan_id.sequence)]
        action["context"] = {
            "current_plan_id": self.plan_id.id,
            "default_subscription_id": self.id,
        }
        return action

    def action_request_renewal(self):
        Operation = self.env["mumtaz.commercial.operation"]
        for rec in self:
            op = Operation.create(
                {
                    "operation_type": "renewal",
                    "tenant_id": rec.tenant_id.id,
                    "subscription_id": rec.id,
                    "status": "requested",
                    "commercial_notes": _("Renewal requested from subscription CTA."),
                }
            )
            rec.tenant_id.message_post(body=_("Renewal request %(op)s created for %(sub)s.", op=op.name, sub=rec.display_name))
            self.env["mumtaz.subscription.notification.service"].notify_event(rec, "renewal_requested", source="manual")
        return True

    def action_request_reactivation(self):
        Operation = self.env["mumtaz.commercial.operation"]
        for rec in self:
            op = Operation.create(
                {
                    "operation_type": "reactivation",
                    "tenant_id": rec.tenant_id.id,
                    "subscription_id": rec.id,
                    "status": "requested",
                    "commercial_notes": _("Reactivation requested from subscription CTA."),
                }
            )
            rec.tenant_id.message_post(body=_("Reactivation request %(op)s created for %(sub)s.", op=op.name, sub=rec.display_name))
        return True

    def action_request_grace_extension(self):
        Operation = self.env["mumtaz.commercial.operation"]
        for rec in self:
            op = Operation.create(
                {
                    "operation_type": "grace_extension",
                    "tenant_id": rec.tenant_id.id,
                    "subscription_id": rec.id,
                    "status": "requested",
                    "grace_days_requested": 3,
                    "commercial_notes": _("Grace extension requested from subscription CTA."),
                }
            )
            rec.tenant_id.message_post(body=_("Grace extension request %(op)s created for %(sub)s.", op=op.name, sub=rec.display_name))
        return True

    def action_open_commercial_operations(self):
        self.ensure_one()
        action = self.env.ref("mumtaz_control_plane.action_mumtaz_commercial_operation").read()[0]
        action["domain"] = [("subscription_id", "=", self.id)]
        action["context"] = {"default_subscription_id": self.id, "default_tenant_id": self.tenant_id.id}
        return action

    def action_extend_grace(self):
        for rec in self:
            if rec.status == "grace":
                rec.grace_until = (rec.grace_until or fields.Date.context_today(self)) + relativedelta(days=3)
        return True

    def action_evaluate_lifecycle(self):
        return self.process_lifecycle(source="manual")

    def process_lifecycle(self, as_of_date=None, source="manual"):
        as_of = fields.Date.to_date(as_of_date) or fields.Date.context_today(self)
        policy_service = self.env["mumtaz.subscription.lifecycle.policy"]
        policy = policy_service.get_policy()

        for rec in self:
            decision = policy_service.evaluate_transition(rec, as_of)
            if decision:
                rec._apply_transition_decision(decision, policy, source)
            else:
                rec.write({"last_lifecycle_check_at": fields.Datetime.now()})
        return True

    def action_reactivate_subscription(self):
        for rec in self:
            if rec.status in ("past_due", "grace", "suspended"):
                rec._apply_transition_decision(
                    {
                        "to_status": "active",
                        "reason": "Manual reactivation action executed.",
                        "clear_grace_until": True,
                    },
                    self.env["mumtaz.subscription.lifecycle.policy"].get_policy(),
                    source="manual",
                )
        return True

    def action_cancel_subscription(self):
        for rec in self:
            rec._apply_transition_decision(
                {
                    "to_status": "cancelled",
                    "reason": "Manual cancellation action executed.",
                    "set_is_current": False,
                },
                self.env["mumtaz.subscription.lifecycle.policy"].get_policy(),
                source="manual",
            )
        return True

    @api.model
    def cron_process_lifecycle(self):
        subscriptions = self.search(
            [
                ("status", "in", ["trial", "active", "past_due", "grace", "suspended", "cancelled"]),
            ]
        )
        subscriptions.process_lifecycle(source="cron")
        return True
