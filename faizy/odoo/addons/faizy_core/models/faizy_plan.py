from odoo import api, fields, models


class FaizyPlan(models.Model):
    """A subscription tier.

    Odoo Community has no Subscriptions app — `sale_subscription` is Enterprise
    — so the recurring model is built here rather than inherited. A plan is the
    template: price, how many care activities it includes per month, and what an
    extra one costs.
    """

    _name = "faizy.plan"
    _description = "Faizy Subscription Plan"
    _order = "sequence, price"

    name = fields.Char(required=True, translate=True)
    code = fields.Selection(
        [
            ("lite", "Lite"),
            ("standard", "Standard"),
            ("family_pro", "Family Pro"),
        ],
        required=True,
        index=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    price = fields.Monetary(
        required=True,
        currency_field="currency_id",
        help="Recurring price per month.",
    )

    # ── Activity allowance ────────────────────────────────────────────────
    # Real figures, from the customer app prototype: 10 / 30 / 60 activities and
    # PKR 300 / 250 / 200 per extra. These are no longer placeholders.
    activities_included = fields.Integer(
        required=True,
        default=10,
        help="Care activities included each billing period.",
    )
    overage_price = fields.Monetary(
        currency_field="currency_id",
        help="Charged per activity once the monthly allowance is spent, in the "
        "company currency.",
    )
    overage_price_pkr = fields.Float(
        string="Extra Activity (PKR)",
        help="The rate the customer app quotes. PKR is the source of truth "
        "because that is where the work is done and priced.",
    )

    max_family_members = fields.Integer(
        default=0,
        help="0 means unlimited.",
    )
    description = fields.Text(translate=True)
    feature_ids = fields.One2many("faizy.plan.feature", "plan_id", string="Features")

    # Product used on the invoice line for the recurring charge. Keeping the
    # accounting side on a real product means tax and account mapping behave
    # exactly as they do everywhere else in Odoo.
    product_id = fields.Many2one(
        "product.product",
        string="Subscription Product",
        domain=[("type", "=", "service")],
        help="Invoice line product for the recurring charge.",
    )
    overage_product_id = fields.Many2one(
        "product.product",
        string="Overage Product",
        domain=[("type", "=", "service")],
        help="Invoice line product used for per-activity overage.",
    )

    subscription_ids = fields.One2many("faizy.subscription", "plan_id")
    subscription_count = fields.Integer(compute="_compute_subscription_count")
    mrr = fields.Monetary(
        string="MRR",
        compute="_compute_subscription_count",
        currency_field="currency_id",
        help="Monthly recurring revenue from active subscriptions on this plan.",
    )

    _sql_code_unique = models.Constraint(
        "unique(code)", "Each plan code may only be used once."
    )

    @api.depends("subscription_ids.state")
    def _compute_subscription_count(self):
        for plan in self:
            live = plan.subscription_ids.filtered(
                lambda s: s.state in ("trial", "active", "past_due")
            )
            plan.subscription_count = len(live)
            plan.mrr = len(live) * plan.price

    def action_view_subscriptions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "faizy.subscription",
            "view_mode": "list,form",
            "domain": [("plan_id", "=", self.id)],
            "context": {"default_plan_id": self.id},
        }


class FaizyPlanFeature(models.Model):
    """A selling point shown on the pricing page. Kept as records rather than a
    text blob so the website can render them as a list and marketing can edit
    them without touching code."""

    _name = "faizy.plan.feature"
    _description = "Faizy Plan Feature"
    _order = "sequence, id"

    plan_id = fields.Many2one("faizy.plan", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, translate=True)
