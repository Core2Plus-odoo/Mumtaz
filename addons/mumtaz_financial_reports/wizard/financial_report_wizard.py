from datetime import date

from odoo import fields, models
from odoo.exceptions import UserError

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
