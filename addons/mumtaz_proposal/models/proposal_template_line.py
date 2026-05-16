from odoo import fields, models


class MumtazProposalTemplateLine(models.Model):
    _name = "mumtaz.proposal.template.line"
    _description = "Proposal Template Line"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "mumtaz.proposal.template",
        string="Template",
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
    price_unit = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
    discount = fields.Float(string="Discount (%)", digits=(6, 2))
