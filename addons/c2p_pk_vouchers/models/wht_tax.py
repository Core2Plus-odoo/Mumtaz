from odoo import api, fields, models


class C2pWhtTax(models.Model):
    _name = "c2p.wht.tax"
    _description = "Withholding Tax Code (Pakistan)"
    _order = "tax_scope, transaction_type, name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company)
    tax_scope = fields.Selection(
        [("income_tax", "Income Tax"), ("sales_tax", "Sales Tax")],
        string="Tax", required=True, default="income_tax")
    transaction_type = fields.Selection(
        [("purchase", "On Payment (we withhold from vendor)"),
         ("sale", "On Receipt (customer withholds from us)")],
        string="Applies To", required=True, default="purchase")
    section_code = fields.Char(
        string="Section / SRO", help="e.g. 153(1)(a) goods, 153(1)(b) services.")
    rate = fields.Float(string="Rate (%)", required=True, digits=(16, 4))
    account_id = fields.Many2one(
        "account.account", string="WHT Account",
        help="Purchase: WHT payable to FBR/SRB (liability). "
             "Sale: advance-tax / WHT receivable (asset). "
             "Set this per your chart of accounts before using the code.")
    note = fields.Char()

    @api.model
    def compute_wht(self, base):
        self.ensure_one()
        return round((base or 0.0) * (self.rate or 0.0) / 100.0, 2)
