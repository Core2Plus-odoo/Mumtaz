from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    pharma_cod_kind = fields.Selection(
        [("collection", "COD collection"), ("settlement", "COD settlement"), ("reversal", "COD reversal")],
        string="COD Entry", copy=False, index=True, readonly=True,
        help="Set when the entry was created by the courier COD process. It is what the accountant's "
             "Entries to Post queue is built from.")
