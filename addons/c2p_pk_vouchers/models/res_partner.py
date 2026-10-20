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
