# -*- coding: utf-8 -*-
"""Live financial statements for the OWL client action.

Everything is computed from posted account.move.line rows, grouped by Odoo
account type — so it works with any chart of accounts. Amounts are returned as
a flat list of rows the front-end renders directly:

    {"t": "section"|"subhead"|"line"|"sub"|"total"|"grand"|"spacer",
     "l": label, "c": current, "p": prior, "a": [account_ids]}

Sign conventions (Odoo balance = debit − credit):
  * P&L lines display ``-balance`` — revenue (credit) becomes positive, expenses
    (debit) negative, and the row sum is the net profit.
  * Balance-sheet asset lines display ``balance``; equity/liability lines display
    ``-balance``. A "Result for the Period" line (the negated P&L balance) is
    added to equity so the sheet always balances.
"""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import http
from odoo.http import request

PL_INCOME = ("income",)
PL_OTHER_INCOME = ("income_other",)
PL_COGS = ("expense_direct_cost",)
PL_OPEX = ("expense", "expense_depreciation")
PL_TYPES = PL_INCOME + PL_OTHER_INCOME + PL_COGS + PL_OPEX

BS_NONCUR_ASSET = ("asset_fixed", "asset_non_current")
BS_CUR_ASSET = ("asset_receivable", "asset_cash", "asset_current",
                "asset_prepayments")
BS_EQUITY = ("equity", "equity_unaffected")
BS_NONCUR_LIAB = ("liability_non_current",)
BS_CUR_LIAB = ("liability_payable", "liability_credit_card", "liability_current")

RECEIVABLE = ("asset_receivable",)
PAYABLE = ("liability_payable", "liability_credit_card")


def _num(v):
    return round(v or 0.0, 2)


