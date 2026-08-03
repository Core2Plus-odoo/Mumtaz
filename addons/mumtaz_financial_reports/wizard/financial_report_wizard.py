import base64
import io
from datetime import date

from odoo import fields, models
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

# Account-type buckets (Odoo 17+ `account.account.account_type` selection).
ASSET_TYPES = (
    "asset_receivable", "asset_cash", "asset_current",
    "asset_non_current", "asset_prepayments", "asset_fixed",
)
LIABILITY_TYPES = (
    "liability_payable", "liability_credit_card",
    "liability_current", "liability_non_current",
)
EQUITY_TYPES = ("equity", "equity_unaffected")
INCOME_TYPES = ("income", "income_other")
EXPENSE_TYPES = ("expense", "expense_depreciation", "expense_direct_cost")


class MumtazFinancialReportWizard(models.TransientModel):
    _name = "mumtaz.financial.report.wizard"
    _description = "Mumtaz Financial Statement Wizard"

    report_type = fields.Selection(
        [("profit_loss", "Profit & Loss"),
         ("balance_sheet", "Balance Sheet"),
         ("trial_balance", "Trial Balance")],
        string="Report", required=True, default="profit_loss")
    company_id = fields.Many2one(
        "res.company", string="Company", required=True,
        default=lambda self: self.env.company)
    date_from = fields.Date(
        string="From", required=True,
        default=lambda self: fields.Date.context_today(self).replace(month=1, day=1))
    date_to = fields.Date(
        string="To", required=True, default=fields.Date.context_today)
    target_move = fields.Selection(
        [("posted", "Posted Entries"), ("all", "All Entries")],
        string="Entries", required=True, default="posted")
    hide_zero = fields.Boolean(string="Hide zero-balance accounts", default=True)
    xlsx_file = fields.Binary(string="Excel File", readonly=True)
    xlsx_name = fields.Char(string="Excel Filename", readonly=True)

    # ── Data ────────────────────────────────────────────────────────────────
    def _base_domain(self):
        domain = [("company_id", "=", self.company_id.id),
                  ("account_id", "!=", False)]
        if self.target_move == "posted":
            domain.append(("parent_state", "=", "posted"))
        else:
            domain.append(("parent_state", "in", ("posted", "draft")))
        return domain

    def _grouped(self, domain):
        """{account: {'debit','credit','balance'}} for a move-line domain."""
        res = {}
        rows = self.env["account.move.line"]._read_group(
            domain, groupby=["account_id"],
            aggregates=["debit:sum", "credit:sum", "balance:sum"])
        for account, debit, credit, balance in rows:
            if not account:
                continue
            res[account] = {"debit": debit or 0.0,
                            "credit": credit or 0.0,
                            "balance": balance or 0.0}
        return res

    def _line(self, account, amount):
        return {"code": account.with_company(self.company_id).code or "",
                "name": account.name or "", "amount": amount}

    def _sort(self, lines):
        return sorted(lines, key=lambda ln: (ln["code"], ln["name"]))

    def _compute_report(self):
        self.ensure_one()
        if not self.date_to:
            raise UserError("Please set the 'To' date.")
        if self.report_type != "balance_sheet" and not self.date_from:
            raise UserError("Please set the 'From' date.")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise UserError("'From' date must be on or before the 'To' date.")

        meta = {
            "company": self.company_id.name,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "target_move": dict(self._fields["target_move"].selection)[self.target_move],
            "printed_on": fields.Date.context_today(self),
        }
        if self.report_type == "profit_loss":
            return {**meta, **self._profit_loss()}
        if self.report_type == "balance_sheet":
            return {**meta, **self._balance_sheet()}
        return {**meta, **self._trial_balance()}

    def _keep(self, amount):
        return not (self.hide_zero and self.company_id.currency_id.is_zero(amount))

    # ── Profit & Loss ───────────────────────────────────────────────────────
    def _profit_loss(self):
        dom = self._base_domain() + [("date", ">=", self.date_from),
                                     ("date", "<=", self.date_to)]
        data = self._grouped(dom)
        income, expense, inc_total, exp_total = [], [], 0.0, 0.0
        for acc, v in data.items():
            if acc.account_type in INCOME_TYPES:
                amount = -v["balance"]
                inc_total += amount
                if self._keep(amount):
                    income.append(self._line(acc, amount))
            elif acc.account_type in EXPENSE_TYPES:
                amount = v["balance"]
                exp_total += amount
                if self._keep(amount):
                    expense.append(self._line(acc, amount))
        return {
            "type": "profit_loss",
            "title": "Profit & Loss Statement",
            "sections": [
                {"name": "Income", "lines": self._sort(income), "total": inc_total},
                {"name": "Expenses", "lines": self._sort(expense), "total": exp_total},
            ],
            "net_label": "Net Profit / (Loss)",
            "net": inc_total - exp_total,
        }

    # ── Balance Sheet ───────────────────────────────────────────────────────
    def _balance_sheet(self):
        dom = self._base_domain() + [("date", "<=", self.date_to)]
        data = self._grouped(dom)
        assets, liabilities, equity = [], [], []
        a_total = l_total = e_total = 0.0
        for acc, v in data.items():
            t = acc.account_type
            if t in ASSET_TYPES:
                amount = v["balance"]
                a_total += amount
                if self._keep(amount):
                    assets.append(self._line(acc, amount))
            elif t in LIABILITY_TYPES:
                amount = -v["balance"]
                l_total += amount
                if self._keep(amount):
                    liabilities.append(self._line(acc, amount))
            elif t in EQUITY_TYPES:
                amount = -v["balance"]
                e_total += amount
                if self._keep(amount):
                    equity.append(self._line(acc, amount))

        # Current-year earnings = P&L movement within the fiscal year to date_to.
        fy_start = date(self.date_to.year, 1, 1)
        pl_dom = self._base_domain() + [("date", ">=", fy_start),
                                        ("date", "<=", self.date_to)]
        pl_balance = 0.0
        for acc, v in self._grouped(pl_dom).items():
            if acc.account_type in INCOME_TYPES + EXPENSE_TYPES:
                pl_balance += v["balance"]
        earnings = -pl_balance
        e_total += earnings
        equity.append({"code": "", "name": "Current Year Earnings", "amount": earnings})

        return {
            "type": "balance_sheet",
            "title": "Balance Sheet",
            "sections": [
                {"name": "Assets", "lines": self._sort(assets), "total": a_total},
                {"name": "Liabilities", "lines": self._sort(liabilities), "total": l_total},
                {"name": "Equity", "lines": self._sort(equity), "total": e_total},
            ],
            "net_label": "Total Assets",
            "net": a_total,
            "check_label": "Total Liabilities + Equity",
            "check": l_total + e_total,
            "balanced": self.company_id.currency_id.is_zero(a_total - (l_total + e_total)),
        }

    # ── Trial Balance ───────────────────────────────────────────────────────
    def _trial_balance(self):
        dom = self._base_domain() + [("date", ">=", self.date_from),
                                     ("date", "<=", self.date_to)]
        data = self._grouped(dom)
        rows, td, tc, tb = [], 0.0, 0.0, 0.0
        for acc, v in data.items():
            if acc.account_type == "off_balance":
                continue
            td += v["debit"]
            tc += v["credit"]
            tb += v["balance"]
            if self.hide_zero and self.company_id.currency_id.is_zero(v["debit"]) \
                    and self.company_id.currency_id.is_zero(v["credit"]):
                continue
            rows.append({"code": acc.with_company(self.company_id).code or "",
                         "name": acc.name or "",
                         "debit": v["debit"], "credit": v["credit"],
                         "balance": v["balance"]})
        return {
            "type": "trial_balance",
            "title": "Trial Balance",
            "rows": self._sort(rows),
            "total_debit": td, "total_credit": tc, "total_balance": tb,
        }

    # ── Output ──────────────────────────────────────────────────────────────
    def _report_filename(self):
        self.ensure_one()
        label = dict(self._fields["report_type"].selection)[self.report_type]
        return "%s - %s" % (label, self.company_id.name or "")

    def action_print(self):
        self.ensure_one()
        # Validate early so errors surface in the wizard, not mid-render.
        self._compute_report()
        return self.env.ref(
            "mumtaz_financial_reports.action_report_financial").report_action(self)

    # ── Excel export (single page) ──────────────────────────────────────────
    def _xlsx_formats(self, wb):
        money = "#,##0.00"
        return {
            "title": wb.add_format({"bold": True, "font_size": 15, "font_color": "#063463"}),
            "sub": wb.add_format({"font_size": 10, "font_color": "#5b6b7b"}),
            "hdr": wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#0a4d94",
                                  "border": 1, "align": "left", "valign": "vcenter"}),
            "hdr_r": wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#0a4d94",
                                    "border": 1, "align": "right", "valign": "vcenter"}),
            "sec": wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#063463", "border": 1}),
            "cell": wb.add_format({"border": 1, "border_color": "#dbe4ef"}),
            "muted": wb.add_format({"border": 1, "border_color": "#dbe4ef", "font_color": "#8794a3"}),
            "num": wb.add_format({"border": 1, "border_color": "#dbe4ef", "align": "right", "num_format": money}),
            "tot_l": wb.add_format({"bold": True, "top": 2, "border_color": "#063463"}),
            "tot": wb.add_format({"bold": True, "top": 2, "border_color": "#063463",
                                  "align": "right", "num_format": money}),
            "net_l": wb.add_format({"bold": True, "bg_color": "#eef5fb", "top": 2}),
            "net": wb.add_format({"bold": True, "bg_color": "#eef5fb", "top": 2,
                                  "align": "right", "num_format": money}),
        }

    def _write_xlsx(self, wb, report):
        f = self._xlsx_formats(wb)
        ws = wb.add_worksheet(report["title"][:31])
        # Force everything onto a single printed page.
        ws.fit_to_pages(1, 1)
        ws.set_paper(9)  # A4
        ws.set_margins(0.3, 0.3, 0.5, 0.5)
        ws.center_horizontally()
        ws.hide_gridlines(2)

        currency = self.company_id.currency_id.name or ""
        if report["type"] == "trial_balance":
            headers = ["Code", "Account", "Debit", "Credit", "Balance"]
            widths = [12, 44, 15, 15, 15]
        else:
            headers = ["Code", "Account", "Amount (%s)" % currency]
            widths = [12, 54, 18]
        for c, w in enumerate(widths):
            ws.set_column(c, c, w)
        last = len(headers) - 1

        # Title block
        ws.merge_range(0, 0, 0, last, report["title"], f["title"])
        if report["type"] == "balance_sheet":
            period = "As of %s" % report["date_to"]
        else:
            period = "%s to %s" % (report["date_from"], report["date_to"])
        ws.merge_range(1, 0, 1, last,
                       "%s  ·  %s  ·  %s" % (report["company"], period, report["target_move"]),
                       f["sub"])
        row = 3

        if report["type"] in ("profit_loss", "balance_sheet"):
            ws.write(row, 0, "Code", f["hdr"])
            ws.write(row, 1, "Account", f["hdr"])
            ws.write(row, 2, headers[2], f["hdr_r"])
            row += 1
            for sec in report["sections"]:
                ws.merge_range(row, 0, row, 1, sec["name"], f["sec"])
                ws.write(row, 2, "", f["sec"])
                row += 1
                if not sec["lines"]:
                    ws.write(row, 0, "", f["muted"])
                    ws.merge_range(row, 1, row, 2, "No movement in this period.", f["muted"])
                    row += 1
                for ln in sec["lines"]:
                    ws.write(row, 0, ln["code"], f["cell"])
                    ws.write(row, 1, ln["name"], f["cell"])
                    ws.write_number(row, 2, ln["amount"], f["num"])
                    row += 1
                ws.merge_range(row, 0, row, 1, "Total %s" % sec["name"], f["tot_l"])
                ws.write_number(row, 2, sec["total"], f["tot"])
                row += 1
            ws.merge_range(row, 0, row, 1, report["net_label"], f["net_l"])
            ws.write_number(row, 2, report["net"], f["net"])
            row += 1
            if report["type"] == "balance_sheet":
                ws.merge_range(row, 0, row, 1, report["check_label"], f["net_l"])
                ws.write_number(row, 2, report["check"], f["net"])
        else:  # trial_balance
            for c, h in enumerate(headers):
                ws.write(row, c, h, f["hdr_r"] if c >= 2 else f["hdr"])
            row += 1
            for ln in report["rows"]:
                ws.write(row, 0, ln["code"], f["cell"])
                ws.write(row, 1, ln["name"], f["cell"])
                ws.write_number(row, 2, ln["debit"], f["num"])
                ws.write_number(row, 3, ln["credit"], f["num"])
                ws.write_number(row, 4, ln["balance"], f["num"])
                row += 1
            if not report["rows"]:
                ws.write(row, 0, "", f["muted"])
                ws.merge_range(row, 1, row, 4, "No movement in this period.", f["muted"])
                row += 1
            ws.merge_range(row, 0, row, 1, "Total", f["tot_l"])
            ws.write_number(row, 2, report["total_debit"], f["tot"])
            ws.write_number(row, 3, report["total_credit"], f["tot"])
            ws.write_number(row, 4, report["total_balance"], f["tot"])

    def action_export_xlsx(self):
        self.ensure_one()
        if xlsxwriter is None:
            raise UserError("The 'xlsxwriter' Python library is not available on this server.")
        report = self._compute_report()
        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {"in_memory": True})
        self._write_xlsx(wb, report)
        wb.close()
        self.write({
            "xlsx_file": base64.b64encode(output.getvalue()),
            "xlsx_name": "%s.xlsx" % self._report_filename(),
        })
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/?model=%s&id=%s&field=xlsx_file"
                   "&filename_field=xlsx_name&download=true" % (self._name, self.id),
            "target": "self",
        }
