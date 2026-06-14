import json

from odoo import api, fields, models


class ZakiBoardPack(models.TransientModel):
    _name = "zaki.board.pack"
    _description = "ZAKI Board Pack — one-time PDF report wizard"

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    report_date = fields.Date(default=fields.Date.today, readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)

    monthly_revenue = fields.Monetary(string="Monthly Revenue", currency_field="currency_id")
    monthly_expenses = fields.Monetary(string="Monthly Expenses", currency_field="currency_id")
    net_profit = fields.Monetary(string="Net Profit", currency_field="currency_id")
    net_margin = fields.Float(string="Net Margin (%)", digits=(5, 1))

    cash = fields.Monetary(string="Cash & Bank", currency_field="currency_id")
    cash_runway = fields.Integer(string="Cash Runway (days)")

    ar_total = fields.Monetary(string="Total Receivables", currency_field="currency_id")
    ar_overdue = fields.Monetary(string="Overdue Receivables", currency_field="currency_id")
    _top_overdue_json = fields.Text(string="_top_overdue_json")

    payroll = fields.Monetary(string="Payroll MTD", currency_field="currency_id")
    payroll_pct = fields.Float(string="Payroll % Revenue", digits=(5, 1))
    pipeline = fields.Monetary(string="CRM Pipeline", currency_field="currency_id")

    @api.model
    def action_open(self):
        wizard = self.create({})
        snap = self.env["zaki.connector"].get_snapshot()
        wizard.write({
            "monthly_revenue":  snap.get("monthly_revenue", 0),
            "monthly_expenses": snap.get("monthly_expenses", 0),
            "net_profit":       snap.get("net_profit", 0),
            "net_margin":       snap.get("net_margin", 0),
            "cash":             snap.get("cash", 0),
            "cash_runway":      snap.get("cash_runway", 0),
            "ar_total":         snap.get("ar_total", 0),
            "ar_overdue":       snap.get("ar_overdue", 0),
            "_top_overdue_json": json.dumps(snap.get("top_overdue", [])),
            "payroll":          snap.get("payroll", 0),
            "payroll_pct":      snap.get("payroll_pct", 0),
            "pipeline":         snap.get("pipeline", 0),
        })
        return self.env.ref("mumtaz_zaki.action_report_board_pack").report_action(wizard)

    def get_top_overdue(self):
        """Called from QWeb template."""
        try:
            return json.loads(self._top_overdue_json or "[]")
        except Exception:
            return []
