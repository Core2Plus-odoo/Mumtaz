from odoo import api, fields, models

class ResPartner(models.Model):
    _inherit = "res.partner"

    x_mumtaz_code = fields.Char(string="Mumtaz Code")
