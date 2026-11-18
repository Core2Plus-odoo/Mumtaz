from odoo import fields, models


class PharmaPartnerStockLine(models.Model):
    _inherit = "pharma.partner.stock.line"

    from_stock_moves = fields.Boolean(string="From stock moves", readonly=True,
                                      help="Opening, inward, sold, returns and scrap on this line were derived from Odoo stock moves.")
