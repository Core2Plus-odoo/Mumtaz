from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # --- Purchase side: what WE withhold when paying this vendor ---
    wht_purchase_tax_id = fields.Many2one(
        "c2p.wht.tax", string="Purchase WHT - Income Tax",
        domain="[('transaction_type', '=', 'purchase'), "
               "('tax_scope', '=', 'income_tax')]",
        help="Income-tax withholding we deduct when paying this vendor "
             "(e.g. u/s 153). Suggested automatically on the payment voucher.")
    wht_purchase_stax_id = fields.Many2one(
        "c2p.wht.tax", string="Purchase WHT - Sales Tax",
        domain="[('transaction_type', '=', 'purchase'), "
               "('tax_scope', '=', 'sales_tax')]",
        help="Sales-tax withholding we deduct on the GST portion of this "
             "vendor's bills. Suggested automatically on the payment voucher.")

    # --- Sale side: what the CUSTOMER withholds from our receipts ---
    wht_sale_tax_id = fields.Many2one(
        "c2p.wht.tax", string="Sales WHT - Income Tax",
        domain="[('transaction_type', '=', 'sale'), "
               "('tax_scope', '=', 'income_tax')]",
        help="Income-tax withholding this customer deducts from our receipts. "
             "Suggested automatically on the receipt voucher.")
    wht_sale_stax_id = fields.Many2one(
        "c2p.wht.tax", string="Sales WHT - Sales Tax",
        domain="[('transaction_type', '=', 'sale'), "
               "('tax_scope', '=', 'sales_tax')]",
        help="Sales-tax withholding this customer deducts from our receipts. "
             "Suggested automatically on the receipt voucher.")

    # --- Rate + ledger surfaced from each code so the whole withholding setup
    #     is completed here on the vendor/customer form. ---
    wht_purchase_rate = fields.Float(
        related="wht_purchase_tax_id.rate", string="Income WHT Rate (%)",
        readonly=True)
    wht_purchase_account_id = fields.Many2one(
        related="wht_purchase_tax_id.account_id", string="Income WHT Account",
        readonly=False,
        help="Income-tax WHT payable ledger (FBR). Shared by every partner on "
             "this code; set it once here.")
    wht_purchase_stax_rate = fields.Float(
        related="wht_purchase_stax_id.rate", string="Sales WHT Rate (%)",
        readonly=True)
    wht_purchase_stax_account_id = fields.Many2one(
        related="wht_purchase_stax_id.account_id", string="Sales WHT Account",
        readonly=False,
        help="Sales-tax withholding payable ledger (FBR/SRB). Shared by every "
             "partner on this code; set it once here.")
    wht_sale_rate = fields.Float(
        related="wht_sale_tax_id.rate", string="Cust. Income WHT Rate (%)",
        readonly=True)
    wht_sale_account_id = fields.Many2one(
        related="wht_sale_tax_id.account_id", string="Cust. Income WHT Account",
        readonly=False,
        help="Advance-tax / income-WHT receivable ledger. Shared by every "
             "partner on this code; set it once here.")
    wht_sale_stax_rate = fields.Float(
        related="wht_sale_stax_id.rate", string="Cust. Sales WHT Rate (%)",
        readonly=True)
    wht_sale_stax_account_id = fields.Many2one(
        related="wht_sale_stax_id.account_id", string="Cust. Sales WHT Account",
        readonly=False,
        help="Sales-tax withheld receivable ledger. Shared by every partner on "
             "this code; set it once here.")
