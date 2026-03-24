from odoo import fields, models


class MumtazModuleBundle(models.Model):
    """Defines a named set of Odoo modules to install in a tenant database."""

    _name = "mumtaz.module.bundle"
    _description = "Mumtaz Module Bundle"
    _rec_name = "name"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(
        required=True,
        help="Short technical code used to identify this bundle (e.g. 'starter', 'finance').",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()

    # Module lists — space or comma-separated Odoo module technical names.
    # Stored as Text; the provisioning service splits them at runtime.
    base_modules = fields.Text(
        string="Base Modules",
        help="Comma-separated Odoo module names always installed for this bundle.",
    )
    optional_modules = fields.Text(
        string="Optional Modules",
        help="Comma-separated Odoo module names that can be toggled per tenant.",
    )

    # Pricing / tier metadata
    monthly_price = fields.Float(string="Monthly Price (USD)", digits=(10, 2))
    max_users = fields.Integer(
        string="Max Users",
        default=0,
        help="0 = unlimited.",
    )

    tenant_ids = fields.One2many(
        "mumtaz.tenant", "bundle_id", string="Tenants on this Bundle"
    )
    tenant_count = fields.Integer(
        compute="_compute_tenant_count", store=True
    )

    def _compute_tenant_count(self):
        for rec in self:
            rec.tenant_count = len(rec.tenant_ids)

    def get_base_module_list(self):
        """Return base_modules as a cleaned Python list."""
        self.ensure_one()
        if not self.base_modules:
            return []
        return [m.strip() for m in self.base_modules.replace(",", " ").split() if m.strip()]

    def get_optional_module_list(self):
        """Return optional_modules as a cleaned Python list."""
        self.ensure_one()
        if not self.optional_modules:
            return []
        return [m.strip() for m in self.optional_modules.replace(",", " ").split() if m.strip()]

    _sql_constraints = [
        ("mumtaz_bundle_code_unique", "unique(code)", "Bundle code must be unique."),
    ]
