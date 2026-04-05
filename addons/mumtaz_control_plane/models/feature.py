from odoo import fields, models


class MumtazFeature(models.Model):
    _name = "mumtaz.feature"
    _description = "Mumtaz Feature Registry"
    _order = "product_area, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)

    product_area = fields.Selection(
        [
            ("erp", "ERP"),
            ("ai", "AI"),
            ("marketplace", "Marketplace"),
            ("api", "API"),
            ("branding", "Branding"),
            ("platform", "Platform"),
        ],
        default="platform",
        required=True,
    )
    feature_type = fields.Selection(
        [
            ("toggle", "Toggle"),
            ("quota", "Quota"),
        ],
        default="toggle",
        required=True,
    )
    description = fields.Text()
    odoo_module_name = fields.Char()
    metric_code_default = fields.Char()
    is_customer_visible = fields.Boolean(default=True)

    plan_feature_ids = fields.One2many("mumtaz.plan.feature", "feature_id", string="Plan Features")
    tenant_feature_ids = fields.One2many("mumtaz.tenant.feature", "feature_id", string="Tenant Overrides")

    _sql_constraints = [
        ("mumtaz_feature_code_unique", "unique(code)", "Feature code must be unique."),
    ]
