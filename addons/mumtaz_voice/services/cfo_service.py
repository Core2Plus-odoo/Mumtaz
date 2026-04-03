from datetime import date

from odoo import fields, models


class CFOService(models.AbstractModel):
    _name = "mumtaz.cfo.service"
    _description = "Mumtaz CFO Data Service - Financial data queries from Odoo DB"

    INTENT_KEYWORDS = {
        "cash_position": ["cash", "bank balance", "liquidity", "bank account", "available funds", "cash on hand"],
        "pl_statement": ["profit", "loss", "p&l", "pnl", "net income", "bottom line", "income statement", "ebitda"],
        "revenue_analysis": ["revenue", "income", "turnover", "sales revenue", "top line", "gross revenue"],
        "expense_analysis": ["expense", "cost", "spending", "opex", "capex", "overhead", "burn rate"],
        "ar_aging": ["receivable", "invoice", "customer owes", "outstanding invoice",
                     "collection", "aging", "overdue customer", "days sales outstanding", "dso"],
        "ap_aging": ["payable", "bill", "vendor", "supplier", "we owe", "outstanding bill",
                     "days payable", "dpo", "overdue bill", "accounts payable"],
        "sales_performance": ["sales order", "quotation", "order", "sold", "pipeline"],
        "top_customers": ["top customer", "best customer", "biggest client", "customer revenue", "customer ranking"],
        "kpi_overview": ["kpi", "overview", "summary", "dashboard", "financial health",
                         "how are we doing", "performance", "how is the company", "status"],
    }

    def detect_intent(self, prompt):
        lower = (prompt or "").lower()
        for intent, keywords in self.INTENT_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                return intent
        return "kpi_overview"

    def build_financial_context(self, company, intent):
        today = fields.Date.today()
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)
        currency = company.currency_id

        parts = [
            f"Company: {company.name}",
            f"Currency: {currency.name} ({currency.symbol})",
            f"Report Date: {today.strftime('%B %d, %Y')}",
            f"Current Month: {month_start.strftime('%B %Y')}",
            "",
        ]

        cash = self._get_cash_position(company)
        parts += self._format_cash(cash, currency)

        if intent in ("pl_statement", "revenue_analysis", "expense_analysis", "kpi_overview"):
            pl = self._get_pl_summary(company, month_start, year_start, today)
            parts += self._format_pl(pl, currency)

        if intent in ("ar_aging", "kpi_overview"):
            ar = self._get_ar_aging(company, today)
            parts += self._format_ar(ar, currency)

        if intent in ("ap_aging", "kpi_overview"):
            ap = self._get_ap_aging(company, today)
            parts += self._format_ap(ap, currency)

        if intent in ("sales_performance", "top_customers", "kpi_overview"):
            sales = self._get_sales_summary(company, month_start, year_start, today)
            parts += self._format_sales(sales, currency)

        return "\n".join(parts)

    def _get_cash_position(self, company):
        accounts = self.env["account.account"].search(
            [("company_ids", "in", [company.id]), ("account_type", "=", "asset_cash")]
        )
        if not accounts:
            return {"total": 0.0, "accounts": []}
        lines = self.env["account.move.line"].read_group(
            [("company_id", "=", company.id), ("account_id", "in", accounts.ids),
             ("move_id.state", "=", "posted")],
            ["account_id", "balance:sum"], ["account_id"],
        )
        account_map = {a.id: a.name for a in accounts}
        account_balances = []
        total = 0.0
        for row in lines:
            acc_id = row["account_id"][0]
            balance = row.get("balance", 0.0) or 0.0
            total += balance
            account_balances.append({"name": account_map.get(acc_id, ""), "balance": balance})
        return {"total": total, "accounts": account_balances}

    def _get_pl_summary(self, company, month_start, year_start, today):
        def _sum(date_from, date_to, acc_types):
            result = self.env["account.move.line"].read_group(
                [("company_id", "=", company.id), ("move_id.state", "=", "posted"),
                 ("date", ">=", date_from), ("date", "<=", date_to),
                 ("account_id.account_type", "in", acc_types)],
                ["balance:sum"], [],
            )
            return result[0].get("balance", 0.0) if result else 0.0

        income_types = ["income", "income_other"]
        expense_types = ["expense", "expense_depreciation", "expense_direct_cost"]
        mtd_revenue = -_sum(month_start, today, income_types)
        mtd_expenses = _sum(month_start, today, expense_types)
        ytd_revenue = -_sum(year_start, today, income_types)
        ytd_expenses = _sum(year_start, today, expense_types)
        mtd_net = mtd_revenue - mtd_expenses
        ytd_net = ytd_revenue - ytd_expenses
        return {
            "mtd_revenue": mtd_revenue, "mtd_expenses": mtd_expenses, "mtd_net": mtd_net,
            "mtd_margin": (mtd_net / mtd_revenue * 100) if mtd_revenue else 0.0,
            "ytd_revenue": ytd_revenue, "ytd_expenses": ytd_expenses, "ytd_net": ytd_net,
            "ytd_margin": (ytd_net / ytd_revenue * 100) if ytd_revenue else 0.0,
        }

    def _get_ar_aging(self, company, today):
        invoices = self.env["account.move"].search_read(
            [("company_id", "=", company.id), ("move_type", "in", ["out_invoice", "out_refund"]),
             ("state", "=", "posted"), ("payment_state", "not in", ["paid", "reversed", "in_payment"])],
            ["amount_residual", "invoice_date_due", "move_type"],
        )
        return self._bucket_aging(invoices, today)

    def _get_ap_aging(self, company, today):
        bills = self.env["account.move"].search_read(
            [("company_id", "=", company.id), ("move_type", "in", ["in_invoice", "in_refund"]),
             ("state", "=", "posted"), ("payment_state", "not in", ["paid", "reversed", "in_payment"])],
            ["amount_residual", "invoice_date_due", "move_type"],
        )
        return self._bucket_aging(bills, today, refund_type="in_refund")

    def _bucket_aging(self, records, today, refund_type="out_refund"):
        buckets = {"current": 0.0, "overdue_30": 0.0, "overdue_60": 0.0, "overdue_90": 0.0, "overdue_90plus": 0.0}
        total = 0.0
        count = 0
        for rec in records:
            amount = rec["amount_residual"] or 0.0
            if rec.get("move_type") == refund_type:
                amount = -amount
            due = rec["invoice_date_due"]
            if isinstance(due, str):
                due = date.fromisoformat(due)
            due = due or today
            days_overdue = (today - due).days if isinstance(due, date) else 0
            total += amount
            count += 1
            if days_overdue <= 0:
                buckets["current"] += amount
            elif days_overdue <= 30:
                buckets["overdue_30"] += amount
            elif days_overdue <= 60:
                buckets["overdue_60"] += amount
            elif days_overdue <= 90:
                buckets["overdue_90"] += amount
            else:
                buckets["overdue_90plus"] += amount
        return {"total": total, "count": count, **buckets}

    def _get_sales_summary(self, company, month_start, year_start, today):
        if "sale.order" not in self.env:
            return {"mtd_sales": 0.0, "ytd_sales": 0.0, "order_count": 0, "top_customers": []}
        orders = self.env["sale.order"].search_read(
            [("company_id", "=", company.id), ("state", "in", ["sale", "done"]),
             ("date_order", ">=", year_start), ("date_order", "<=", today)],
            ["amount_total", "date_order", "partner_id"],
        )
        mtd_sales = ytd_sales = 0.0
        customer_totals: dict = {}
        for order in orders:
            amount = order["amount_total"] or 0.0
            order_date = order["date_order"]
            if hasattr(order_date, "date"):
                order_date = order_date.date()
            elif isinstance(order_date, str):
                order_date = date.fromisoformat(order_date[:10])
            ytd_sales += amount
            if order_date >= month_start:
                mtd_sales += amount
            if order.get("partner_id"):
                name = order["partner_id"][1] if isinstance(order["partner_id"], (list, tuple)) else str(order["partner_id"])
                customer_totals[name] = customer_totals.get(name, 0.0) + amount
        top = sorted(customer_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        return {"mtd_sales": mtd_sales, "ytd_sales": ytd_sales, "order_count": len(orders),
                "top_customers": [{"name": n, "revenue": v} for n, v in top]}

    def _fmt(self, currency, amount):
        return f"{currency.symbol}{amount:,.2f}"

    def _format_cash(self, cash, currency):
        lines = ["CASH & LIQUIDITY:"]
        lines.append(f"  Total Cash & Bank: {self._fmt(currency, cash['total'])}")
        for acc in cash.get("accounts", []):
            lines.append(f"  - {acc['name']}: {self._fmt(currency, acc['balance'])}")
        lines.append("")
        return lines

    def _format_pl(self, pl, currency):
        lines = ["INCOME STATEMENT:"]
        lines.append(f"  Month-to-Date Revenue:    {self._fmt(currency, pl['mtd_revenue'])}")
        lines.append(f"  Month-to-Date Expenses:   {self._fmt(currency, pl['mtd_expenses'])}")
        lines.append(f"  Month-to-Date Net Profit: {self._fmt(currency, pl['mtd_net'])}  ({pl['mtd_margin']:.1f}% margin)")
        lines.append(f"  Year-to-Date Revenue:     {self._fmt(currency, pl['ytd_revenue'])}")
        lines.append(f"  Year-to-Date Expenses:    {self._fmt(currency, pl['ytd_expenses'])}")
        lines.append(f"  Year-to-Date Net Profit:  {self._fmt(currency, pl['ytd_net'])}  ({pl['ytd_margin']:.1f}% margin)")
        lines.append("")
        return lines

    def _format_ar(self, ar, currency):
        lines = ["ACCOUNTS RECEIVABLE (Outstanding Customer Invoices):"]
        lines.append(f"  Total Outstanding:   {self._fmt(currency, ar['total'])}  ({ar['count']} invoices)")
        lines.append(f"  Current (not due):   {self._fmt(currency, ar['current'])}")
        lines.append(f"  Overdue  1-30 days:  {self._fmt(currency, ar['overdue_30'])}")
        lines.append(f"  Overdue 31-60 days:  {self._fmt(currency, ar['overdue_60'])}")
        lines.append(f"  Overdue 61-90 days:  {self._fmt(currency, ar['overdue_90'])}")
        lines.append(f"  Overdue  90+ days:   {self._fmt(currency, ar['overdue_90plus'])}")
        lines.append("")
        return lines

    def _format_ap(self, ap, currency):
        lines = ["ACCOUNTS PAYABLE (Outstanding Vendor Bills):"]
        lines.append(f"  Total Outstanding:   {self._fmt(currency, ap['total'])}  ({ap['count']} bills)")
        lines.append(f"  Current (not due):   {self._fmt(currency, ap['current'])}")
        lines.append(f"  Overdue  1-30 days:  {self._fmt(currency, ap['overdue_30'])}")
        lines.append(f"  Overdue 31-60 days:  {self._fmt(currency, ap['overdue_60'])}")
        lines.append(f"  Overdue 61-90 days:  {self._fmt(currency, ap['overdue_90'])}")
        lines.append(f"  Overdue  90+ days:   {self._fmt(currency, ap['overdue_90plus'])}")
        lines.append("")
        return lines

    def _format_sales(self, sales, currency):
        lines = ["SALES PERFORMANCE:"]
        lines.append(f"  Month-to-Date Sales:  {self._fmt(currency, sales['mtd_sales'])}")
        lines.append(f"  Year-to-Date Sales:   {self._fmt(currency, sales['ytd_sales'])}")
        lines.append(f"  Total Orders (YTD):   {sales['order_count']}")
        if sales.get("top_customers"):
            lines.append("  Top Customers (YTD by Revenue):")
            for i, c in enumerate(sales["top_customers"], 1):
                lines.append(f"    {i}. {c['name']}: {self._fmt(currency, c['revenue'])}")
        lines.append("")
        return lines
