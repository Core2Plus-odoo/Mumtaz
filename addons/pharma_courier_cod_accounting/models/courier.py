from odoo import fields, models

# field name -> label shown in the "missing configuration" message
ACCOUNT_FIELDS = {
    "acc_journal_id": "Journal",
    "acc_clearing_account_id": "COD clearing account",
    "acc_bank_account_id": "Bank / receipts account",
    "acc_freight_account_id": "Freight account",
    "acc_cod_fee_account_id": "COD fee account",
    "acc_wht_income_account_id": "Withholding income tax account",
    "acc_wht_sales_account_id": "Withholding sales tax account",
    "acc_other_account_id": "Other deductions account",
    "acc_difference_account_id": "Difference account",
}


class PharmaCourier(models.Model):
    _inherit = "pharma.courier"

    acc_journal_id = fields.Many2one(
        "account.journal", string="Journal", domain=[("type", "=", "general")],
        help="Miscellaneous journal the settlement entry is created in.")
    acc_clearing_account_id = fields.Many2one(
        "account.account", string="COD Clearing Account",
        help="The account customer COD payments are registered against (the courier's journal outstanding / clearing "
             "account). The settlement entry credits it with the gross the courier remitted, clearing what it held.")
    acc_bank_account_id = fields.Many2one(
        "account.account", string="Bank / Receipts Account",
        help="Debited with the amount actually received. Use the bank account, or an outstanding-receipts account if "
             "you reconcile the bank statement against this entry.")
    acc_freight_account_id = fields.Many2one("account.account", string="Freight Account",
                                             help="Expense account for freight deducted on the slip.")
    acc_cod_fee_account_id = fields.Many2one("account.account", string="COD Fee Account",
                                             help="Expense account for the COD handling fee deducted on the slip.")
    acc_wht_income_account_id = fields.Many2one(
        "account.account", string="Withholding Income Tax Account",
        help="Receivable / advance-tax account for income tax the courier withheld at source.")
    acc_wht_sales_account_id = fields.Many2one(
        "account.account", string="Withholding Sales Tax Account",
        help="Receivable account for sales tax the courier withheld at source.")
    acc_other_account_id = fields.Many2one("account.account", string="Other Deductions Account",
                                           help="Where deductions with no better home are booked, so Finance can review them.")
    acc_difference_account_id = fields.Many2one(
        "account.account", string="Difference Account",
        help="Where the difference between what the slip says was paid and what reached the bank is booked. "
             "A difference is never hidden inside another line.")
