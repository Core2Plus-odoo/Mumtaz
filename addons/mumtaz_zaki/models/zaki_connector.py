from datetime import datetime

from odoo import api, fields, models


class ZakiConnector(models.AbstractModel):
    """Read-only financial snapshot of the tenant's Odoo, consumed by the
    ZAKI AI CFO backend (zaki.mumtaz.digital) via XML-RPC:

        execute_kw(db, uid, pw, 'zaki.connector', 'get_snapshot', [])

    Optional modules (hr.payslip, crm.lead) are guarded so this works on any
    tenant DB regardless of which apps are installed.
    """
    _name = "zaki.connector"
    _description = "ZAKI AI CFO — financial snapshot bridge"

    @api.model
    def get_snapshot(self):
        today = fields.Date.today()
        month_start = today.replace(day=1)
        AM = self.env["account.move"]

        inv = AM.search([("move_type", "=", "out_invoice"), ("state", "=", "posted"),
                         ("invoice_date", ">=", month_start)])
        revenue = abs(sum(inv.mapped("amount_total_signed"))) if inv else 0.0

        bills = AM.search([("move_type", "=", "in_invoice"), ("state", "=", "posted"),
                           ("invoice_date", ">=", month_start)])
        expenses = abs(sum(bills.mapped("amount_total_signed"))) if bills else 0.0

        AML = self.env["account.move.line"]
        ar = AML.search([("account_type", "=", "asset_receivable"),
                         ("reconciled", "=", False), ("parent_state", "=", "posted")])
        ar_total = sum(abs(l.amount_residual) for l in ar)
        ar_overdue = sum(abs(l.amount_residual) for l in ar
                         if l.date_maturity and l.date_maturity < today)
        top_overdue = sorted([
            {"partner": l.partner_id.name or "Unknown",
             "amount": float(abs(l.amount_residual)),
             "days_late": (today - l.date_maturity).days}
            for l in ar if l.date_maturity and l.date_maturity < today
        ], key=lambda x: x["amount"], reverse=True)[:5]

        cash = 0.0
        for j in self.env["account.journal"].search([("type", "in", ["bank", "cash"])]):
            cash += getattr(j, "current_balance", 0.0) or 0.0

        payroll = 0.0
        if "hr.payslip" in self.env:
            ps = self.env["hr.payslip"].search([("date_from", ">=", month_start),
                                                ("state", "=", "done")])
            payroll = sum(ps.mapped("net_wage")) if ps else 0.0

        pipeline = 0.0
        if "crm.lead" in self.env:
            leads = self.env["crm.lead"].search([("active", "=", True),
                                                 ("type", "=", "opportunity")])
            pipeline = sum(leads.mapped("expected_revenue")) if leads else 0.0

        net = revenue - expenses
        margin = round(net / revenue * 100, 1) if revenue > 0 else 0.0
        runway = int(round(cash / (expenses / 30))) if expenses > 0 else 999
        payroll_pct = round(payroll / revenue * 100, 1) if revenue > 0 else 0.0

        return {
            "monthly_revenue": float(revenue),
            "monthly_expenses": float(expenses),
            "net_profit": float(net),
            "net_margin": margin,
            "cash": float(cash),
            "cash_runway": runway,
            "ar_total": float(ar_total),
            "ar_overdue": float(ar_overdue),
            "top_overdue": top_overdue,
            "payroll": float(payroll),
            "payroll_pct": payroll_pct,
            "pipeline": float(pipeline),
            "timestamp": datetime.now().isoformat(),
        }
