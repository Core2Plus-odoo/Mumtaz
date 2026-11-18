from odoo import models
from odoo.exceptions import UserError


def _gate_check(env, products):
    if env["ir.config_parameter"].sudo().get_param("pharma.tax_gate", "block") != "block":
        return
    bad = products.filtered(lambda p: p.product_tmpl_id.pharma_tax_status != "approved")
    if bad:
        raise UserError(
            "Blocked: no approved tax classification for: %s.\n"
            "Record the documented product-specific tax opinion and approve the classification first."
            % ", ".join(sorted(set(bad.mapped("display_name")))))


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        for o in self:
            _gate_check(self.env, o.order_line.filtered(lambda l: not l.display_type).product_id)
        return super().action_confirm()


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        for m in self.filtered(lambda m: m.move_type in ("out_invoice", "out_refund")):
            _gate_check(self.env, m.invoice_line_ids.filtered(lambda l: l.display_type == "product").product_id)
        return super()._post(soft=soft)
