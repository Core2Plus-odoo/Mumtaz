from odoo import fields, models, api
from odoo.exceptions import UserError
from .pharma_tax_rule import TAX_TYPES

CHANNELS = [("shopify", "Shopify"), ("odoo_website", "Odoo Website"), ("b2b", "B2B / Wholesale"),
            ("pos", "POS"), ("partner", "Distribution Partner")]


class PharmaTaxEvent(models.Model):
    """One tax event per (order, channel, settlement, tax type). Immutable; reversed by a new event."""

    _name = "pharma.tax.event"
    _description = "Pharma Tax Event"
    _order = "id desc"

    order_ref = fields.Char(required=True, readonly=True, index=True)
    channel = fields.Selection(CHANNELS, required=True, readonly=True)
    settlement_ref = fields.Char(required=True, readonly=True)
    tax_type = fields.Selection(TAX_TYPES, required=True, readonly=True)
    kind = fields.Selection([("original", "Original"), ("reversal", "Reversal")],
                            default="original", required=True, readonly=True)
    base = fields.Float(digits=(16, 2), readonly=True)
    amount = fields.Float(digits=(16, 2), readonly=True)
    rule_id = fields.Many2one("pharma.tax.rule", readonly=True)
    rule_code = fields.Char(readonly=True)
    rate = fields.Float(digits=(8, 4), readonly=True)
    legal_ref = fields.Char(readonly=True)
    evidence_ref = fields.Char(readonly=True)
    approved_by_name = fields.Char(readonly=True)
    reversal_of = fields.Many2one("pharma.tax.event", readonly=True)
    is_demo = fields.Boolean(string="DEMO", readonly=True)

    _sql_event_unique = models.Constraint(
        "unique(order_ref, channel, settlement_ref, tax_type, kind)",
        "A tax event already exists for this order/channel/settlement/tax type (duplicate withholding prevented).")

    @api.model
    def post_event(self, order_ref, channel, settlement_ref, tax_type, product, on, base):
        res = self.env["pharma.tax.rule"].resolve(product, on, base, tax_type)
        if res["resolution"] != "resolved":
            raise UserError(f"Posting refused ({res['resolution']}): {res['reason']}")
        r = res["rule"]
        return self.sudo().create({
            "order_ref": order_ref, "channel": channel, "settlement_ref": settlement_ref,
            "tax_type": tax_type, "base": base, "amount": res["amount"], "rule_id": r.id,
            "rule_code": r.name, "rate": r.rate, "legal_ref": r.legal_ref,
            "evidence_ref": r.evidence_ref, "approved_by_name": r.approved_by.name,
            "is_demo": r.is_demo})

    def action_reverse(self):
        for ev in self:
            if ev.kind == "reversal":
                raise UserError("A reversal cannot be reversed.")
            self.sudo().create({
                "order_ref": ev.order_ref, "channel": ev.channel, "settlement_ref": ev.settlement_ref,
                "tax_type": ev.tax_type, "kind": "reversal", "base": -ev.base, "amount": -ev.amount,
                "rule_id": ev.rule_id.id, "rule_code": ev.rule_code, "rate": ev.rate,
                "legal_ref": ev.legal_ref, "evidence_ref": ev.evidence_ref,
                "approved_by_name": ev.approved_by_name, "reversal_of": ev.id, "is_demo": ev.is_demo})

    def write(self, vals):
        raise UserError("Tax events are immutable. Use Reverse to correct.")

    def unlink(self):
        raise UserError("Tax events cannot be deleted. Use Reverse to correct.")
