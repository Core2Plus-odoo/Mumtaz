from datetime import date as _date
from decimal import Decimal, ROUND_HALF_UP

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

TAX_TYPES = [
    ("SALES_TAX_OUTPUT", "Sales tax: output"),
    ("SALES_TAX_WITHHOLDING", "Sales tax: withholding"),
    ("INCOME_TAX_153_2A", "Income tax s.153(2A) e-commerce"),
    ("INCOME_TAX_153_1", "Income tax s.153(1) supplier"),
    ("INCOME_TAX_236G", "Income tax s.236G"),
    ("INCOME_TAX_236H", "Income tax s.236H"),
    ("PROVINCIAL_SERVICE_TAX", "Provincial service tax"),
]


class PharmaTaxRule(models.Model):
    _name = "pharma.tax.rule"
    _description = "Pharma Tax Rule (effective-dated, approved-only)"
    _order = "tax_type, tax_class, date_from desc"

    name = fields.Char(string="Rule Code", required=True)
    tax_type = fields.Selection(TAX_TYPES, required=True)
    tax_class = fields.Char(string="Tax Class Key", required=True,
                            help="Matched against the product's approved tax class (set from the adviser opinion).")
    rate = fields.Float(string="Rate %", digits=(8, 4), required=True)
    date_from = fields.Date(string="Effective From", required=True)
    date_to = fields.Date(string="Effective To")
    state = fields.Selection([("draft", "Draft"), ("approved", "Approved"),
                              ("superseded", "Superseded")], default="draft", required=True, readonly=True)
    legal_ref = fields.Char(string="Legal Reference")
    evidence_ref = fields.Char(string="Evidence / Adviser Opinion Ref")
    approved_by = fields.Many2one("res.users", readonly=True)
    approved_on = fields.Datetime(readonly=True)
    is_demo = fields.Boolean(string="DEMO rule (fictional rate)")

    _sql_name_unique = models.Constraint("unique(name)", "Rule code must be unique.")

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for r in self:
            if r.date_to and r.date_to < r.date_from:
                raise ValidationError("Effective To cannot be before Effective From.")

    def write(self, vals):
        if not self.env.context.get("pharma_internal"):
            for r in self:
                if r.state == "approved":
                    allowed = {"date_to"}
                    if set(vals) - allowed:
                        raise UserError(
                            "Approved tax rules are immutable. End-date this rule and create a new one.")
        return super().write(vals)

    def unlink(self):
        if any(r.state != "draft" for r in self):
            raise UserError("Only draft rules can be deleted.")
        return super().unlink()

    def action_approve(self):
        if not self.env.user.has_group("pharma_core.group_pharma_tax_approver"):
            raise UserError("Only a Pharma Tax Approver can approve tax rules.")
        for r in self:
            if r.state != "draft":
                continue
            if not (r.legal_ref and r.evidence_ref):
                raise UserError("Legal reference and evidence reference are required before approval.")
            if r.create_uid == self.env.user:
                raise UserError("Maker-checker: the approver must be different from the creator.")
            r.with_context(pharma_internal=True).write({
                "state": "approved", "approved_by": self.env.user.id,
                "approved_on": fields.Datetime.now()})

    def action_supersede(self):
        if not self.env.user.has_group("pharma_core.group_pharma_tax_approver"):
            raise UserError("Only a Pharma Tax Approver can supersede tax rules.")
        self.with_context(pharma_internal=True).write({"state": "superseded"})

    # ------------------------------------------------------------------ engine
    @api.model
    def _mode(self):
        return self.env["ir.config_parameter"].sudo().get_param("pharma.mode", "production")

    @api.model
    def resolve(self, product, on, base, tax_type="SALES_TAX_OUTPUT"):
        """Return dict(resolution, rule, reason, amount). Never assumes a rate."""
        tmpl = product.product_tmpl_id if product._name == "product.product" else product
        if tmpl.pharma_tax_status != "approved" or not tmpl.pharma_tax_class:
            return {"resolution": "blocked", "rule": self.browse(), "amount": None,
                    "reason": f"{tmpl.display_name}: no approved tax classification (pending adviser evidence)"}
        cands = self.sudo().search([
            ("tax_type", "=", tax_type), ("tax_class", "=", tmpl.pharma_tax_class),
            ("date_from", "<=", on), "|", ("date_to", "=", False), ("date_to", ">=", on)])
        if not cands:
            return {"resolution": "blocked", "rule": self.browse(), "amount": None,
                    "reason": f"No rule for {tax_type} class={tmpl.pharma_tax_class} on {on}"}
        usable, notes = self.browse(), []
        for r in cands:
            if r.state != "approved":
                notes.append(f"rule {r.name} not approved")
            elif not (r.legal_ref and r.evidence_ref and r.approved_by):
                notes.append(f"rule {r.name} missing legal ref / evidence / approver")
            elif r.is_demo and self._mode() != "demo":
                notes.append(f"rule {r.name} is DEMO-only and refused in production")
            else:
                usable |= r
        if not usable:
            return {"resolution": "needs_approval", "rule": self.browse(), "amount": None,
                    "reason": "; ".join(notes)}
        if len(usable) > 1:
            return {"resolution": "blocked", "rule": self.browse(), "amount": None,
                    "reason": "ambiguous: multiple approved rules overlap: " + ", ".join(usable.mapped("name"))}
        amount = (Decimal(str(base)) * Decimal(str(usable.rate)) / Decimal(100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)
        return {"resolution": "resolved", "rule": usable, "reason": "ok", "amount": float(amount)}
