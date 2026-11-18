from odoo import fields, models
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


def _tax_link_check(env, lines, on):
    """A product line whose approved rule is linked to an Odoo sales tax must carry exactly that tax.

    Opt-in per rule: a rule without a linked tax, or a product that does not resolve to a single approved
    rule, is left to the classification gate above. Nothing is guessed and nothing is corrected here."""
    if env["ir.config_parameter"].sudo().get_param("pharma.tax_gate", "block") != "block":
        return
    Rule = env["pharma.tax.rule"]
    problems = []
    for line in lines:
        res = Rule.resolve(line.product_id, on, line.price_subtotal, "SALES_TAX_OUTPUT")
        rule = res["rule"]
        if res["resolution"] != "resolved" or not rule.account_tax_id:
            continue
        want = rule.account_tax_id
        carried = line.tax_ids.flatten_taxes_hierarchy().filtered(lambda t: t.type_tax_use == "sale")
        if abs(want.amount - rule.rate) > 0.00005:
            problems.append("%s: the Odoo tax '%s' is now %g%% but rule %s says %g%%; fix the tax or issue a new rule."
                            % (line.product_id.display_name, want.name, want.amount, rule.name, rule.rate))
        elif set(carried.ids) != set(want.ids):
            have = ", ".join(carried.mapped("name")) or "no sales tax"
            problems.append("%s: approved rule %s (%g%%) requires the Odoo tax '%s' but the line carries %s."
                            % (line.product_id.display_name, rule.name, rule.rate, want.name, have))
    if problems:
        raise UserError("Blocked: tax on the lines does not match the approved tax rule.\n" + "\n".join(problems))


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        for o in self:
            lines = o.order_line.filtered(lambda l: not l.display_type and l.product_id)
            _gate_check(self.env, lines.product_id)
            _tax_link_check(self.env, lines, (o.date_order or fields.Datetime.now()).date())
        return super().action_confirm()


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        for m in self.filtered(lambda m: m.move_type in ("out_invoice", "out_refund")):
            lines = m.invoice_line_ids.filtered(lambda l: l.display_type == "product" and l.product_id)
            _gate_check(self.env, lines.product_id)
            _tax_link_check(self.env, lines, m.invoice_date or fields.Date.context_today(m))
        return super()._post(soft=soft)
