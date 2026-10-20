from odoo import api, fields, models
from odoo.exceptions import UserError


class C2pPaymentVoucher(models.TransientModel):
    _name = "c2p.payment.voucher"
    _description = "Payment / Receipt Voucher"

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
    payment_type = fields.Selection(
        [("outbound", "Payment (Send)"), ("inbound", "Receipt (Receive)")],
        string="Type", required=True, default="outbound")
    partner_id = fields.Many2one("res.partner", string="Party", required=True)
    journal_id = fields.Many2one(
        "account.journal", string="Bank / Cash Journal", required=True,
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]")
    date = fields.Date(required=True, default=fields.Date.context_today)
    cheque_no = fields.Char(string="Cheque / Instrument No.")
    cheque_date = fields.Date(string="Cheque Date")
    memo = fields.Char(string="Narration")

    is_intercompany = fields.Boolean(string="Intercompany Transfer")
    intercompany_account_id = fields.Many2one(
        "account.account", string="Intercompany Account",
        help="Due-from / Due-to current account of the group company.")
    amount = fields.Monetary(string="Transfer Amount")

    wht_tax_id = fields.Many2one(
        "c2p.wht.tax", string="Withholding", compute="_compute_wht_tax_id",
        store=True, readonly=False, domain="[('company_id', '=', company_id)]")
    apply_wht = fields.Boolean(
        string="Deduct Withholding", compute="_compute_apply_wht",
        store=True, readonly=False)
    wht_amount = fields.Monetary(
        string="WHT Amount", compute="_compute_totals", store=True)

    line_ids = fields.One2many(
        "c2p.payment.voucher.line", "voucher_id", string="Open Items")
    total_selected = fields.Monetary(compute="_compute_totals", store=True)
    net_amount = fields.Monetary(
        string="Net Payable / Receivable", compute="_compute_totals", store=True)

    @api.depends("partner_id", "payment_type")
    def _compute_wht_tax_id(self):
        for v in self:
            tax = False
            if v.partner_id:
                partner = v.partner_id.with_company(v.company_id)
                tax = (partner.wht_purchase_tax_id if v.payment_type == "outbound"
                       else partner.wht_sale_tax_id)
            v.wht_tax_id = tax

    @api.depends("wht_tax_id")
    def _compute_apply_wht(self):
        for v in self:
            v.apply_wht = bool(v.wht_tax_id)

    @api.depends("line_ids.selected", "line_ids.to_pay", "apply_wht", "wht_tax_id")
    def _compute_totals(self):
        for v in self:
            total = sum(line.to_pay for line in v.line_ids if line.selected)
            wht = (v.wht_tax_id.compute_wht(total)
                   if (v.apply_wht and v.wht_tax_id) else 0.0)
            v.total_selected = total
            v.wht_amount = wht
            v.net_amount = total - wht

    def action_load_open_items(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError("Select a party first.")
        types = (("in_invoice", "in_refund") if self.payment_type == "outbound"
                 else ("out_invoice", "out_refund"))
        moves = self.env["account.move"].search([
            ("partner_id", "=", self.partner_id.id),
            ("company_id", "=", self.company_id.id),
            ("state", "=", "posted"),
            ("move_type", "in", types),
            ("payment_state", "in", ("not_paid", "partial")),
        ], order="invoice_date, id")
        cur = self.company_id.currency_id
        vals = [(5, 0, 0)]
        for move in moves:
            if cur.is_zero(move.amount_residual):
                continue
            vals.append((0, 0, {
                "move_id": move.id,
                "invoice_date": move.invoice_date,
                "name": move.name,
                "ref": move.ref or move.payment_reference or "",
                "amount_total": move.amount_total,
                "residual": move.amount_residual,
                "to_pay": move.amount_residual,
                "selected": True,
            }))
        self.line_ids = vals
        return {
            "type": "ir.actions.act_window", "res_model": self._name,
            "res_id": self.id, "view_mode": "form", "target": "new",
        }

    def _open_result(self, moves):
        return {
            "type": "ir.actions.act_window", "name": "Voucher Entry",
            "res_model": "account.move", "view_mode": "list,form",
            "domain": [("id", "in", moves.ids)],
            "target": "current",
        }

    def action_post(self):
        self.ensure_one()
        if self.is_intercompany:
            return self._post_intercompany()
        selected = self.line_ids.filtered("selected")
        if not selected:
            raise UserError(
                "Select at least one invoice/bill to knock off, or tick "
                "Intercompany Transfer.")
        moves = selected.mapped("move_id")
        register = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=moves.ids).create({
            "journal_id": self.journal_id.id,
            "payment_date": self.date,
            "communication": self.memo or "",
        })
        register.wht_tax_id = self.wht_tax_id.id
        register.apply_wht = self.apply_wht
        register.wht_base = self.total_selected
        register._onchange_wht_suggest()
        payments = register._create_payments()
        if self.cheque_no or self.cheque_date:
            payments.write({"cheque_no": self.cheque_no,
                            "cheque_date": self.cheque_date})
        return self._open_result(payments.move_id)

    def _post_intercompany(self):
        self.ensure_one()
        if not self.intercompany_account_id:
            raise UserError("Select the intercompany (Due-from/Due-to) account.")
        if not self.amount:
            raise UserError("Enter the transfer amount.")
        bank_account = self.journal_id.default_account_id
        if not bank_account:
            raise UserError("The selected journal has no bank/cash account set.")
        inter_vals = {"account_id": self.intercompany_account_id.id,
                      "partner_id": self.partner_id.id, "name": self.memo or "Intercompany"}
        bank_vals = {"account_id": bank_account.id, "name": self.memo or "Intercompany"}
        if self.payment_type == "outbound":
            inter_vals.update(debit=self.amount, credit=0.0)
            bank_vals.update(debit=0.0, credit=self.amount)
        else:
            bank_vals.update(debit=self.amount, credit=0.0)
            inter_vals.update(debit=0.0, credit=self.amount)
        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.journal_id.id,
            "date": self.date,
            "ref": self.memo or "Intercompany Transfer",
            "partner_id": self.partner_id.id,
            "is_intercompany": True,
            "cheque_no": self.cheque_no,
            "cheque_date": self.cheque_date,
            "line_ids": [(0, 0, inter_vals), (0, 0, bank_vals)],
        })
        move.action_post()
        return self._open_result(move)


class C2pPaymentVoucherLine(models.TransientModel):
    _name = "c2p.payment.voucher.line"
    _description = "Payment / Receipt Voucher Open Item"

    voucher_id = fields.Many2one("c2p.payment.voucher", required=True, ondelete="cascade")
    currency_id = fields.Many2one(related="voucher_id.currency_id")
    move_id = fields.Many2one("account.move", string="Invoice / Bill", required=True)
    invoice_date = fields.Date(string="Date")
    name = fields.Char(string="Number")
    ref = fields.Char(string="Reference")
    amount_total = fields.Monetary(string="Invoice Amount")
    residual = fields.Monetary(string="Open")
    to_pay = fields.Monetary(string="To Pay")
    selected = fields.Boolean(string="Pay", default=True)
