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
        net_c = op_c + oth_c
        rows.append({"t": "grand", "l": "Net Profit / (Loss) for the Period",
                     "c": _num(net_c), "p": _num(op_p + oth_p)})

        def marg(x):
            return f"{(x / rev_c * 100):.1f}% margin" if rev_c else "—"

        def delta(c, p):
            return f"{'+' if c >= p else ''}{((c - p) / abs(p) * 100):.1f}% vs prior" if p else "vs prior"
        tiles = [
            {"lab": "Revenue", "val": _num(rev_c), "sub": delta(rev_c, rev_p), "kind": ""},
            {"lab": "Gross Profit", "val": _num(gp_c), "sub": marg(gp_c), "kind": "g"},
            {"lab": "Operating Profit", "val": _num(op_c), "sub": marg(op_c), "kind": ""},
            {"lab": "Net Profit", "val": _num(net_c),
             "sub": (f"{(net_c / rev_c * 100):.1f}% net margin" if rev_c else "—"),
             "kind": "g" if net_c >= 0 else "b"},
        ]
        return rows, tiles

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

        assets = nca_c + ca_c
        liab = ncl_c + cl_c
        wc = ca_c - cl_c
        prior_assets = nca_p + ca_p
        tiles = [
            {"lab": "Total Assets", "val": _num(assets),
             "sub": (f"{'+' if assets >= prior_assets else ''}{((assets - prior_assets) / abs(prior_assets) * 100):.1f}% YoY" if prior_assets else ""),
             "kind": ""},
            {"lab": "Total Equity", "val": _num(teq_c),
             "sub": (f"{(teq_c / assets * 100):.1f}% of assets" if assets else ""), "kind": "g"},
            {"lab": "Total Liabilities", "val": _num(liab),
             "sub": (f"{(liab / assets * 100):.1f}% of assets" if assets else ""), "kind": "n"},
            {"lab": "Working Capital", "val": _num(wc),
             "sub": (f"current ratio {ca_c / cl_c:.2f}×" if cl_c else ""),
             "kind": "g" if wc >= 0 else "b"},
        ]
        return rows, tiles

    # ------------------------------------------------------------------ #
    #  Cash Flow Statement (indirect method)
    # ------------------------------------------------------------------ #
    def _cash_types(self):
        return ("asset_cash",)

    def _flows(self, dfrom, dto):
        """Scalar cash-flow figures for one period, all in cash terms.

        Every balance-sheet movement contributes ``-(closing - opening)`` to
        cash: an asset increase is a use of cash, a liability/equity increase a
        source. Net profit (the period's P&L result) plus the movement of all
        non-cash balance-sheet accounts equals the movement in cash — so the
        statement always reconciles to the actual cash-account movement.
        """
        accs = self._accounts()
        openb = self._balances(dfrom - relativedelta(days=1))
        close = self._balances(dto)

        def impact(types):
            tot, ids = 0.0, []
            for a in accs:
                if a.account_type not in types:
                    continue
                cl = close.get(a.id, {}).get("balance", 0.0)
                op = openb.get(a.id, {}).get("balance", 0.0)
                tot += -(cl - op)
                if round(cl, 2) or round(op, 2):
                    ids.append(a.id)
            return tot, ids

        # period P&L result (net profit) and depreciation add-back
        pl = self._balances(dto, dfrom, PL_TYPES)
        np_ = -sum(v.get("balance", 0.0) for v in pl.values())
        dep = self._balances(dto, dfrom, ("expense_depreciation",))
        dep_amt = sum(v.get("balance", 0.0) for v in dep.values())
        pl_ids = list(pl.keys())

        recv, recv_a = impact(("asset_receivable",))
        prepay, prepay_a = impact(("asset_prepayments",))
        othca, othca_a = impact(("asset_current",))
        pay, pay_a = impact(("liability_payable", "liability_credit_card"))
        othcl, othcl_a = impact(("liability_current",))
        nca, nca_a = impact(BS_NONCUR_ASSET)
        ncl, ncl_a = impact(BS_NONCUR_LIAB)
        eq, eq_a = impact(BS_EQUITY)

        cfo = np_ + dep_amt + recv + prepay + othca + pay + othcl
        cfi = nca - dep_amt          # gross capex = net-book change + depreciation
        cff = ncl + eq
        net = cfo + cfi + cff

        open_cash = sum(openb.get(a.id, {}).get("balance", 0.0)
                        for a in accs if a.account_type in self._cash_types())
        close_cash = sum(close.get(a.id, {}).get("balance", 0.0)
                         for a in accs if a.account_type in self._cash_types())

        return {
            "np": np_, "dep": dep_amt, "recv": recv, "prepay": prepay,
            "othca": othca, "pay": pay, "othcl": othcl, "nca": nca - dep_amt,
            "ncl": ncl, "eq": eq, "cfo": cfo, "cfi": cfi, "cff": cff,
            "net": net, "open_cash": open_cash, "close_cash": close_cash,
            "a": {"np": pl_ids, "recv": recv_a, "prepay": prepay_a,
                  "othca": othca_a, "pay": pay_a, "othcl": othcl_a,
                  "nca": nca_a, "ncl": ncl_a, "eq": eq_a},
        }

    def _cf(self, dfrom, dto):
        c = self._flows(dfrom, dto)
        p = self._flows(dfrom - relativedelta(years=1),
                        dto - relativedelta(years=1))
        rows = []

        def line(label, key, kind="line"):
            row = {"t": kind, "l": label,
                   "c": _num(c.get(key, 0.0)), "p": _num(p.get(key, 0.0))}
            ids = c.get("a", {}).get(key)
            if ids:
                row["a"] = ids
            rows.append(row)

        rows.append({"t": "section", "l": "Cash Flows from Operating Activities"})
        line("Net profit / (loss) for the period", "np")
        line("Adjustment for depreciation & amortisation", "dep")
        line("(Increase) / decrease in trade receivables", "recv")
        line("(Increase) / decrease in prepayments", "prepay")
        line("(Increase) / decrease in inventory & other current assets", "othca")
        line("Increase / (decrease) in trade & other payables", "pay")
        line("Increase / (decrease) in other current liabilities", "othcl")
        line("Net Cash from Operating Activities", "cfo", "sub")
        rows.append({"t": "spacer"})

        rows.append({"t": "section", "l": "Cash Flows from Investing Activities"})
        line("Acquisition of non-current assets (net)", "nca")
        line("Net Cash used in Investing Activities", "cfi", "sub")
        rows.append({"t": "spacer"})

        rows.append({"t": "section", "l": "Cash Flows from Financing Activities"})
        line("Proceeds from / (repayment of) borrowings", "ncl")
        line("Equity contributions / (distributions)", "eq")
        line("Net Cash from Financing Activities", "cff", "sub")
        rows.append({"t": "spacer"})

        line("Net Increase / (Decrease) in Cash", "net", "total")
        line("Cash & Equivalents — Opening", "open_cash")
        line("Cash & Equivalents — Closing", "close_cash", "grand")

        tiles = [
            {"lab": "Operating Cash Flow", "val": _num(c["cfo"]),
             "sub": ("healthy" if c["cfo"] >= 0 else "under pressure"),
             "kind": "g" if c["cfo"] >= 0 else "b"},
            {"lab": "Free Cash Flow", "val": _num(c["cfo"] + c["cfi"]),
             "sub": "operating less investing", "kind": ""},
            {"lab": "Net Change in Cash", "val": _num(c["net"]),
             "sub": (f"{'+' if c['net'] >= 0 else ''}{c['net']:,.0f} this period"),
             "kind": "g" if c["net"] >= 0 else "b"},
            {"lab": "Closing Cash", "val": _num(c["close_cash"]),
             "sub": (f"from {_num(c['open_cash']):,.0f} opening"), "kind": "n"},
        ]
        return rows, tiles

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
            rows, tiles = self._pl(date_from, date_to)
            return {"rows": rows, "tiles": tiles, "meta": meta}
        if report == "bs":
            rows, tiles = self._bs(date_to)
            return {"rows": rows, "tiles": tiles, "meta": meta}
        if report == "cf":
            rows, tiles = self._cf(date_from, date_to)
            return {"rows": rows, "tiles": tiles, "meta": meta}
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
