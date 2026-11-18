from odoo import api, fields, models
from odoo.exceptions import UserError

CLASS_FIELDS = {"pharma_tax_class", "pharma_hs_code", "pharma_drap_ref", "pharma_tax_evidence_ref"}


class ProductTemplate(models.Model):
    _inherit = "product.template"

    pharma_tax_status = fields.Selection(
        [("pending_evidence", "Pending evidence"), ("approved", "Approved")],
        string="Tax Classification", default="pending_evidence", required=True, readonly=True, copy=False)
    pharma_tax_class = fields.Char(string="Tax Class Key", copy=False,
                                   help="From the documented, product-specific adviser opinion. Never guessed.")
    pharma_hs_code = fields.Char(string="HS / PCT Code", copy=False,
                                 help="Only from approved evidence. Never invented.")
    pharma_drap_ref = fields.Char(string="DRAP Registration Ref", copy=False)
    pharma_tax_evidence_ref = fields.Char(string="Tax Opinion / Evidence Ref", copy=False)
    pharma_tax_proposed_by = fields.Many2one("res.users", string="Classification Proposed By",
                                             readonly=True, copy=False)
    pharma_tax_approved_by = fields.Many2one("res.users", string="Classification Approved By",
                                             readonly=True, copy=False)

    def write(self, vals):
        if CLASS_FIELDS & set(vals) and not self.env.context.get("pharma_internal"):
            vals = dict(vals, pharma_tax_status="pending_evidence",
                        pharma_tax_proposed_by=self.env.user.id, pharma_tax_approved_by=False)
        return super().write(vals)

    def action_pharma_approve_tax_class(self):
        if not self.env.user.has_group("pharma_core.group_pharma_tax_approver"):
            raise UserError("Only a Pharma Tax Approver can approve a tax classification.")
        for p in self:
            if not (p.pharma_tax_class and p.pharma_tax_evidence_ref):
                raise UserError(f"{p.display_name}: tax class and evidence reference are required.")
            if p.pharma_tax_proposed_by == self.env.user:
                raise UserError("Maker-checker: the approver must be different from the proposer.")
            p.with_context(pharma_internal=True).write({
                "pharma_tax_status": "approved", "pharma_tax_approved_by": self.env.user.id})
