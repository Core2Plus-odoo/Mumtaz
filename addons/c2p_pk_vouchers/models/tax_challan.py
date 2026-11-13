from odoo import api, fields, models


class C2pTaxChallan(models.Model):
    """Register of tax challans / CPRs received from customers who withheld
    tax from their payments to us. The withheld amount is our advance tax,
    and these records are the proof we hold to claim it.
    """
    _name = "c2p.tax.challan"
    _description = "Tax Challan Received"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(
        string="Challan / CPR No.", required=True, tracking=True, copy=False)
    date = fields.Date(
        string="Challan Date", required=True, tracking=True,
        default=fields.Date.context_today)
    partner_id = fields.Many2one(
        "res.partner", string="Customer / Withholding Agent",
        required=True, tracking=True,
        help="The customer who withheld the tax and deposited it on our behalf.")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
    tax_type = fields.Selection(
        [("income_tax", "Income Tax (advance tax u/s 153)"),
         ("sales_tax", "Sales Tax Withheld")],
        string="Tax", required=True, default="income_tax", tracking=True)
    section_code = fields.Char(string="Section / SRO")
    amount = fields.Monetary(string="Tax Withheld", required=True, tracking=True)
    period = fields.Char(string="Tax Period", help="e.g. Oct-2026 or FY26 Q2.")
    move_id = fields.Many2one(
        "account.move", string="Related Receipt / Invoice",
        domain="[('company_id', '=', company_id)]", tracking=True,
        help="The customer receipt or invoice this withholding relates to.")
    state = fields.Selection(
        [("received", "Received"), ("verified", "Verified"),
         ("claimed", "Claimed in Return")],
        string="Status", default="received", required=True, tracking=True)
    note = fields.Char()

    @api.onchange("move_id")
    def _onchange_move_id(self):
        if self.move_id and self.move_id.partner_id and not self.partner_id:
            self.partner_id = self.move_id.partner_id
