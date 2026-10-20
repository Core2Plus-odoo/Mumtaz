from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    cheque_no = fields.Char(
        related="move_id.cheque_no", readonly=False,
        string="Cheque / Instrument No.")
    cheque_date = fields.Date(
        related="move_id.cheque_date", readonly=False, string="Cheque Date")
