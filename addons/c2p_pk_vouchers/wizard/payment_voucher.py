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

    # --- Income-tax withholding (u/s 153 etc.) ---
    wht_it_tax_id = fields.Many2one(
        "c2p.wht.tax", string="Income Tax WHT", compute="_compute_wht_codes",
        store=True, readonly=False, domain="[('company_id', '=', company_id)]")
    wht_it_base = fields.Monetary(
        string="Income WHT Base", compute="_compute_bases",
        store=True, readonly=False)
    wht_it_amount = fields.Monetary(
        string="Income WHT", compute="_compute_totals", store=True)

    # --- Sales-tax withholding (WHST, on the GST portion) ---
    wht_st_tax_id = fields.Many2one(
        "c2p.wht.tax", string="Sales Tax WHT (WHST)",
        compute="_compute_wht_codes", store=True, readonly=False,
        domain="[('company_id', '=', company_id)]")
    wht_st_base = fields.Monetary(
        string="Sales WHT Base", compute="_compute_bases",
        store=True, readonly=False)
    wht_st_amount = fields.Monetary(
        string="Sales WHT", compute="_compute_totals", store=True)

    line_ids = fields.One2many(
        "c2p.payment.voucher.line", "voucher_id", string="Open Items")
    total_selected = fields.Monetary(compute="_compute_totals", store=True)
    wht_total = fields.Monetary(compute="_compute_totals", store=True)
    net_amount = fields.Monetary(
        string="Net Payable / Receivable", compute="_compute_totals", store=True)

    @api.depends("partner_id", "payment_type")
    def _compute_wht_codes(self):
        for v in self:
            it = st = False
            if v.partner_id:
                partner = v.partner_id.with_company(v.company_id)
                if v.payment_type == "outbound":
                    it = partner.wht_purchase_tax_id
                    st = partner.wht_purchase_stax_id
                else:
                    it = partner.wht_sale_tax_id
                    st = partner.wht_sale_stax_id
            v.wht_it_tax_id = it
            v.wht_st_tax_id = st

    @api.depends("line_ids.selected", "line_ids.to_pay", "line_ids.move_id")
    def _compute_bases(self):
        for v in self:
            selected = v.line_ids.filtered("selected")
            # Income WHT is charged on the amount paid.
            v.wht_it_base = sum(line.to_pay for line in selected)
            # Sales-tax WHT is charged on the GST portion of the bills, prorated
            # to the amount being paid.
            stax = 0.0
            for line in selected:
                bill = line.move_id
                if bill and bill.amount_total:
                    stax += bill.amount_tax * (line.to_pay / bill.amount_total)
            v.wht_st_base = round(stax, 2)

    @api.depends("line_ids.selected", "line_ids.to_pay",
                 "wht_it_tax_id", "wht_it_base", "wht_st_tax_id", "wht_st_base")
    def _compute_totals(self):
        for v in self:
            total = sum(line.to_pay for line in v.line_ids if line.selected)
            it = (v.wht_it_tax_id.compute_wht(v.wht_it_base)
                  if v.wht_it_tax_id else 0.0)
            st = (v.wht_st_tax_id.compute_wht(v.wht_st_base)
                  if v.wht_st_tax_id else 0.0)
            v.total_selected = total
            v.wht_it_amount = it
            v.wht_st_amount = st
            v.wht_total = it + st
            v.net_amount = total - it - st

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
        return self._post_voucher()

    def _wht_components(self):
        """Return [(code, amount), ...] for the withholdings that apply."""
        self.ensure_one()
        out = []
        for code, amount in ((self.wht_it_tax_id, self.wht_it_amount),
                             (self.wht_st_tax_id, self.wht_st_amount)):
            if code and amount:
                if not code.account_id:
                    raise UserError(
                        "Set the WHT ledger on code '%s' (on the vendor/customer "
                        "form or in Withholding Codes) before posting." % code.name)
                out.append((code, amount))
        return out

    def _post_voucher(self):
        self.ensure_one()
        selected = self.line_ids.filtered("selected")
        if not selected:
            raise UserError(
                "Select at least one invoice/bill to knock off, or tick "
                "Intercompany Transfer.")
        bank_account = self.journal_id.default_account_id
        if not bank_account:
            raise UserError("The selected journal has no bank/cash account set.")
        cur = self.company_id.currency_id
        outbound = self.payment_type == "outbound"
        wht = self._wht_components()
        wht_total = sum(a for _, a in wht)
        net = self.total_selected - wht_total
        if cur.compare_amounts(net, 0.0) < 0:
            raise UserError("Withholding exceeds the amount being paid.")

        label = self.memo or ("Payment" if outbound else "Receipt")
        move_lines = []
        bill_control_lines = self.env["account.move.line"]
        for line in selected:
            bill = line.move_id
            ctrl = bill.line_ids.filtered(
                lambda ln: ln.account_id.account_type in (
                    "liability_payable", "asset_receivable")
                and not ln.reconciled)[:1]
            if not ctrl:
                raise UserError(
                    "Could not find the open control line on %s." % bill.name)
            bill_control_lines |= ctrl
            vals = {"account_id": ctrl.account_id.id,
                    "partner_id": self.partner_id.id,
                    "name": bill.name or label}
            if outbound:
                vals.update(debit=line.to_pay, credit=0.0)
            else:
                vals.update(debit=0.0, credit=line.to_pay)
            move_lines.append((0, 0, vals))

        bank_vals = {"account_id": bank_account.id,
                     "partner_id": self.partner_id.id, "name": label}
        if outbound:
            bank_vals.update(debit=0.0, credit=net)
        else:
            bank_vals.update(debit=net, credit=0.0)
        move_lines.append((0, 0, bank_vals))

        for code, amount in wht:
            wlabel = ("WHT %s %s" % (code.name, code.section_code or "")).strip()
            wvals = {"account_id": code.account_id.id,
                     "partner_id": self.partner_id.id, "name": wlabel}
            if outbound:
                wvals.update(debit=0.0, credit=amount)
            else:
                wvals.update(debit=amount, credit=0.0)
            move_lines.append((0, 0, wvals))

        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.journal_id.id,
            "date": self.date,
            "ref": label,
            "partner_id": self.partner_id.id,
            "cheque_no": self.cheque_no,
            "cheque_date": self.cheque_date,
            "is_wht": bool(wht),
            "wht_tax_id": wht[0][0].id if wht else False,
            "wht_base": self.wht_it_base,
            "line_ids": move_lines,
        })
        move.action_post()

        # Reconcile the voucher's control lines against the open bills, grouped
        # by account so partial and multi-bill knock-offs allocate correctly.
        created_ctrl = move.line_ids.filtered(
            lambda ln: ln.account_id.account_type in (
                "liability_payable", "asset_receivable"))
        for acct in created_ctrl.mapped("account_id"):
            group = (created_ctrl.filtered(lambda ln: ln.account_id == acct)
                     | bill_control_lines.filtered(
                         lambda ln: ln.account_id == acct))
            group.reconcile()
        return self._open_result(move)

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
                      "partner_id": self.partner_id.id,
                      "name": self.memo or "Intercompany"}
        bank_vals = {"account_id": bank_account.id,
                     "name": self.memo or "Intercompany"}
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

    voucher_id = fields.Many2one(
        "c2p.payment.voucher", required=True, ondelete="cascade")
    currency_id = fields.Many2one(related="voucher_id.currency_id")
    move_id = fields.Many2one("account.move", string="Invoice / Bill", required=True)
    invoice_date = fields.Date(string="Date")
    name = fields.Char(string="Number")
    ref = fields.Char(string="Reference")
    amount_total = fields.Monetary(string="Invoice Amount")
    residual = fields.Monetary(string="Open")
    to_pay = fields.Monetary(string="To Pay")
    selected = fields.Boolean(string="Pay", default=True)
