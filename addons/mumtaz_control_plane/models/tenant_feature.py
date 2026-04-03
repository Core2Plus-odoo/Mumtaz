from odoo import fields, models


class MumtazTenantFeature(models.Model):
    _name = "mumtaz.tenant.feature"
    _description = "Mumtaz Tenant Feature Override"
    _order = "tenant_id, feature_id"

    tenant_id = fields.Many2one("mumtaz.tenant", required=True, ondelete="cascade", index=True)
    feature_id = fields.Many2one("mumtaz.feature", required=True, ondelete="cascade", index=True)
    override_mode = fields.Selection(
        [
            ("inherit", "Inherit"),
            ("force_on", "Force On"),
            ("force_off", "Force Off"),
            ("quota_override", "Quota Override"),
        ],
        default="inherit",
        required=True,
    )
    override_quota_limit = fields.Float()
    reason = fields.Text()
    effective_from = fields.Datetime()
    effective_to = fields.Datetime()
    granted_by = fields.Many2one("res.users", ondelete="set null")

    _sql_constraints = [
        (
            "mumtaz_tenant_feature_unique",
            "unique(tenant_id, feature_id)",
            "A tenant can only have one override per feature.",
        ),
    ]
