from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    proposal_id = fields.Many2one(
        "mumtaz.proposal",
        string="Proposal",
        copy=False,
        index=True,
    )
