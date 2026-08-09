from odoo import api, fields, models


class ResCompany(models.Model):
    """Revenue policy lives on the company, not in code.

    The 5% platform fee and 10% vendor commission are commercial decisions that
    will change. Putting them here means ops adjusts them in Settings rather than
    waiting on a release — and every historical order keeps the figure it was
    actually computed with, because order amounts are stored.
    """

    _inherit = "res.company"

    faizy_platform_fee_rate = fields.Float(
        string="Platform Fee Rate",
        default=0.05,
        digits=(3, 4),
        help="Added to the customer invoice as a share of purchase value.",
    )
    faizy_vendor_commission_rate = fields.Float(
        string="Vendor Commission Rate",
        default=0.10,
        digits=(3, 4),
        help="Retained from the vendor on vendor-fulfilled orders.",
    )
    faizy_free_activity_grant = fields.Integer(
        string="Free Activities on Signup",
        default=3,
        help="Care activities a new customer gets before the paywall.",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    faizy_platform_fee_rate = fields.Float(
        related="company_id.faizy_platform_fee_rate", readonly=False
    )
    faizy_vendor_commission_rate = fields.Float(
        related="company_id.faizy_vendor_commission_rate", readonly=False
    )
    faizy_free_activity_grant = fields.Integer(
        related="company_id.faizy_free_activity_grant", readonly=False
    )


class ResPartner(models.Model):
    """Faizy customer data on the standard contact record.

    Extending res.partner rather than inventing a parallel customer model means
    invoicing, messaging and the portal all work without translation layers.
    """

    _inherit = "res.partner"

    # Marks records created by the sample-data loader so they can all be
    # removed together without touching anything real.
    is_sample = fields.Boolean(default=False, copy=False, index=True)

    is_faizy_customer = fields.Boolean(string="Faizy Customer", index=True)

    family_member_ids = fields.One2many("faizy.family.member", "partner_id")
    family_member_count = fields.Integer(compute="_compute_faizy_counts")

    subscription_ids = fields.One2many("faizy.subscription", "partner_id")
    faizy_subscription_id = fields.Many2one(
        "faizy.subscription",
        string="Current Subscription",
        compute="_compute_faizy_subscription",
        store=True,
        help="The one live subscription, if any.",
    )
    faizy_plan_id = fields.Many2one(
        related="faizy_subscription_id.plan_id", string="Plan", store=True
    )

    # The signup grant. Server-maintained: readonly in the UI and only written
    # by the metering code, because a customer who could edit this bills nothing.
    faizy_free_activities = fields.Integer(
        string="Free Activities Left",
        default=lambda self: self.env.company.faizy_free_activity_grant,
        readonly=True,
        copy=False,
    )

    order_ids = fields.One2many("faizy.order", "partner_id")
    faizy_order_count = fields.Integer(compute="_compute_faizy_counts")

    wallet_balance = fields.Monetary(
        compute="_compute_wallet_balance", currency_field="currency_id"
    )

    # Segmentation for the ops CRM. Derived, so it cannot drift from reality.
    faizy_segment = fields.Selection(
        [
            ("new", "New"),
            ("free_trial", "Free Trial"),
            ("regular", "Regular"),
            ("high_value", "High Value"),
            ("vip", "VIP"),
            ("at_risk", "At Risk"),
        ],
        compute="_compute_faizy_segment",
        store=True,
        index=True,
    )

    @api.depends("family_member_ids", "order_ids")
    def _compute_faizy_counts(self):
        for partner in self:
            partner.family_member_count = len(partner.family_member_ids)
            partner.faizy_order_count = len(partner.order_ids)

    @api.depends("subscription_ids.state")
    def _compute_faizy_subscription(self):
        for partner in self:
            partner.faizy_subscription_id = partner.subscription_ids.filtered(
                lambda s: s.state in ("trial", "active", "past_due", "paused")
            )[:1]

    @api.depends("is_faizy_customer")
    def _compute_wallet_balance(self):
        # Summed from the ledger rather than stored — a stored balance and a
        # ledger eventually disagree, and then neither can be trusted.
        data = self.env["faizy.wallet.transaction"]._read_group(
            [("partner_id", "in", self.ids)],
            groupby=["partner_id"],
            aggregates=["amount:sum"],
        )
        balances = {partner.id: total for partner, total in data}
        for partner in self:
            partner.wallet_balance = balances.get(partner.id, 0.0)

    @api.depends(
        "faizy_subscription_id.state",
        "faizy_subscription_id.plan_id",
        "order_ids.state",
        "order_ids.date_completed",
        "order_ids.amount_total",
    )
    def _compute_faizy_segment(self):
        today = fields.Date.context_today(self)
        for partner in self:
            subscription = partner.faizy_subscription_id
            completed = partner.order_ids.filtered(lambda o: o.state == "completed")

            if not subscription and not completed:
                partner.faizy_segment = "new"
                continue
            if not subscription:
                partner.faizy_segment = "free_trial"
                continue

            last = max(
                (o.date_completed for o in completed if o.date_completed), default=None
            )
            days_quiet = (today - last.date()).days if last else 999

            # The prototype's thresholds, kept exactly so ops sees the same
            # segments here as in the app they already know:
            #   >=15 orders or Family Pro -> VIP
            #   >=500 AED lifetime spend  -> High Value
            #   quiet 30+ days with history -> At Risk
            #   joined <30 days, <4 orders  -> New
            total_spend = sum(completed.mapped("amount_total"))
            days_since_joined = (
                (today - partner.create_date.date()).days if partner.create_date else 999
            )

            if len(partner.order_ids) >= 15 or subscription.plan_id.code == "family_pro":
                partner.faizy_segment = "vip"
            elif total_spend >= 500:
                partner.faizy_segment = "high_value"
            elif days_quiet > 30 and partner.order_ids:
                partner.faizy_segment = "at_risk"
            elif days_since_joined < 30 and len(partner.order_ids) < 4:
                partner.faizy_segment = "new"
            else:
                partner.faizy_segment = "regular"

    # ── Care score ───────────────────────────────────────────────────────
    care_score = fields.Integer(
        compute="_compute_care_score",
        store=True,
        help="How well this family is actually being looked after, 0-100.",
    )
    care_score_label = fields.Char(compute="_compute_care_score", store=True)

    document_ids = fields.One2many("faizy.document", "partner_id")

    @api.depends(
        "family_member_ids",
        "order_ids.state",
        "order_ids.date_completed",
        "document_ids",
        "faizy_subscription_id.state",
    )
    def _compute_care_score(self):
        """A heuristic, and worth being honest that it is one.

        It answers "is this family actually being looked after, or is the
        subscription just sitting there?" — which is the question that predicts
        churn. Four things, weighted by how much each one tells us:

          40  recency: someone was cared for lately
          25  coverage: the family is actually on the system
          20  consistency: care happens regularly, not once
          15  readiness: documents on file, so an errand can start immediately

        Deliberately not a rating of the customer. A low score is a prompt for
        ops to reach out, not a judgement.
        """
        today = fields.Date.context_today(self)
        for partner in self:
            if not partner.is_faizy_customer:
                partner.care_score = 0
                partner.care_score_label = ""
                continue

            completed = partner.order_ids.filtered(lambda o: o.state == "completed")

            # Recency — full marks within a fortnight, nothing past ten weeks.
            last = max((o.date_completed for o in completed if o.date_completed), default=None)
            if last:
                days = (today - last.date()).days
                recency = 40 if days <= 14 else max(0, 40 - (days - 14))
            else:
                recency = 0

            # Coverage — a subscription with nobody attached to it helps no one.
            coverage = min(25, len(partner.family_member_ids) * 12)

            # Consistency — five completed tasks is a settled habit.
            consistency = min(20, len(completed) * 4)

            # Readiness — paperwork on file means an errand can start same-day.
            readiness = min(15, len(partner.document_ids) * 5)

            score = int(recency + coverage + consistency + readiness)
            partner.care_score = score
            partner.care_score_label = (
                self.env._("Well cared for") if score >= 75
                else self.env._("Steady") if score >= 50
                else self.env._("Slipping") if score >= 25
                else self.env._("Needs attention")
            )

    def action_view_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Documents"),
            "res_model": "faizy.document",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }

    def action_view_family_members(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Family"),
            "res_model": "faizy.family.member",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }

    def action_view_faizy_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Orders"),
            "res_model": "faizy.order",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }
