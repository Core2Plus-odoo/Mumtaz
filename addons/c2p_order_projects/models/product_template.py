from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    c2p_delivery_template_id = fields.Many2one(
        "project.project", string="Delivery Project Template",
        domain="[('is_template', '=', True)]", copy=True,
        help="Template for the delivery project created when an order with "
             "this product is confirmed. Empty: the default template from "
             "the system parameters is used.")
