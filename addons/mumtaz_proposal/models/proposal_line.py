from odoo import api, fields, models


class MumtazProposalLine(models.Model):
    _name = "mumtaz.proposal.line"
    _description = "Proposal Line"
    _order = "sequence, id"

    proposal_id = fields.Many2one(
        "mumtaz.proposal",
        string="Proposal",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)
    product_id = fields.Many2one(
        "product.product",
        string="Product",
    )
    name = fields.Text(string="Description", required=True)
    quantity = fields.Float(string="Quantity", default=1.0)
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
    )
    price_unit = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
    )
    discount = fields.Float(
        string="Discount (%)",
        digits=(6, 2),
    )
    tax_ids = fields.Many2many(
        "account.tax",
        string="Taxes",
        domain=[("type_tax_use", "=", "sale")],
    )
    price_subtotal = fields.Monetary(
        string="Subtotal",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    price_tax = fields.Monetary(
        string="Tax Amount",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="proposal_id.currency_id",
        store=True,
        string="Currency",
    )

    # ────────────────────────────────────────────────────────────────────────
    # Compute
    # ────────────────────────────────────────────────────────────────────────

    @api.depends("quantity", "price_unit", "discount", "tax_ids")
    def _compute_amounts(self):
        for line in self:
            subtotal = line.quantity * line.price_unit * (1.0 - line.discount / 100.0)
            if line.tax_ids:
                taxes = line.tax_ids.compute_all(
                    subtotal,
                    currency=line.currency_id,
                    quantity=1.0,
                    product=line.product_id,
                    partner=line.proposal_id.partner_id,
                )
                line.price_subtotal = taxes["total_excluded"]
                line.price_tax = taxes["total_included"] - taxes["total_excluded"]
            else:
                line.price_subtotal = subtotal
                line.price_tax = 0.0

    # ────────────────────────────────────────────────────────────────────────
    # Onchange
    # ────────────────────────────────────────────────────────────────────────

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if not self.product_id:
            return
        product = self.product_id
        self.name = product.description_sale or product.name
        self.price_unit = product.lst_price
        if product.uom_id:
            self.product_uom_id = product.uom_id
        # Default sale taxes from product
        company = self.proposal_id.company_id or self.env.company
        taxes = product.taxes_id.filtered(
            lambda t: t.company_id == company
        )
        self.tax_ids = taxes
