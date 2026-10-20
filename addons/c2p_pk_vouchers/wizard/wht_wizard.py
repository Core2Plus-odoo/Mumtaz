from odoo import api, fields, models
from odoo.exceptions import UserError


class C2pWhtWizard(models.TransientModel):
    _name = "c2p.wht.wizard"
    _description = "Record Withholding Deduction"

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
    date = fields.Date(required=True, default=fields.Date.context_today)
    transaction_type = fields.Selection(
        [("purchase", "On Payment (we withhold from vendor)"),
         ("sale", "On Receipt (customer withholds from us)")],
        string="Type", required=True, default="purchase")
    partner_id = fields.Many2one("res.partner", string="Partner", required=True)
    wht_tax_id = fields.Many2one(
        "c2p.wht.tax", string="WHT Code", required=True,
        domain="[('transaction_type', '=', transaction_type), "
               "('company_id', '=', company_id)]")
    base_amount = fields.Monetary(string="Base Amount", required=True)
    wht_amount = fields.Monetary(
        string="Withholding Amount", compute="_compute_wht_amount",
        store=True, readonly=True)
    journal_id = fields.Many2one(
        "account.journal", string="Journal", required=True,
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]")
    partner_account_id = fields.Many2one(
        "account.account", string="Partner Account", required=True,
        compute="_compute_partner_account", store=True, readonly=False)
    memo = fields.Char(string="Memo")

    @api.depends("wht_tax_id", "base_amount")
    def _compute_wht_amount(self):
        for wiz in self:
            wiz.wht_amount = (wiz.wht_tax_id.compute_wht(wiz.base_amount)
                              if wiz.wht_tax_id else 0.0)

    @api.depends("partner_id", "transaction_type", "company_id")
    def _compute_partner_account(self):
        for wiz in self:
            acc = False
            if wiz.partner_id:
                partner = wiz.partner_id.with_company(wiz.company_id)
                acc = (partner.property_account_payable_id
                       if wiz.transaction_type == "purchase"
                       else partner.property_account_receivable_id)
            wiz.partner_account_id = acc

    def action_record(self):
        self.ensure_one()
        if not self.wht_amount:
            raise UserError(
                "The withholding amount is zero — check the base amount and rate.")
        if not self.wht_tax_id.account_id:
            raise UserError(
                "Set the WHT Account on withholding code '%s' first."
                % self.wht_tax_id.name)
        wht_acc = self.wht_tax_id.account_id
        label = ("WHT %s %s" % (self.wht_tax_id.name,
                                self.wht_tax_id.section_code or "")).strip()
        partner_vals = {"account_id": self.partner_account_id.id,
                        "partner_id": self.partner_id.id, "name": label}
        wht_vals = {"account_id": wht_acc.id, "partner_id": self.partner_id.id,
                    "name": label}
        if self.transaction_type == "purchase":
            # We withhold from the vendor: reduce payable, raise WHT liability.
            partner_vals.update(debit=self.wht_amount, credit=0.0)
            wht_vals.update(debit=0.0, credit=self.wht_amount)
        else:
            # Customer withheld from our receipt: advance tax asset, reduce receivable.
            wht_vals.update(debit=self.wht_amount, credit=0.0)
            partner_vals.update(debit=0.0, credit=self.wht_amount)
        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.journal_id.id,
            "date": self.date,
            "ref": self.memo or label,
            "partner_id": self.partner_id.id,
            "is_wht": True,
            "wht_tax_id": self.wht_tax_id.id,
            "wht_base": self.base_amount,
            "line_ids": [(0, 0, partner_vals), (0, 0, wht_vals)],
        })
        move.action_post()
        return {
            "type": "ir.actions.act_window",
            "name": "Withholding Entry",
            "res_model": "account.move",
            "res_id": move.id,
            "view_mode": "form",
            "target": "current",
        }
