from odoo import fields, models


class MumtazPlan(models.Model):
    _name = "mumtaz.plan"
    _description = "Mumtaz Commercial Plan"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    billing_cycle_default = fields.Selection(
        [
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("yearly", "Yearly"),
        ],
        default="monthly",
        required=True,
    )
    list_price = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
        ondelete="restrict",
    )
    grace_days_default = fields.Integer(default=0)
    legacy_bundle_id = fields.Many2one(
        "mumtaz.module.bundle",
        string="Legacy Module Bundle",
        ondelete="set null",
    )
    notes = fields.Text()

    plan_feature_ids = fields.One2many("mumtaz.plan.feature", "plan_id", string="Plan Features")
    subscription_ids = fields.One2many("mumtaz.subscription", "plan_id", string="Subscriptions")

    _sql_constraints = [
        ("mumtaz_plan_code_unique", "unique(code)", "Plan code must be unique."),
    ]


class MumtazPlanFeature(models.Model):
    _name = "mumtaz.plan.feature"
    _description = "Mumtaz Plan Feature"
    _order = "plan_id, feature_id"

    plan_id = fields.Many2one("mumtaz.plan", required=True, ondelete="cascade", index=True)
    feature_id = fields.Many2one("mumtaz.feature", required=True, ondelete="cascade", index=True)
    enabled = fields.Boolean(default=True)
    quota_limit = fields.Float()
    limit_period = fields.Selection(
        [
            ("day", "Day"),
            ("month", "Month"),
            ("year", "Year"),
            ("lifetime", "Lifetime"),
        ],
        default="month",
    )
    source = fields.Selection(
        [
            ("plan", "Plan"),
        ],
        default="plan",
        required=True,
    )

    _sql_constraints = [
        (
            "mumtaz_plan_feature_unique",
            "unique(plan_id, feature_id)",
            "Each plan/feature pair must be unique.",
        ),
    ]
