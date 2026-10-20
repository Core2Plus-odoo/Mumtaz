from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

VOUCHER_TITLES = {
    "payment": "PAYMENT VOUCHER",
    "receipt": "RECEIPT VOUCHER",
    "payable": "PAYABLE VOUCHER",
    "receivable": "RECEIVABLE VOUCHER",
    "journal": "JOURNAL VOUCHER",
}


class AccountMove(models.Model):
    _inherit = "account.move"

    cheque_no = fields.Char(string="Cheque / Instrument No.", copy=False, tracking=True)
    cheque_date = fields.Date(string="Cheque Date", copy=False, tracking=True)
    is_intercompany = fields.Boolean(
        string="Intercompany", copy=False,
        help="Mark this voucher as an intercompany transaction "
             "(posted to a Due-from / Due-to current account).")
    # Withholding (set by the Record Withholding wizard)
    is_wht = fields.Boolean(string="Withholding Entry", copy=False)
    wht_tax_id = fields.Many2one("c2p.wht.tax", string="WHT Code", copy=False)
    wht_base = fields.Monetary(string="WHT Base", copy=False)

    # ── Voucher classification ──────────────────────────────────────────────
    def _voucher_kind(self):
        """payment | receipt | payable | receivable | journal — from the journal."""
        self.ensure_one()
        jtype = self.journal_id.type
        if jtype in ("bank", "cash"):
            bank_acc = self.journal_id.default_account_id
            bank_line = self.line_ids.filtered(
                lambda line: bank_acc and line.account_id == bank_acc)[:1]
            if bank_line and bank_line.credit > 0:
                return "payment"
            if bank_line and bank_line.debit > 0:
                return "receipt"
            # No identifiable bank line: fall back to net direction.
            return "receipt" if sum(self.line_ids.mapped("balance")) < 0 else "payment"
        if jtype == "purchase":
            return "payable"
        if jtype == "sale":
            return "receivable"
        return "journal"

    def _voucher_lines(self):
        self.ensure_one()
        lines = self.line_ids.filtered(
            lambda line: line.display_type not in ("line_section", "line_note"))
        return lines.sorted(lambda line: (0 if line.debit else 1, -abs(line.balance)))

    def _voucher_data(self):
        """Everything the voucher template needs, so the QWeb stays simple."""
        self.ensure_one()
        kind = self._voucher_kind()
        lines = self._voucher_lines()
        total = sum(lines.mapped("debit"))
        party_label = {"payment": "Payee", "receipt": "Received From"}.get(kind)
        if kind in ("payment", "receipt"):
            signatures = ["Prepared By", "Checked/Verified By", "Approved By", "Received By"]
        else:
            signatures = ["Prepared By", "Checked/Verified By", "Approved By"]
        try:
            in_words = self.currency_id.amount_to_text(total)
        except Exception:
            in_words = ""
        return {
            "kind": kind,
            "title": VOUCHER_TITLES.get(kind, "VOUCHER"),
            "party_label": party_label,
            "party": self.partner_id.display_name or "",
            "show_cheque": kind in ("payment", "receipt"),
            "lines": lines,
            "total": total,
            "signatures": signatures,
            "in_words": in_words,
            "posted": self.state == "posted",
            "intercompany": self.is_intercompany,
        }

    def _voucher_cc_jc(self, line):
        """Best-effort (Cost Center, Job Code) codes from analytic distribution.

        Mapping assumes a 'Job'-named analytic plan for J/C and any other plan
        for CC; adjust once the client confirms their analytic plan setup.
        """
        cc, jc = "00", "000"
        dist = line.analytic_distribution or {}
        acc_ids = []
        for key in dist:
            acc_ids += [int(x) for x in str(key).split(",") if str(x).strip().isdigit()]
        for acc in self.env["account.analytic.account"].browse(acc_ids).exists():
            plan = (acc.plan_id.name or "").lower()
            if "job" in plan:
                jc = acc.code or acc.name or jc
            else:
                cc = acc.code or acc.name or cc
        return cc, jc

    def _voucher_knockoff(self):
        """Invoices/bills offset against this payment/receipt (for the knock-off report)."""
        self.ensure_one()
        recs = []
        open_lines = self.line_ids.filtered(
            lambda line: line.account_id.account_type in (
                "asset_receivable", "liability_payable"))
        for line in open_lines:
            for partial in (line.matched_debit_ids | line.matched_credit_ids):
                counter = (partial.credit_move_id
                           if partial.debit_move_id == line else partial.debit_move_id)
                inv = counter.move_id
                if not inv or inv == self:
                    continue
                recs.append({
                    "invoice": inv.name or "",
                    "ref": inv.ref or inv.payment_reference or "",
                    "partner": inv.partner_id.display_name or "",
                    "inv_amt": abs(inv.amount_total),
                    "paid": partial.amount,
                })
        return recs

    # ── Journal Voucher control ─────────────────────────────────────────────
    @api.constrains("line_ids", "state", "journal_id")
    def _check_journal_voucher_no_bank_cash(self):
        for move in self:
            if move.state != "posted" or not move.journal_id.is_journal_voucher:
                continue
            bad = move.line_ids.filtered(
                lambda line: line.account_id.account_type in (
                    "asset_cash", "liability_credit_card"))
            if bad:
                raise ValidationError(_(
                    "Journal '%s' is set up for Journal Vouchers (non-cash / "
                    "non-bank adjustments only). Record payments through a Payment "
                    "Voucher and receipts through a Receipt Voucher instead.")
                    % move.journal_id.name)
