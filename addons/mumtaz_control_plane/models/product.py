from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MumtazProduct(models.Model):
    """What Mumtaz Digital sells: the catalogue the control plane works from.

    A product is a commercial offer (Mumtaz ERP, Jawhar, ZAKI ...). Customer
    deployments (an internal ERP, a client's own instance) are not products
    and do not belong here.
    """

    _name = "mumtaz.product"
    _description = "Mumtaz Product"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    summary = fields.Char()
    category = fields.Selection(
        [
            ("erp", "General ERP"),
            ("edition", "Industry edition"),
            ("ai", "AI"),
            ("marketplace", "Marketplace"),
            ("service", "Operations service"),
        ],
        required=True,
        default="erp",
    )
    status = fields.Selection(
        [
            ("available", "Available"),
            ("pilot", "Pilot"),
            ("planned", "Planned"),
        ],
        required=True,
        default="planned",
        help="Set from evidence, not from how a screen looks.\n"
             "Available: sold, provisioned and supported in production.\n"
             "Pilot: works end to end for selected customers or in staging.\n"
             "Planned: not built, or not safe to expose yet.",
    )
    evidence = fields.Text(
        string="Basis for the Status",
        help="What the status rests on: the test, the deployment or the "
             "review that showed it.",
    )
    delivery_mode = fields.Selection(
        [
            ("odoo_database", "Own Odoo database per customer"),
            ("shared_service", "Shared service"),
            ("embedded", "Inside another product"),
        ],
        required=True,
        default="odoo_database",
    )
    bundle_id = fields.Many2one(
        "mumtaz.module.bundle", string="Install Profile", ondelete="restrict",
        help="The modules installed in a new customer database for this product.",
    )
    access_feature_id = fields.Many2one(
        "mumtaz.feature", string="Access Feature", ondelete="restrict",
        help="The entitlement a subscription must grant before this product "
             "is provisioned or opened.",
    )
    self_service = fields.Boolean(
        string="Open to Registration Requests",
        help="An organization may ask for a staging tenant of this product.",
    )
    plan_ids = fields.One2many("mumtaz.plan", "product_id", string="Plans")

    _sql_code_unique = models.Constraint("unique(code)", "Product code must be unique.")

    @api.constrains("self_service", "status", "delivery_mode", "bundle_id", "access_feature_id")
    def _check_self_service(self):
        for rec in self:
            if not rec.self_service:
                continue
            problems = []
            if rec.status == "planned":
                problems.append(_("its status is Planned"))
            if rec.delivery_mode != "odoo_database":
                problems.append(_("it is not delivered as a customer database"))
            if not rec.bundle_id:
                problems.append(_("it has no install profile"))
            if not rec.access_feature_id:
                problems.append(_("it has no access feature"))
            if problems:
                raise ValidationError(_(
                    "%(product)s cannot be opened to registration requests: %(why)s.",
                    product=rec.name, why="; ".join(problems)))


class MumtazPlanProduct(models.Model):
    _inherit = "mumtaz.plan"

    product_id = fields.Many2one(
        "mumtaz.product", string="Product", ondelete="restrict", index=True,
        help="The product this plan sells. Empty on plans created before the "
             "product catalogue existed.",
    )
    trial_days = fields.Integer(
        default=14,
        help="Length of the trial a registration request starts on this plan.",
    )
