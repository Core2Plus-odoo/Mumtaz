from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    wht_purchase_tax_id = fields.Many2one(
        "c2p.wht.tax", string="Purchase WHT",
        domain="[('transaction_type', '=', 'purchase')]",
        help="Withholding tax we deduct when paying this vendor. "
             "Suggested automatically on the payment screen.")
    wht_sale_tax_id = fields.Many2one(
        "c2p.wht.tax", string="Sales WHT",
        domain="[('transaction_type', '=', 'sale')]",
        help="Withholding tax this customer deducts from our receipts. "
             "Suggested automatically on the receipt screen.")

    # Rate + ledger surfaced from the selected code so the whole withholding
    # setup can be completed here on the vendor/customer form.
    wht_purchase_rate = fields.Float(
        related="wht_purchase_tax_id.rate", string="Purchase WHT Rate (%)",
        readonly=True)
    wht_purchase_account_id = fields.Many2one(
        related="wht_purchase_tax_id.account_id", string="Purchase WHT Account",
        readonly=False,
        help="WHT payable ledger (FBR/SRB). Shared by every partner on this "
             "code; set it once here and it applies to the code.")
    wht_sale_rate = fields.Float(
        related="wht_sale_tax_id.rate", string="Sales WHT Rate (%)",
        readonly=True)
    wht_sale_account_id = fields.Many2one(
        related="wht_sale_tax_id.account_id", string="Sales WHT Account",
        readonly=False,
        help="Advance-tax / WHT receivable ledger. Shared by every partner on "
             "this code; set it once here and it applies to the code.")
