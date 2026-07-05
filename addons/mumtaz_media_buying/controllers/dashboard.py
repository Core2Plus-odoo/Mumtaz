# -*- coding: utf-8 -*-
"""Live data feed for the standalone CEO dashboard (mumtaz_ceo_dashboard).

The dashboard JS calls /mumtaz_ceo_dashboard/data at load time. When this
module is installed and holds at least one active plan, it answers with a
payload shaped exactly like the dashboard's built-in sample data; otherwise
it returns {"live": False} and the dashboard keeps its illustrative figures.
"""
from datetime import date

from odoo import fields, http
from odoo.http import request

# dashboard buckets: radio rolls up into tv
CHANNEL_BUCKET = {
    "tv": "tv", "radio": "tv",
    "print": "print", "digital": "digital", "ooh": "ooh",
}
BUCKETS = ("tv", "digital", "print", "ooh")
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _month_count(d1, d2):
    return (d2.year - d1.year) * 12 + (d2.month - d1.month) + 1


def _elapsed_fraction(d1, d2, today):
    """How much of [d1, d2] has elapsed as of today, clamped to 0..1."""
    if today <= d1:
        return 0.0
    if today >= d2:
        return 1.0
    total = (d2 - d1).days or 1
    return (today - d1).days / total


class CeoDashboardData(http.Controller):

    @http.route("/mumtaz_ceo_dashboard/data", type="jsonrpc", auth="user")
    def dashboard_data(self):
        env = request.env
        today = fields.Date.context_today(env.user)
        year = today.year
        # The dashboard renders monetary values in millions (e.g. 114 -> "114m",
        # 1840 -> "1.84B"), so convert raw currency amounts to millions here.
        def m(x):
            return round(x / 1_000_000.0, 2)
        plans = env["media.plan"].search([
            ("state", "in", ["approved", "running", "done"]),
            ("date_from", "<=", date(year, 12, 31)),
            ("date_to", ">=", date(year, 1, 1)),
        ])
        if not plans:
            return {"live": False}

        n_months = today.month
        months = MONTH_LABELS[:n_months]
        billings = {b: [0.0] * n_months for b in BUCKETS}
        revenue = [0.0] * n_months

        # Spread each plan's money evenly across its campaign months, then
        # keep the slices that fall inside the current fiscal year.
        for plan in plans:
            span = _month_count(plan.date_from, plan.date_to)
            rev_share = plan.net_revenue / span
            for i in range(span):
                m_year = plan.date_from.year + (plan.date_from.month - 1 + i) // 12
                m_month = (plan.date_from.month - 1 + i) % 12
                if m_year != year or m_month >= n_months:
                    continue
                revenue[m_month] += rev_share
            for line in plan.line_ids:
                bucket = CHANNEL_BUCKET.get(line.channel, "digital")
                cost_share = line.net_cost / span
                for i in range(span):
                    m_year = (plan.date_from.year
                              + (plan.date_from.month - 1 + i) // 12)
                    m_month = (plan.date_from.month - 1 + i) % 12
                    if m_year != year or m_month >= n_months:
                        continue
                    billings[bucket][m_month] += cost_share

        # top clients (by client billing) and vendors (by media cost)
        client_totals = {}
        for plan in plans:
            client_totals.setdefault(plan.client_id, 0.0)
            client_totals[plan.client_id] += plan.client_total
        vendor_totals = {}
        for line in plans.mapped("line_ids"):
            vendor = line.outlet_id.vendor_id
            vendor_totals.setdefault(vendor, 0.0)
            vendor_totals[vendor] += line.net_cost
        top = lambda d: [  # noqa: E731
            {"nm": p.name, "v": m(v)}
            for p, v in sorted(d.items(), key=lambda kv: -kv[1])[:6]
        ]

        # pacing per channel: planned = full cost, spent = elapsed share
        pace_labels = {"tv": "TV & Radio", "digital": "Digital",
                       "print": "Print", "ooh": "OOH"}
        pacing_map = {b: {"plan": 0.0, "spent": 0.0} for b in BUCKETS}
        for plan in plans:
            frac = 1.0 if plan.state == "done" else _elapsed_fraction(
                plan.date_from, plan.date_to, today)
            for line in plan.line_ids:
                bucket = CHANNEL_BUCKET.get(line.channel, "digital")
                pacing_map[bucket]["plan"] += line.net_cost
                pacing_map[bucket]["spent"] += line.net_cost * frac
        pacing = [
            {"nm": pace_labels[b], "ch": b,
             "plan": m(v["plan"]), "spent": m(v["spent"])}
            for b, v in pacing_map.items() if v["plan"]
        ]

        # campaign watchlist: active plans, flagged by pace vs elapsed time
        campaigns = []
        watch = plans.filtered(lambda p: p.state in ("approved", "running"))
        for plan in sorted(watch, key=lambda p: -(p.budget or p.client_total)):
            budget = plan.budget or plan.client_total
            frac = _elapsed_fraction(plan.date_from, plan.date_to, today)
            spent = plan.media_cost * frac
            pace_pct = spent / budget * 100 if budget else 0.0
            elapsed_pct = frac * 100
            if pace_pct > 100:
                status, label = "serious", "Overpacing"
            elif elapsed_pct > 50 and pace_pct < 35:
                status, label = "warning", "At risk"
            elif pace_pct < elapsed_pct - 15:
                status, label = "warning", "Underpacing"
            else:
                status, label = "good", "On track"
            channels = sorted({
                CHANNEL_BUCKET.get(c, "digital")
                for c in plan.line_ids.mapped("channel")})
            campaigns.append({
                "nm": plan.campaign, "cl": plan.client_id.name,
                "ch": channels, "budget": m(budget),
                "spent": m(spent),
                "margin": round(plan.margin_percent, 1),
                "status": status, "label": label,
            })
        campaigns = campaigns[:8]

        # receivables ageing from posted customer invoices
        ageing = [
            {"nm": "Current", "v": 0.0, "c": "--cd-good"},
            {"nm": "1–30 days", "v": 0.0, "c": "--cd-ch-tv"},
            {"nm": "31–60 days", "v": 0.0, "c": "--cd-warning"},
            {"nm": "60+ days", "v": 0.0, "c": "--cd-critical"},
        ]
        receivable = payable = 0.0
        try:
            Move = env["account.move"]
        except KeyError:
            Move = None
        if Move is not None:
            inv = Move.search([
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("amount_residual", ">", 0),
            ])
            for move in inv:
                residual = move.amount_residual
                receivable += residual
                due = move.invoice_date_due or move.invoice_date or today
                overdue = (today - due).days
                idx = (0 if overdue <= 0 else
                       1 if overdue <= 30 else
                       2 if overdue <= 60 else 3)
                ageing[idx]["v"] += residual
            bills = Move.search([
                ("move_type", "=", "in_invoice"),
                ("state", "=", "posted"),
                ("amount_residual", ">", 0),
            ])
            payable = sum(bills.mapped("amount_residual"))
        for slot in ageing:
            slot["v"] = m(slot["v"])

        total_billed = sum(client_totals.values())
        days_elapsed = max((today - date(year, 1, 1)).days, 1)
        dso = round(receivable / (total_billed / days_elapsed)) \
            if total_billed else 0

        return {
            "live": True,
            "db": env.cr.dbname,
            "currency": env.company.currency_id.name or "PKR",
            "as_of": fields.Date.to_string(today),
            "months": months,
            "billings": {b: [m(v) for v in billings[b]]
                         for b in BUCKETS},
            "revenue": [m(v) for v in revenue],
            "clients": top(client_totals),
            "vendors": top(vendor_totals),
            "pacing": pacing,
            "campaigns": campaigns,
            "ageing": ageing,
            "kpis": {
                "active_campaigns": len(watch),
                "clients_live": len(client_totals),
                "receivables": m(receivable),
                "payables": m(payable),
                "dso": dso,
            },
        }
