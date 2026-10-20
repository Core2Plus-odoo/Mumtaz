from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_journal_voucher = fields.Boolean(
        string="Journal Voucher (adjustments only)",
        help="When set, entries in this journal may not contain bank or cash "
             "lines — payments and receipts must go through Payment / Receipt "
             "Vouchers. Typically set on your 'JV' general journal.")
