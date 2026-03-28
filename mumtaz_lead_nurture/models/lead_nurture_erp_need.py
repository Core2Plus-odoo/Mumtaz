from odoo import fields, models


class LeadNurtureErpNeed(models.Model):
    """Tag-style model representing a probable Odoo ERP module need."""

    _name = "lead.nurture.erp.need"
    _description = "ERP Module Need"
    _order = "sequence, name"
    _rec_name = "name"

    name = fields.Char(required=True)
    code = fields.Char(help="Short code e.g. INV, ACC, MFG")
    sequence = fields.Integer(default=10)
    description = fields.Char()
    color = fields.Integer()
    active = fields.Boolean(default=True)
