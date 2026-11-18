from odoo.addons.pharma_courier_cod.tests.common import CourierCase

ACCOUNTS = {  # courier field -> (code, name, account type)
    "acc_clearing_account_id": ("CODT01", "TEST COD clearing", "asset_current"),
    "acc_bank_account_id": ("CODT02", "TEST bank receipts", "asset_current"),
    "acc_freight_account_id": ("CODT03", "TEST freight", "expense"),
    "acc_cod_fee_account_id": ("CODT04", "TEST COD fee", "expense"),
    "acc_wht_income_account_id": ("CODT05", "TEST WHT income tax receivable", "asset_current"),
    "acc_wht_sales_account_id": ("CODT06", "TEST WHT sales tax receivable", "asset_current"),
    "acc_other_account_id": ("CODT07", "TEST other deductions", "expense"),
    "acc_difference_account_id": ("CODT08", "TEST remittance difference", "expense"),
}



class AccountingCase(CourierCase):
    """CourierCase plus the accounts and journal a courier needs, configured on the test courier."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Account = cls.env["account.account"]
        cls.acc = {f: Account.create({"code": code, "name": name, "account_type": typ})
                   for f, (code, name, typ) in ACCOUNTS.items()}
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.env.company.id)], limit=1) or \
            cls.env["account.journal"].create({"name": "TEST misc", "code": "TMSC", "type": "general"})
        cls.courier.write({"acc_journal_id": cls.journal.id, **{f: a.id for f, a in cls.acc.items()}})
        # the test customer needs a receivable account for collection entries (the chart normally provides one)
        if not cls.partner.property_account_receivable_id:
            receivable = Account.search([("account_type", "=", "asset_receivable")], limit=1) or Account.create(
                {"code": "CODT09", "name": "TEST receivable", "account_type": "asset_receivable"})
            cls.partner.property_account_receivable_id = receivable
        cls.receivable = cls.partner.property_account_receivable_id

    def _by_account(self, move):
        """{account code: (debit, credit)} summed, so the tests state what was booked where."""
        out = {}
        for line in move.line_ids:
            d, c = out.get(line.account_id.code, (0.0, 0.0))
            out[line.account_id.code] = (d + line.debit, c + line.credit)
        return out

