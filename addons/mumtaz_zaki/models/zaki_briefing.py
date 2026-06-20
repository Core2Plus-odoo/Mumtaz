from odoo import api, fields, models


class ZakiBriefingConfig(models.Model):
    _name = "zaki.briefing.config"
    _description = "ZAKI Morning Briefing Configuration"
    _rec_name = "company_id"

    company_id = fields.Many2one(
        "res.company", required=True, ondelete="cascade",
        default=lambda self: self.env.company,
    )
    enabled = fields.Boolean(string="Send Morning Briefings", default=False)
    send_hour = fields.Integer(
        string="Send At (hour, UTC)", default=6,
        help="Hour of day (UTC) to send the briefing. E.g. 6 = 06:00 UTC.",
    )
    recipient_ids = fields.Many2many(
        "res.users", string="Recipients",
        domain=[("share", "=", False), ("active", "=", True)],
        help="Users who will receive the daily briefing email.",
    )

    _sql_company_unique = models.Constraint(
        "unique(company_id)",
        "Each company can only have one briefing configuration.",
    )


class ZakiBriefingLog(models.Model):
    _name = "zaki.briefing.log"
    _description = "ZAKI Morning Briefing Log"
    _order = "sent_at desc"

    company_id = fields.Many2one("res.company", readonly=True)
    sent_at = fields.Datetime(readonly=True, default=fields.Datetime.now)
    recipient_count = fields.Integer(readonly=True)
    status = fields.Selection(
        [("sent", "Sent"), ("error", "Error")],
        default="sent", readonly=True,
    )
    error_message = fields.Text(readonly=True)

    @api.model
    def _send_morning_briefings(self):
        """Cron entry point: send daily briefing to all enabled companies."""
        now_hour = fields.Datetime.now().hour
        configs = self.env["zaki.briefing.config"].search([
            ("enabled", "=", True),
            ("send_hour", "=", now_hour),
        ])
        for cfg in configs:
            self.with_company(cfg.company_id)._dispatch_briefing(cfg)

    @api.model
    def _dispatch_briefing(self, cfg):
        try:
            snap = self.env["zaki.connector"].with_company(cfg.company_id).get_snapshot()
            body = self._render_briefing_html(snap, cfg.company_id)
            users_model = self.env["res.users"]
            # Odoo 19 renamed res.users.groups_id -> group_ids.
            gfield = "group_ids" if "group_ids" in users_model._fields else "groups_id"
            recipients = cfg.recipient_ids or users_model.search([
                ("share", "=", False), ("active", "=", True),
                ("company_id", "=", cfg.company_id.id),
                (gfield, "in", [self.env.ref("account.group_account_manager").id]),
            ])
            emails = recipients.mapped("email")
            emails = [e for e in emails if e]
            if not emails:
                return
            mail = self.env["mail.mail"].sudo().create({
                "subject": f"ZAKI Morning Briefing — {fields.Date.today().strftime('%d %b %Y')}",
                "body_html": body,
                "email_to": ",".join(emails),
                "auto_delete": True,
            })
            mail.send()
            self.sudo().create({
                "company_id": cfg.company_id.id,
                "recipient_count": len(emails),
                "status": "sent",
            })
        except Exception as exc:
            self.sudo().create({
                "company_id": cfg.company_id.id,
                "recipient_count": 0,
                "status": "error",
                "error_message": str(exc),
            })

    @api.model
    def _render_briefing_html(self, snap, company):
        cur = company.currency_id.symbol or ""
        rev = snap.get("monthly_revenue", 0)
        exp = snap.get("monthly_expenses", 0)
        net = snap.get("net_profit", 0)
        margin = snap.get("net_margin", 0)
        cash = snap.get("cash", 0)
        runway = snap.get("cash_runway", 0)
        ar_total = snap.get("ar_total", 0)
        ar_overdue = snap.get("ar_overdue", 0)
        payroll = snap.get("payroll", 0)
        pipeline = snap.get("pipeline", 0)
        top_overdue = snap.get("top_overdue", [])
        date_str = fields.Date.today().strftime("%A, %d %B %Y")
        net_color = "#27ae60" if net >= 0 else "#e74c3c"

        from markupsafe import escape as _esc
        overdue_rows = "".join(
            f"<tr><td style='padding:4px 8px'>{_esc(r['partner'])}</td>"
            f"<td style='padding:4px 8px;text-align:right'>{_esc(cur)}{r['amount']:,.0f}</td>"
            f"<td style='padding:4px 8px;text-align:right'>{int(r['days_late'])}d</td></tr>"
            for r in top_overdue
        ) if top_overdue else "<tr><td colspan='3' style='padding:4px 8px;color:#888'>No overdue invoices</td></tr>"

        return f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#333">
  <div style="background:#1a1a2e;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0">
    <h1 style="margin:0;font-size:22px">🤖 ZAKI Morning Briefing</h1>
    <p style="margin:4px 0 0;opacity:0.75;font-size:14px">{company.name} · {date_str}</p>
  </div>

  <div style="background:#f9f9f9;padding:20px 24px;border:1px solid #e0e0e0;border-top:none">

    <h3 style="margin:0 0 12px;color:#555;font-size:13px;text-transform:uppercase;letter-spacing:.5px">📊 This Month's P&L</h3>
    <table style="width:100%;border-collapse:collapse">
      <tr>
        <td style="padding:8px;background:#fff;border:1px solid #eee;border-radius:4px;width:33%">
          <div style="font-size:11px;color:#888">Revenue</div>
          <div style="font-size:20px;font-weight:bold;color:#27ae60">{cur}{rev:,.0f}</div>
        </td>
        <td style="width:10px"></td>
        <td style="padding:8px;background:#fff;border:1px solid #eee;border-radius:4px;width:33%">
          <div style="font-size:11px;color:#888">Expenses</div>
          <div style="font-size:20px;font-weight:bold;color:#e74c3c">{cur}{exp:,.0f}</div>
        </td>
        <td style="width:10px"></td>
        <td style="padding:8px;background:#fff;border:1px solid #eee;border-radius:4px;width:33%">
          <div style="font-size:11px;color:#888">Net Profit ({margin:.1f}%)</div>
          <div style="font-size:20px;font-weight:bold;color:{net_color}">{cur}{net:,.0f}</div>
        </td>
      </tr>
    </table>

    <h3 style="margin:20px 0 12px;color:#555;font-size:13px;text-transform:uppercase;letter-spacing:.5px">💰 Cash & Liquidity</h3>
    <table style="width:100%;border-collapse:collapse">
      <tr>
        <td style="padding:8px;background:#fff;border:1px solid #eee;border-radius:4px;width:48%">
          <div style="font-size:11px;color:#888">Cash & Bank</div>
          <div style="font-size:20px;font-weight:bold">{cur}{cash:,.0f}</div>
        </td>
        <td style="width:4%"></td>
        <td style="padding:8px;background:#fff;border:1px solid #eee;border-radius:4px;width:48%">
          <div style="font-size:11px;color:#888">Cash Runway</div>
          <div style="font-size:20px;font-weight:bold">{'∞' if runway >= 999 else str(runway) + ' days'}</div>
        </td>
      </tr>
    </table>

    <h3 style="margin:20px 0 12px;color:#555;font-size:13px;text-transform:uppercase;letter-spacing:.5px">📋 Receivables</h3>
    <p style="margin:0 0 8px">Total AR: <strong>{cur}{ar_total:,.0f}</strong> · Overdue: <strong style="color:#e74c3c">{cur}{ar_overdue:,.0f}</strong></p>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead><tr style="background:#f0f0f0">
        <th style="padding:4px 8px;text-align:left">Partner</th>
        <th style="padding:4px 8px;text-align:right">Amount</th>
        <th style="padding:4px 8px;text-align:right">Days Late</th>
      </tr></thead>
      <tbody>{overdue_rows}</tbody>
    </table>

    <h3 style="margin:20px 0 12px;color:#555;font-size:13px;text-transform:uppercase;letter-spacing:.5px">📈 Other</h3>
    <p style="margin:0">Payroll MTD: <strong>{cur}{payroll:,.0f}</strong> &nbsp;|&nbsp; CRM Pipeline: <strong>{cur}{pipeline:,.0f}</strong></p>
  </div>

  <div style="background:#f0f0f0;padding:10px 24px;border-radius:0 0 8px 8px;font-size:11px;color:#888;text-align:center">
    Sent by ZAKI AI CFO · Mumtaz ERP
  </div>
</div>"""
