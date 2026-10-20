from odoo import api, fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    wht_tax_id = fields.Many2one(
        "c2p.wht.tax", string="Withholding",
        compute="_compute_wht_tax_id", store=True, readonly=False,
        domain="[('company_id', '=', company_id)]")
    apply_wht = fields.Boolean(
        string="Deduct Withholding",
        compute="_compute_apply_wht", store=True, readonly=False)
    wht_base = fields.Monetary(
        string="WHT Base", compute="_compute_wht_base", store=True, readonly=False,
        currency_field="currency_id")
    wht_amount = fields.Monetary(
        string="WHT Amount", compute="_compute_wht_amount", store=True, readonly=False,
        currency_field="currency_id")

    @api.depends("partner_id", "payment_type")
    def _compute_wht_tax_id(self):
        for wiz in self:
            tax = False
            if wiz.partner_id:
                partner = wiz.partner_id.with_company(wiz.company_id)
                if wiz.payment_type == "outbound":
                    tax = partner.wht_purchase_tax_id
                elif wiz.payment_type == "inbound":
                    tax = partner.wht_sale_tax_id
            wiz.wht_tax_id = tax

    @api.depends("wht_tax_id")
    def _compute_apply_wht(self):
        for wiz in self:
            wiz.apply_wht = bool(wiz.wht_tax_id)

    @api.depends("source_amount", "apply_wht")
    def _compute_wht_base(self):
        for wiz in self:
            wiz.wht_base = wiz.source_amount if wiz.apply_wht else 0.0

    @api.depends("wht_tax_id", "wht_base", "apply_wht")
    def _compute_wht_amount(self):
        for wiz in self:
            wiz.wht_amount = (wiz.wht_tax_id.compute_wht(wiz.wht_base)
                              if (wiz.apply_wht and wiz.wht_tax_id) else 0.0)

    def _wht_label(self):
        self.ensure_one()
        return ("WHT %s %s" % (self.wht_tax_id.name,
                               self.wht_tax_id.section_code or "")).strip()

    @api.onchange("apply_wht", "wht_tax_id", "wht_base", "wht_amount")
    def _onchange_wht_suggest(self):
        """Live suggestion: show the net payable and route WHT to its ledger."""
        for wiz in self:
            if wiz.apply_wht and wiz.wht_tax_id and wiz.wht_amount:
                wiz.payment_difference_handling = "reconcile"
                wiz.writeoff_account_id = wiz.wht_tax_id.account_id
                wiz.writeoff_label = wiz._wht_label()
                wiz.amount = max(wiz.source_amount - wiz.wht_amount, 0.0)

    def _create_payments(self):
        # Enforce the WHT write-off at commit, even if the onchange did not run
        # (e.g. the wizard was driven programmatically).
        for wiz in self:
            if (wiz.apply_wht and wiz.wht_tax_id and wiz.wht_amount
                    and wiz.wht_tax_id.account_id):
                wiz.payment_difference_handling = "reconcile"
                wiz.writeoff_account_id = wiz.wht_tax_id.account_id
                wiz.writeoff_label = wiz._wht_label()
                if wiz.source_amount and wiz.amount >= wiz.source_amount:
                    wiz.amount = max(wiz.source_amount - wiz.wht_amount, 0.0)
        payments = super()._create_payments()
        for wiz in self:
            if wiz.apply_wht and wiz.wht_tax_id and wiz.wht_amount:
                payments.move_id.write({
                    "is_wht": True,
                    "wht_tax_id": wiz.wht_tax_id.id,
                    "wht_base": wiz.wht_base,
                })
        return payments
