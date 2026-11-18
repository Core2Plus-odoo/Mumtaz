from odoo import api, fields, models


class PharmaPartnerScenario(models.Model):
    """Gate for the Distribution Partner commercial model. A/B/C is NOT finalized until contract and sign-offs exist."""

    _name = "pharma.partner.scenario"
    _description = "Distribution Partner Scenario Approval"

    name = fields.Char(default="Distribution Partner commercial model", required=True)
    scenario = fields.Selection([("A", "A: Buy-sell"), ("B", "B: Custody / consignment"),
                                 ("C", "C: Agency / hybrid")])
    contract_ref = fields.Char()
    finance_signoff_id = fields.Many2one("res.users")
    tax_signoff_id = fields.Many2one("res.users")
    complete = fields.Boolean(compute="_compute_complete", store=True)

    @api.depends("scenario", "contract_ref", "finance_signoff_id", "tax_signoff_id")
    def _compute_complete(self):
        for r in self:
            r.complete = bool(r.scenario and r.contract_ref and r.finance_signoff_id and r.tax_signoff_id)

    @api.model
    def custody_transfer(self, sku, lot, qty):
        """A physical move to Distribution Partner always records custody; revenue/tax only per an approved scenario."""
        base = {"custody_move": True, "sku": sku, "lot": lot, "qty": qty, "location": "PARTNER_DIST",
                "tax_posted": False}
        ap = self.search([("complete", "=", True)], limit=1)
        if not ap:
            return {**base, "revenue_recognised": False,
                    "status": "BLOCKED_AWAITING_CLIENT: Distribution Partner contract / scenario sign-off pending"}
        if ap.scenario == "A":
            return {**base, "revenue_recognised": "pending_title_transfer_evidence",
                    "status": "approved_scenario_A: recognition only on evidenced title transfer"}
        return {**base, "revenue_recognised": False,
                "status": f"approved_scenario_{ap.scenario}: not a sale; trigger per contract"}


class PharmaPartnerStockLine(models.Model):
    _name = "pharma.partner.stock.line"
    _description = "Distribution Partner Stock Roll-forward"
    _order = "sku, lot"

    run_id = fields.Many2one("pharma.recon.run", ondelete="cascade", index=True)
    sku = fields.Char(required=True)
    lot = fields.Char(required=True)
    location = fields.Char(required=True)
    opening = fields.Integer()
    inward_accepted = fields.Integer()
    adj_positive_approved = fields.Integer()
    sold_or_issued = fields.Integer()
    returned_to_pharma = fields.Integer()
    expired_damaged_documented = fields.Integer()
    adj_negative_approved = fields.Integer()
    expected_closing = fields.Integer(compute="_compute_expected", store=True)
    reported = fields.Integer(string="Reported by Distribution Partner")
    variance = fields.Integer(compute="_compute_expected", store=True)
    is_demo = fields.Boolean(string="DEMO")

    @api.depends("opening", "inward_accepted", "adj_positive_approved", "sold_or_issued",
                 "returned_to_pharma", "expired_damaged_documented", "adj_negative_approved", "reported")
    def _compute_expected(self):
        for r in self:
            r.expected_closing = (r.opening + r.inward_accepted + r.adj_positive_approved - r.sold_or_issued
                                  - r.returned_to_pharma - r.expired_damaged_documented - r.adj_negative_approved)
            r.variance = r.reported - r.expected_closing

    def action_raise_exceptions(self):
        """One exception per variance, unassigned. Nothing is written off."""
        for l in self.filtered(lambda l: l.variance and l.run_id):
            if not self.env["pharma.recon.exception"].search_count(
                    [("run_id", "=", l.run_id.id), ("description", "like", f"{l.sku} / {l.lot}"),
                     ("state", "!=", "closed")]):
                self.env["pharma.recon.exception"].create({
                    "run_id": l.run_id.id, "is_demo": l.is_demo, "amount": l.variance,
                    "description": f"Stock variance {l.sku} / {l.lot} @ {l.location}: expected "
                                   f"{l.expected_closing}, reported {l.reported}"})
