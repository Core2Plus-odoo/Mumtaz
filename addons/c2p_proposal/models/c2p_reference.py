from odoo import fields, models


class C2pOdooModule(models.Model):
    """Catalog of standard Odoo applications the salesperson can tick when an
    ERP implementation is in scope, so the proposal states exactly which apps
    are being configured."""

    _name = "c2p.odoo.module"
    _description = "Odoo Application (proposal scope)"
    _order = "sequence, name"

    name = fields.Char(required=True)
    category = fields.Selection(
        [("sales", "Sales & CRM"),
         ("finance", "Finance"),
         ("supply", "Supply Chain & Manufacturing"),
         ("services", "Services & Operations"),
         ("hr", "Human Resources"),
         ("website", "Website & eCommerce"),
         ("marketing", "Marketing"),
         ("productivity", "Productivity")],
        string="Area", required=True, default="sales")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class C2pIntegration(models.Model):
    """Common third-party / external integrations offered as tick-boxes on the
    proposal so scope and effort reflect them."""

    _name = "c2p.integration"
    _description = "Integration (proposal scope)"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
