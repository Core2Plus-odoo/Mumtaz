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
        help="This company's Due-from / Due-to current account.")
    amount = fields.Monetary(string="Transfer Amount")
    # Optional mirror in the other group company.
    dest_company_id = fields.Many2one(
        "res.company", string="Other Company",
        domain="[('id', '!=', company_id)]",
        help="Post the matching entry in this company's books too.")
    dest_bank_journal_id = fields.Many2one(
        "account.journal", string="Other Co. Bank / Cash",
        domain="[('type', 'in', ('bank', 'cash')), "
               "('company_id', '=', dest_company_id)]")
    dest_intercompany_account_id = fields.Many2one(
        "account.account", string="Other Co. Intercompany Account",
        help="The other company's Due-to / Due-from current account.")

    is_bank_transfer = fields.Boolean(
        string="Interbank Transfer",
        help="Move funds between two of this company's own bank/cash accounts.")
    dest_journal_id = fields.Many2one(
        "account.journal", string="To Bank / Cash Journal",
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]",
        help="Destination account. The 'Bank / Cash Journal' above is the source.")

    # Withholding codes bound to the partner (income tax + sales tax), shown so
    # the operator can see which ledgers drive the per-line WHT columns.
    wht_it_tax_id = fields.Many2one(
        "c2p.wht.tax", string="Income Tax WHT", compute="_compute_wht_codes",
        store=True, readonly=False, domain="[('company_id', '=', company_id)]")
    wht_st_tax_id = fields.Many2one(
        "c2p.wht.tax", string="Sales Tax WHT (WHST)",
        compute="_compute_wht_codes", store=True, readonly=False,
        domain="[('company_id', '=', company_id)]")

    line_ids = fields.One2many(
        "c2p.payment.voucher.line", "voucher_id", string="Open Items")
    total_selected = fields.Monetary(compute="_compute_totals", store=True)
    wht_it_amount = fields.Monetary(
        string="Income WHT", compute="_compute_totals", store=True)
    wht_st_amount = fields.Monetary(
        string="Sales WHT", compute="_compute_totals", store=True)
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

    @api.depends("line_ids.selected", "line_ids.to_pay",
                 "line_ids.wht_it", "line_ids.wht_st")
    def _compute_totals(self):
        for v in self:
            selected = v.line_ids.filtered("selected")
            v.total_selected = sum(selected.mapped("to_pay"))
            v.wht_it_amount = sum(selected.mapped("wht_it"))
            v.wht_st_amount = sum(selected.mapped("wht_st"))
            v.wht_total = v.wht_it_amount + v.wht_st_amount
            v.net_amount = v.total_selected - v.wht_total

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
                "amount_tax": move.amount_tax,
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

    @api.onchange("is_bank_transfer")
    def _onchange_is_bank_transfer(self):
        if self.is_bank_transfer:
            self.is_intercompany = False

    @api.onchange("is_intercompany")
    def _onchange_is_intercompany(self):
        if self.is_intercompany:
            self.is_bank_transfer = False

    def action_post(self):
        self.ensure_one()
        if self.is_bank_transfer:
            return self._post_bank_transfer()
        if self.is_intercompany:
            return self._post_intercompany()
        return self._post_voucher()

    def _post_bank_transfer(self):
        self.ensure_one()
        if not self.dest_journal_id:
            raise UserError("Select the destination (To) bank/cash journal.")
        if self.dest_journal_id == self.journal_id:
            raise UserError("Source and destination journals must be different.")
        if not self.amount:
            raise UserError("Enter the transfer amount.")
        src = self.journal_id.default_account_id
        dst = self.dest_journal_id.default_account_id
        if not src or not dst:
            raise UserError("Both journals must have a bank/cash account set.")
        label = self.memo or "Interbank Transfer"
        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.journal_id.id,
            "date": self.date,
            "ref": label,
            "cheque_no": self.cheque_no,
            "cheque_date": self.cheque_date,
            "line_ids": [
                (0, 0, {"account_id": dst.id, "name": label,
                        "debit": self.amount, "credit": 0.0}),
                (0, 0, {"account_id": src.id, "name": label,
                        "debit": 0.0, "credit": self.amount}),
            ],
        })
        move.action_post()
        return self._open_result(move)

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
        net = self.net_amount
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
            "wht_base": self.total_selected,
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
        a_bank = self.journal_id.default_account_id
        if not a_bank:
            raise UserError("The selected journal has no bank/cash account set.")
        outbound = self.payment_type == "outbound"
        label = self.memo or "Intercompany Transfer"
        other = self.dest_company_id
        # On this company's side, tag the line with the other company's partner.
        a_partner = (other.partner_id.id if other
                     else (self.partner_id.id if self.partner_id else False))

        # --- This company (A) ---
        a_inter = {"account_id": self.intercompany_account_id.id,
                   "partner_id": a_partner, "name": label}
        a_bank_l = {"account_id": a_bank.id, "partner_id": a_partner,
                    "name": label}
        if outbound:                      # A sends money
            a_inter.update(debit=self.amount, credit=0.0)
            a_bank_l.update(debit=0.0, credit=self.amount)
        else:                             # A receives money
            a_bank_l.update(debit=self.amount, credit=0.0)
            a_inter.update(debit=0.0, credit=self.amount)
        move_a = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.journal_id.id,
            "date": self.date,
            "ref": label,
            "partner_id": a_partner,
            "is_intercompany": True,
            "cheque_no": self.cheque_no,
            "cheque_date": self.cheque_date,
            "line_ids": [(0, 0, a_inter), (0, 0, a_bank_l)],
        })
        move_a.action_post()
        moves = move_a

        # --- Other company (B): mirror entry ---
        if other:
            if not (self.dest_bank_journal_id
                    and self.dest_intercompany_account_id):
                raise UserError(
                    "For the mirror entry, set the other company's bank journal "
                    "and intercompany account.")
            b_bank = self.dest_bank_journal_id.default_account_id
            if not b_bank:
                raise UserError(
                    "The other company's journal has no bank/cash account set.")
            b_partner = self.company_id.partner_id.id
            b_inter = {"account_id": self.dest_intercompany_account_id.id,
                       "partner_id": b_partner, "name": label}
            b_bank_l = {"account_id": b_bank.id, "partner_id": b_partner,
                        "name": label}
            if outbound:                  # B receives the money
                b_bank_l.update(debit=self.amount, credit=0.0)
                b_inter.update(debit=0.0, credit=self.amount)
            else:                         # B sends the money
                b_inter.update(debit=self.amount, credit=0.0)
                b_bank_l.update(debit=0.0, credit=self.amount)
            move_b = self.env["account.move"].sudo().with_company(other).create({
                "move_type": "entry",
                "company_id": other.id,
                "journal_id": self.dest_bank_journal_id.id,
                "date": self.date,
                "ref": label,
                "partner_id": b_partner,
                "is_intercompany": True,
                "line_ids": [(0, 0, b_inter), (0, 0, b_bank_l)],
            })
            move_b.action_post()
            moves = move_a | move_b

        return self._open_result(moves)


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
    amount_tax = fields.Monetary(string="Invoice Tax")
    residual = fields.Monetary(string="Open")
    to_pay = fields.Monetary(string="To Pay")
    selected = fields.Boolean(string="Pay", default=True)

    # Per-line withholding, driven by the codes bound to the partner.
    wht_it = fields.Monetary(
        string="Income WHT", compute="_compute_line_wht", store=True)
    wht_st = fields.Monetary(
        string="Sales WHT", compute="_compute_line_wht", store=True)
    net_pay = fields.Monetary(
        string="Net", compute="_compute_line_wht", store=True)

    @api.depends("to_pay", "amount_total", "amount_tax",
                 "voucher_id.wht_it_tax_id", "voucher_id.wht_st_tax_id")
    def _compute_line_wht(self):
        for line in self:
            v = line.voucher_id
            # Income WHT is charged on the amount being paid.
            it = (v.wht_it_tax_id.compute_wht(line.to_pay)
                  if v.wht_it_tax_id else 0.0)
            # Sales-tax WHT is charged on the GST portion of this bill, prorated
            # to the amount being paid.
            stax_base = 0.0
            if line.amount_total:
                stax_base = line.amount_tax * (line.to_pay / line.amount_total)
            st = (v.wht_st_tax_id.compute_wht(stax_base)
                  if v.wht_st_tax_id else 0.0)
            line.wht_it = it
            line.wht_st = st
            line.net_pay = line.to_pay - it - st
