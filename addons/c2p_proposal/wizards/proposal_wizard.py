from odoo import fields, models
from odoo.exceptions import UserError


class C2pProposalWizard(models.TransientModel):
    _name = "c2p.proposal.wizard"
    _description = "C2P Proposal Maker"

    partner_id = fields.Many2one(
        "res.partner", string="Customer", required=True)
    proposal_title = fields.Char(
        string="Proposal Title", default="Odoo ERP Implementation Proposal")
    industry = fields.Char(string="Client Industry")
    service_ids = fields.Many2many(
        "product.product", string="Services / Modules",
        domain=[("sale_ok", "=", True)],
        help="Tick every service or module this proposal should include.")
    template_id = fields.Many2one(
        "sale.order.template", string="Start from template",
        help="Optionally seed the proposal from a saved quotation template; "
             "ticked services are added on top.")
    validity_days = fields.Integer(string="Valid for (days)", default=30)
    timeline_weeks = fields.Integer(string="Indicative timeline (weeks)", default=12)
    amc_monthly = fields.Monetary(
        string="Monthly AMC", currency_field="currency_id",
        help="Optional post go-live maintenance, billed monthly. Shown as a "
             "separate AMC section on the proposal.")
    currency_id = fields.Many2one(
        "res.currency", string="Currency",
        default=lambda self: self.env.company.currency_id.id)
    exec_summary = fields.Text(string="Executive Summary (optional)")
    pain_points = fields.Text(
        string="Pain points (one per line)",
        help="Leave blank to use a sensible default set.")
    objectives = fields.Text(string="Objectives (one per line)")
    note = fields.Text(string="Notes / scope summary")
    open_pdf = fields.Boolean(
        string="Open proposal PDF immediately", default=True)

    def _order_vals(self, order_lines):
        vals = {
            "partner_id": self.partner_id.id,
            "order_line": order_lines,
            "c2p_is_proposal": True,
            "c2p_proposal_title": self.proposal_title,
            "c2p_industry": self.industry,
            "c2p_timeline_weeks": self.timeline_weeks,
            "c2p_amc_monthly": self.amc_monthly,
            "c2p_exec_summary": self.exec_summary,
            "c2p_pain_points": self.pain_points,
            "c2p_objectives": self.objectives,
        }
        SO = self.env["sale.order"]
        if self.template_id and "sale_order_template_id" in SO._fields:
            vals["sale_order_template_id"] = self.template_id.id
        if self.validity_days and "validity_date" in SO._fields:
            vals["validity_date"] = fields.Date.add(
                fields.Date.today(), days=self.validity_days)
        if self.note and "note" in SO._fields:
            vals["note"] = self.note
        return vals

    def action_generate(self):
        """Create the proposal (a sale.order) and render its branded PDF."""
        self.ensure_one()
        if not self.service_ids and not self.template_id:
            raise UserError(
                "Tick at least one service, or pick a template, to build the proposal.")
        order_lines = [(0, 0, {"product_id": p.id, "product_uom_qty": 1})
                       for p in self.service_ids]
        order = self.env["sale.order"].create(self._order_vals(order_lines))

        if self.open_pdf:
            return self.env.ref(
                "c2p_proposal.action_report_c2p_proposal").report_action(order)
        return {
            "type": "ir.actions.act_window",
            "name": "Proposal",
            "res_model": "sale.order",
            "res_id": order.id,
            "view_mode": "form",
            "target": "current",
        }