class FinancialReports(http.Controller):

    # ------------------------------------------------------------------ #
    #  helpers
    # ------------------------------------------------------------------ #
    def _balances(self, date_to, date_from=None, types=None):
        """{account_id: {'balance','debit','credit'}} for posted lines."""
        env = request.env
        domain = [("parent_state", "=", "posted"),
                  ("company_id", "=", env.company.id),
                  ("date", "<=", date_to)]
        if date_from:
            domain.append(("date", ">=", date_from))
        if types:
            domain.append(("account_id.account_type", "in", list(types)))
        groups = env["account.move.line"]._read_group(
            domain, ["account_id"], ["balance:sum", "debit:sum", "credit:sum"])
        res = {}
        for acc, bal, deb, cred in groups:
            res[acc.id] = {"balance": bal or 0.0,
                           "debit": deb or 0.0, "credit": cred or 0.0}
        return res

    def _accounts(self):
        env = request.env
        accs = env["account.account"].search(
            [("account_type", "in", list(PL_TYPES) + list(BS_NONCUR_ASSET)
              + list(BS_CUR_ASSET) + list(BS_EQUITY) + list(BS_NONCUR_LIAB)
              + list(BS_CUR_LIAB))])
        return sorted(accs, key=lambda a: (a.code or "zzz", a.name or ""))

    def _label(self, acc):
        return f"{acc.code}  {acc.name}" if acc.code else (acc.name or "")

    # ------------------------------------------------------------------ #
    #  Profit & Loss
    # ------------------------------------------------------------------ #
    def _pl(self, dfrom, dto):
        accs = self._accounts()
        cur = self._balances(dto, dfrom)
        pri = self._balances(dto - relativedelta(years=1),
                             dfrom - relativedelta(years=1))
        rows = []

        def block(title, types):
            sub_c = sub_p = 0.0
            body = []
            for a in accs:
                if a.account_type not in types:
                    continue
                c = -(cur.get(a.id, {}).get("balance", 0.0))
                p = -(pri.get(a.id, {}).get("balance", 0.0))
                if not round(c, 2) and not round(p, 2):
                    continue
                body.append({"t": "line", "l": self._label(a),
                             "c": _num(c), "p": _num(p), "a": [a.id]})
                sub_c += c
                sub_p += p
            if body:
                rows.append({"t": "section", "l": title})
                rows.extend(body)
                rows.append({"t": "sub", "l": "Total " + title,
                             "c": _num(sub_c), "p": _num(sub_p)})
                rows.append({"t": "spacer"})
            return sub_c, sub_p

        rev_c, rev_p = block("Revenue", PL_INCOME)
        cogs_c, cogs_p = block("Cost of Sales", PL_COGS)
        gp_c, gp_p = rev_c + cogs_c, rev_p + cogs_p
        rows.append({"t": "total", "l": "Gross Profit",
                     "c": _num(gp_c), "p": _num(gp_p)})
        rows.append({"t": "spacer"})
        opex_c, opex_p = block("Operating Expenses", PL_OPEX)
        op_c, op_p = gp_c + opex_c, gp_p + opex_p
        rows.append({"t": "total", "l": "Operating Profit / (Loss)",
                     "c": _num(op_c), "p": _num(op_p)})
        rows.append({"t": "spacer"})
        oth_c, oth_p = block("Other Income", PL_OTHER_INCOME)
        rows.append({"t": "grand", "l": "Net Profit / (Loss) for the Period",
                     "c": _num(op_c + oth_c), "p": _num(op_p + oth_p)})
        return rows

    # ------------------------------------------------------------------ #
    #  Balance Sheet
    # ------------------------------------------------------------------ #
    def _bs(self, dto):
        accs = self._accounts()
        cur = self._balances(dto)
        pri = self._balances(dto - relativedelta(years=1))
        # current-year result = negated P&L balance (keeps the sheet balanced)
        pl_c = sum(cur.get(a.id, {}).get("balance", 0.0)
                   for a in accs if a.account_type in PL_TYPES)
        pl_p = sum(pri.get(a.id, {}).get("balance", 0.0)
                   for a in accs if a.account_type in PL_TYPES)

        rows = []

        def block(title, types, sign, sub_label):
            sub_c = sub_p = 0.0
            body = []
            for a in accs:
                if a.account_type not in types:
                    continue
                c = sign * cur.get(a.id, {}).get("balance", 0.0)
                p = sign * pri.get(a.id, {}).get("balance", 0.0)
                if not round(c, 2) and not round(p, 2):
                    continue
                body.append({"t": "line", "l": self._label(a),
                             "c": _num(c), "p": _num(p), "a": [a.id]})
                sub_c += c
                sub_p += p
            if title:
                rows.append({"t": "subhead", "l": title})
            rows.extend(body)
            rows.append({"t": "sub", "l": sub_label,
                         "c": _num(sub_c), "p": _num(sub_p)})
            return sub_c, sub_p

        # Assets
        rows.append({"t": "section", "l": "Assets"})
        nca_c, nca_p = block("Non-Current Assets", BS_NONCUR_ASSET, 1.0,
                             "Total Non-Current Assets")
        rows.append({"t": "spacer"})
        ca_c, ca_p = block("Current Assets", BS_CUR_ASSET, 1.0,
                           "Total Current Assets")
        rows.append({"t": "total", "l": "Total Assets",
                     "c": _num(nca_c + ca_c), "p": _num(nca_p + ca_p)})
        rows.append({"t": "spacer"})

        # Equity & Liabilities
        rows.append({"t": "section", "l": "Equity & Liabilities"})
        eq_c, eq_p = block("Equity", BS_EQUITY, -1.0, "Booked Equity")
        # result for the period folds the live P&L into equity
        rows.append({"t": "line", "l": "Result for the Period",
                     "c": _num(-pl_c), "p": _num(-pl_p), "a": []})
        teq_c, teq_p = eq_c + (-pl_c), eq_p + (-pl_p)
        rows.append({"t": "sub", "l": "Total Equity",
                     "c": _num(teq_c), "p": _num(teq_p)})
        rows.append({"t": "spacer"})
        ncl_c, ncl_p = block("Non-Current Liabilities", BS_NONCUR_LIAB, -1.0,
                             "Total Non-Current Liabilities")
        rows.append({"t": "spacer"})
        cl_c, cl_p = block("Current Liabilities", BS_CUR_LIAB, -1.0,
                           "Total Current Liabilities")
        rows.append({"t": "total", "l": "Total Equity & Liabilities",
                     "c": _num(teq_c + ncl_c + cl_c),
                     "p": _num(teq_p + ncl_p + cl_p)})
        return rows

    # ------------------------------------------------------------------ #
    #  Trial Balance
    # ------------------------------------------------------------------ #
    def _tb(self, dto):
        accs = self._accounts()
        bals = self._balances(dto)
        rows, td, tc = [], 0.0, 0.0
        for a in accs:
            bal = bals.get(a.id, {}).get("balance", 0.0)
            if not round(bal, 2):
                continue
            deb = bal if bal > 0 else 0.0
            cred = -bal if bal < 0 else 0.0
            td += deb
            tc += cred
            rows.append({"t": "line", "l": self._label(a),
                         "c": _num(deb), "p": _num(cred), "a": [a.id]})
        rows.append({"t": "total", "l": "Total",
                     "c": _num(td), "p": _num(tc)})
        return rows

    # ------------------------------------------------------------------ #
    #  Aged partners
    # ------------------------------------------------------------------ #
    def _aged(self, dto, types):
        env = request.env
        lines = env["account.move.line"].search([
            ("parent_state", "=", "posted"),
            ("company_id", "=", env.company.id),
            ("account_id.account_type", "in", list(types)),
            ("date", "<=", dto),
            ("amount_residual", "!=", 0.0),
        ])
        buckets = {}
        for ml in lines:
            partner = ml.partner_id.display_name or "—"
            due = ml.date_maturity or ml.date or dto
            overdue = (dto - due).days
            idx = 0 if overdue <= 0 else 1 if overdue <= 30 else 2 if overdue <= 60 else 3
            b = buckets.setdefault(partner, [0.0, 0.0, 0.0, 0.0])
            b[idx] += abs(ml.amount_residual)
        out = [{"nm": p, "b": [_num(x) for x in v]}
               for p, v in sorted(buckets.items(), key=lambda kv: -sum(kv[1]))]
        return out

    # ------------------------------------------------------------------ #
    #  endpoint
    # ------------------------------------------------------------------ #
    @http.route("/mumtaz_financial_reports/data", type="jsonrpc", auth="user")
    def data(self, report, date_from=None, date_to=None):
        env = request.env
        today = date.today()
        # default to the current fiscal year from company settings
        if not date_to:
            date_to = today
        else:
            date_to = date.fromisoformat(date_to)
        if not date_from:
            fy = env.company.compute_fiscalyear_dates(date_to)
            date_from = fy["date_from"]
        else:
            date_from = date.fromisoformat(date_from)

        meta = {
            "company": env.company.name,
            "currency": env.company.currency_id.name or "",
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        }
        if report == "pl":
            return {"rows": self._pl(date_from, date_to), "meta": meta}
        if report == "bs":
            return {"rows": self._bs(date_to), "meta": meta}
        if report == "tb":
            return {"rows": self._tb(date_to), "meta": meta}
        if report == "aged":
            return {"ar": self._aged(date_to, RECEIVABLE),
                    "ap": self._aged(date_to, PAYABLE), "meta": meta}
        return {"rows": [], "meta": meta}

    @http.route("/mumtaz_financial_reports/drill", type="jsonrpc", auth="user")
    def drill(self, account_ids, date_from=None, date_to=None):
        """Return an act_window descriptor to open the journal items behind a line."""
        domain = [("account_id", "in", account_ids), ("parent_state", "=", "posted")]
        if date_from:
            domain.append(("date", ">=", date_from))
        if date_to:
            domain.append(("date", "<=", date_to))
        return {
            "type": "ir.actions.act_window",
            "name": "Journal Items",
            "res_model": "account.move.line",
            "views": [[False, "list"], [False, "form"]],
            "domain": domain,
            "context": {"search_default_group_by_account": 1},
            "target": "current",
        }
