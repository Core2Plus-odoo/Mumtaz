from odoo import fields, models
from odoo.exceptions import UserError


class C2pProposalWizard(models.TransientModel):
    _name = "c2p.proposal.wizard"
    _description = "C2P Proposal Maker"

    partner_id = fields.Many2one(
        "res.partner", string="Customer", required=True)
    service_ids = fields.Many2many(
        "product.product", string="Services / Modules",
        domain=[("sale_ok", "=", True)],
        help="Tick every service or module this proposal should include.")
    validity_days = fields.Integer(string="Valid for (days)", default=30)
    note = fields.Text(string="Notes / Scope summary")

    def action_generate(self):
        """Create a quotation (the proposal) from the ticked services and open it."""
        self.ensure_one()
        if not self.service_ids:
            raise UserError("Tick at least one service to include in the proposal.")
        order_lines = [(0, 0, {"product_id": p.id, "product_uom_qty": 1})
                       for p in self.service_ids]
        vals = {"partner_id": self.partner_id.id, "order_line": order_lines}
        if "validity_date" in self.env["sale.order"]._fields and self.validity_days:
            vals["validity_date"] = fields.Date.add(
                fields.Date.today(), days=self.validity_days)
        if self.note and "note" in self.env["sale.order"]._fields:
            vals["note"] = self.note
        order = self.env["sale.order"].create(vals)
        return {
            "type": "ir.actions.act_window",
            "name": "Proposal",
            "res_model": "sale.order",
            "res_id": order.id,
            "view_mode": "form",
            "target": "current",
        }
