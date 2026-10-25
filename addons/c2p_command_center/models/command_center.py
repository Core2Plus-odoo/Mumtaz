from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

GROUP = "c2p_command_center.group_c2p_command_center"
BD_AUTHOR_LOGIN = "bd@core2plus.com"       # the outreach engine posts as this user
AGENT_BOARD_NAME = "AI Agents"             # matches "🤖 AI Agents · Work Board"
GST = timedelta(hours=4)                   # C2P works on Dubai time


class C2pCommandCenter(models.AbstractModel):
    """Read-only aggregation behind the Command Center client action.

    One RPC returns every section so the page renders in a single round trip.
    Each section is computed defensively: a missing app, field or record only
    blanks that section (with a note) instead of failing the whole page.
    """

    _name = "c2p.command.center"
    _description = "C2P Command Center data"

    # ── entry point ──────────────────────────────────────────────────────
    @api.model
    def get_data(self):
        if not self.env.user.has_group(GROUP):
            raise AccessError(_("You do not have access to the C2P Command Center."))
        now = fields.Datetime.now()
        local_now = now + GST
        day_start = datetime.combine(local_now.date(), time.min) - GST  # UTC
        ctx = {"now": now, "day_start": day_start, "local_today": local_now.date()}

        sections = {}
        for key, fn in [
            ("outreach", self._outreach),
            ("pipeline", self._pipeline),
            ("money", self._money),
            ("activities", self._activities),
            ("agents", self._agents),
            ("delivery", self._delivery),
            ("content", self._content),
            ("health", self._health),
        ]:
            try:
                sections[key] = fn(ctx)
            except Exception as exc:  # noqa: BLE001 — one broken card must not blank the page
                sections[key] = {"error": str(exc)}
        sections["generated_at"] = fields.Datetime.to_string(now)
        sections["local_time"] = local_now.strftime("%a %d %b %Y, %H:%M")
        sections["user_name"] = self.env.user.name
        sections["kpis"] = self._kpis(sections)
        return sections

    # ── helpers ──────────────────────────────────────────────────────────
    def _bd_partner(self):
        user = self.env["res.users"].sudo().search([("login", "=", BD_AUTHOR_LOGIN)], limit=1)
        return user.partner_id

    def _own_partner_ids(self):
        """Partners of every C2P group company — their invoices are intercompany, not receivables."""
        return self.env["res.company"].sudo().search([]).mapped("partner_id.commercial_partner_id").ids

    @staticmethod
    def _act(model, domain, name, views="list"):
        """A serialisable act_window the client opens on click."""
        return {"res_model": model, "domain": domain, "name": name, "views": views}

    # ── outreach (BD engine) ─────────────────────────────────────────────
    def _outreach(self, ctx):
        Msg = self.env["mail.message"].sudo()
        Lead = self.env["crm.lead"].sudo().with_context(active_test=False)
        bd = self._bd_partner()
        now, day_start = ctx["now"], ctx["day_start"]
        since14 = day_start - timedelta(days=13)
        sent_dom = [("model", "=", "crm.lead"), ("author_id", "=", bd.id),
                    ("message_type", "=", "comment"), ("subject", "!=", False),
                    ("date", ">=", since14)]
        sent = Msg.search_read(sent_dom, ["date", "subject"])
        reply_dom = [("model", "=", "crm.lead"), ("message_type", "=", "email"),
                     ("date", ">=", since14), ("author_id", "!=", bd.id)]
        replies = Msg.search_read(reply_dom, ["date", "res_id", "email_from", "subject"])

        series = []
        for i in range(14):
            d0 = since14 + timedelta(days=i)
            d1 = d0 + timedelta(days=1)
            day_sent = [m for m in sent if d0 <= m["date"] < d1]
            series.append({
                "label": (d0 + GST).strftime("%d %b"),
                "first": sum(1 for m in day_sent if not (m["subject"] or "").startswith("Re:")),
                "followup": sum(1 for m in day_sent if (m["subject"] or "").startswith("Re:")),
                "replies": sum(1 for r in replies if d0 <= r["date"] < d1),
            })
        today = series[-1]
        sent7 = sum(s["first"] + s["followup"] for s in series[-7:])

        has_bd = "x_bd_status" in Lead._fields
        queued = Lead.search_count([("x_bd_status", "=", "queued")]) if has_bd else 0
        due = Lead.search_count([("x_bd_status", "=", "active"),
                                 ("x_bd_next", "<=", ctx["local_today"])]) if has_bd else 0
        in_seq = Lead.search_count([("x_bd_status", "=", "active")]) if has_bd else 0
        fails = self.env["mail.mail"].sudo().search_count(
            [("state", "=", "exception"), ("create_date", ">=", now - timedelta(hours=24))])
        P = self.env["ir.config_parameter"].sudo()

        recent_replies = []
        for r in sorted(replies, key=lambda r: r["date"], reverse=True)[:8]:
            lead = Lead.browse(r["res_id"])
            recent_replies.append({
                "id": lead.id, "name": lead.name or "", "from": r["email_from"] or "",
                "date": (r["date"] + GST).strftime("%d %b %H:%M"),
            })
        return {
            "series": series,
            "today_sent": today["first"] + today["followup"],
            "today_first": today["first"], "today_followup": today["followup"],
            "sent7": sent7,
            "replies14": len(replies),
            "queued": queued, "due": due, "in_sequence": in_seq,
            "failures24": fails,
            "daily_cap": P.get_param("c2p_bd.daily_cap") or "",
            "max_followups": P.get_param("c2p_bd.max_followups") or "",
            "recent_replies": recent_replies,
            "act_queued": self._act("crm.lead", [("x_bd_status", "=", "queued")], "Queued leads"),
            "act_due": self._act("crm.lead", [("x_bd_status", "=", "active"),
                                              ("x_bd_next", "<=", str(ctx["local_today"]))],
                                 "Follow-ups due"),
            "act_fail": self._act("mail.mail", [("state", "=", "exception"),
                                                ("create_date", ">=", fields.Datetime.to_string(now - timedelta(hours=24)))],
                                  "Failed emails (24h)"),
        }

    # ── pipeline ─────────────────────────────────────────────────────────
    def _pipeline(self, ctx):
        Lead = self.env["crm.lead"].sudo()
        Stage = self.env["crm.stage"].sudo()
        stages = Stage.search([], order="sequence")
        early = stages.filtered(lambda s: s.sequence <= 1).ids          # New, Contacted
        closed = stages.filtered(lambda s: s.is_won or s.fold).ids
        lost_like = stages.filtered(lambda s: s.name.lower() in ("lost", "no response", "project onhold")).ids
        skip = set(early) | set(closed) | set(lost_like)
        open_stages = [s for s in stages if s.id not in skip]
        now = ctx["now"]

        columns = []
        total = 0.0
        for st in open_stages:
            leads = Lead.search([("stage_id", "=", st.id), ("type", "in", ("lead", "opportunity"))],
                                order="expected_revenue desc, write_date desc")
            rows = []
            for l in leads:
                idle = (now - l.write_date).days if l.write_date else 0
                rows.append({
                    "id": l.id, "name": l.name, "value": l.expected_revenue or 0.0,
                    "idle_days": idle,
                    "next": l.activity_summary or "",
                    "next_date": l.activity_date_deadline and fields.Date.to_string(l.activity_date_deadline) or "",
                    "overdue": bool(l.activity_date_deadline and l.activity_date_deadline < ctx["local_today"]),
                    "stale": idle >= 14,
                })
                total += l.expected_revenue or 0.0
            columns.append({"stage": st.name, "count": len(rows),
                            "value": sum(r["value"] for r in rows), "rows": rows})

        won_stage = stages.filtered("is_won")
        month_start = ctx["local_today"].replace(day=1)
        won = Lead.search([("stage_id", "in", won_stage.ids),
                           ("date_closed", ">=", fields.Date.to_string(month_start))]) if won_stage else Lead
        return {
            "columns": columns,
            "open_value": total,
            "open_count": sum(c["count"] for c in columns),
            "won_month_count": len(won),
            "won_month_value": sum(won.mapped("expected_revenue")),
            "currency": self.env.company.currency_id.symbol or "AED",
        }

    # ── money ────────────────────────────────────────────────────────────
    def _money(self, ctx):
        Move = self.env["account.move"].sudo()
        today = ctx["local_today"]
        own = self._own_partner_ids()
        unpaid = Move.search([("move_type", "=", "out_invoice"), ("state", "=", "posted"),
                              ("payment_state", "in", ("not_paid", "partial")),
                              ("commercial_partner_id", "not in", own)],
                             order="invoice_date_due")
        rows = []
        for m in unpaid:
            due = m.invoice_date_due
            rows.append({
                "id": m.id, "name": m.name, "partner": m.partner_id.display_name,
                "amount": m.amount_residual, "currency": m.currency_id.name,
                "company_ccy_amount": abs(m.amount_residual_signed),
                "due": due and fields.Date.to_string(due) or "",
                "days_overdue": (today - due).days if due and due < today else 0,
            })
        month_start = today.replace(day=1)
        paid_month = Move.search([("move_type", "=", "out_invoice"), ("state", "=", "posted"),
                                  ("payment_state", "in", ("paid", "in_payment")),
                                  ("commercial_partner_id", "not in", own),
                                  ("invoice_date", ">=", fields.Date.to_string(month_start))])
        draft_bills = Move.search_count([("move_type", "in", ("in_invoice", "out_invoice")),
                                         ("state", "=", "draft")])
        return {
            "rows": rows,
            "receivable": sum(r["company_ccy_amount"] for r in rows),
            "overdue_count": sum(1 for r in rows if r["days_overdue"] > 0),
            "invoiced_paid_month": sum(abs(x) for x in paid_month.mapped("amount_total_signed")),
            "drafts": draft_bills,
            "currency": self.env.company.currency_id.symbol or "AED",
            "act_unpaid": self._act("account.move", [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
                                                     ("payment_state", "in", ["not_paid", "partial"]),
                                                     ("commercial_partner_id", "not in", own)],
                                    "Unpaid customer invoices"),
            "act_drafts": self._act("account.move", [("state", "=", "draft"),
                                                     ("move_type", "in", ["in_invoice", "out_invoice"])],
                                    "Draft invoices and bills"),
        }

    # ── my activities ────────────────────────────────────────────────────
    def _activities(self, ctx):
        acts = self.env["mail.activity"].sudo().search(
            [("user_id", "=", self.env.uid)], order="date_deadline, id")
        today = ctx["local_today"]
        rows = []
        for a in acts:
            rows.append({
                "id": a.id, "res_model": a.res_model, "res_id": a.res_id,
                "record": a.res_name or "", "summary": a.summary or a.activity_type_id.name or "",
                "type": a.activity_type_id.name or "",
                "date": fields.Date.to_string(a.date_deadline),
                "state": "overdue" if a.date_deadline < today else ("today" if a.date_deadline == today else "planned"),
                "model_label": self.env["ir.model"]._get(a.res_model).name if a.res_model else "",
            })
        return {
            "rows": rows,
            "overdue": sum(1 for r in rows if r["state"] == "overdue"),
            "today": sum(1 for r in rows if r["state"] == "today"),
            "planned": sum(1 for r in rows if r["state"] == "planned"),
        }

    # ── AI agents work board ─────────────────────────────────────────────
    def _agents(self, ctx):
        Project = self.env["project.project"].sudo()
        board = Project.search([("name", "ilike", AGENT_BOARD_NAME)], limit=1)
        if not board:
            return {"missing": True}
        Task = self.env["project.task"].sudo()
        tasks = Task.search([("project_id", "=", board.id)])
        now = ctx["now"]
        stage_names = [s.name for s in board.type_ids.sorted("sequence")]
        agents = {}
        for t in tasks:
            tag = next((g.name.replace("Agent: ", "") for g in t.tag_ids if g.name.startswith("Agent: ")), "Unassigned")
            a = agents.setdefault(tag, {"agent": tag, "by_stage": {}, "overdue": 0, "next": None})
            st = t.stage_id.name or ""
            a["by_stage"][st] = a["by_stage"].get(st, 0) + 1
            open_stage = not t.stage_id.fold and st not in ("Done",)
            if open_stage and t.date_deadline and t.date_deadline < now and st in ("Ready", "In progress"):
                a["overdue"] += 1
            if open_stage and st in ("Ready", "In progress") and t.date_deadline:
                if not a["next"] or t.date_deadline < a["next"][1]:
                    a["next"] = (t.name, t.date_deadline)
        rows = []
        for a in sorted(agents.values(), key=lambda a: a["agent"]):
            nxt = a.pop("next")
            a["next_name"] = nxt[0] if nxt else ""
            a["next_date"] = (nxt[1] + GST).strftime("%d %b") if nxt else ""
            rows.append(a)
        review = tasks.filtered(lambda t: t.stage_id.name.startswith("Review"))
        return {
            "board_id": board.id,
            "stages": stage_names,
            "rows": rows,
            "review": [{"id": t.id, "name": t.name, "url": getattr(t, "x_output_url", "") or "",
                        "since": (now - t.date_last_stage_update).days if t.date_last_stage_update else 0}
                       for t in review],
            "overdue_total": sum(r["overdue"] for r in rows),
            "blocked": len(tasks.filtered(lambda t: t.stage_id.name == "Blocked")),
        }

    # ── client delivery ──────────────────────────────────────────────────
    def _delivery(self, ctx):
        Project = self.env["project.project"].sudo().with_context(allowed_company_ids=self.env.user.company_ids.ids)
        # Client projects only: a customer is set and it is not one of our own companies
        # (excludes templates such as "Web & Digital Delivery" and internal projects).
        projects = Project.search([("partner_id", "!=", False),
                                   ("partner_id.commercial_partner_id", "not in", self._own_partner_ids())],
                                  order="name")
        Task = self.env["project.task"].sudo()
        now = ctx["now"]
        week = now + timedelta(days=7)
        rows = []
        for p in projects:
            open_t = Task.search([("project_id", "=", p.id), "|", ("stage_id", "=", False), ("stage_id.fold", "=", False)])
            overdue = open_t.filtered(lambda t: t.date_deadline and t.date_deadline < now)
            due7 = open_t.filtered(lambda t: t.date_deadline and now <= t.date_deadline <= week)
            last = max(open_t.mapped("write_date") or [p.write_date])
            rows.append({
                "id": p.id, "name": p.name, "company": p.company_id.name or "",
                "open": len(open_t), "overdue": len(overdue), "due7": len(due7),
                "idle_days": (now - last).days if last else 0,
                "rag": "red" if overdue else ("amber" if due7 or (now - last).days >= 7 else "green"),
            })
        return {"rows": rows, "overdue_total": sum(r["overdue"] for r in rows)}

    # ── content ──────────────────────────────────────────────────────────
    def _content(self, ctx):
        Post = self.env["blog.post"].sudo()
        since30 = ctx["now"] - timedelta(days=30)
        published = Post.search([("is_published", "=", True)], order="post_date desc", limit=5)
        return {
            "published30": Post.search_count([("is_published", "=", True), ("post_date", ">=", since30)]),
            "drafts": Post.search_count([("is_published", "=", False)]),
            "total": Post.search_count([]),
            "latest": [{"id": p.id, "name": p.name,
                        "date": p.post_date and (p.post_date + GST).strftime("%d %b %Y") or "",
                        "url": p.website_url} for p in published],
            "last_days_ago": (ctx["now"] - published[0].post_date).days if published and published[0].post_date else None,
        }

    # ── system health ────────────────────────────────────────────────────
    def _health(self, ctx):
        Cron = self.env["ir.cron"].sudo().with_context(active_test=False)
        crons = Cron.search(["|", "|", ("name", "ilike", "C2P"), ("name", "ilike", "AI Agents"),
                             ("name", "ilike", "BD Engine")], order="name")
        now = ctx["now"]
        rows = []
        for c in crons:
            hours = (now - c.lastcall).total_seconds() / 3600 if c.lastcall else None
            period_h = {"minutes": c.interval_number / 60.0, "hours": c.interval_number,
                        "days": 24 * c.interval_number, "weeks": 168 * c.interval_number,
                        "months": 720 * c.interval_number}.get(c.interval_type, 24)
            late = c.active and hours is not None and hours > max(period_h * 2.5, 72 if period_h >= 24 else 6)
            rows.append({
                "id": c.id, "name": c.name, "active": c.active,
                "last": c.lastcall and (c.lastcall + GST).strftime("%d %b %H:%M") or "never",
                "next": c.nextcall and (c.nextcall + GST).strftime("%d %b %H:%M") or "",
                "status": "off" if not c.active else ("late" if late else "ok"),
            })
        return {"crons": rows, "problems": sum(1 for r in rows if r["status"] != "ok")}

    # ── headline KPIs ────────────────────────────────────────────────────
    @api.model
    def _kpis(self, s):
        def g(sec, key, default=0):
            return (s.get(sec) or {}).get(key, default)
        return [
            {"label": "Emails today", "value": g("outreach", "today_sent"),
             "sub": "%s first · %s follow-up" % (g("outreach", "today_first"), g("outreach", "today_followup")),
             "tone": "info", "section": "outreach"},
            {"label": "Replies (14 days)", "value": g("outreach", "replies14"),
             "sub": "%s emails sent in 7 days" % g("outreach", "sent7"), "tone": "good" if g("outreach", "replies14") else "muted",
             "section": "outreach"},
            {"label": "Open pipeline", "value": g("pipeline", "open_value"), "money": True,
             "sub": "%s deals past Contacted" % g("pipeline", "open_count"), "tone": "info", "section": "pipeline"},
            {"label": "Receivable", "value": g("money", "receivable"), "money": True,
             "sub": "%s invoices overdue" % g("money", "overdue_count"),
             "tone": "bad" if g("money", "overdue_count") else "info", "section": "money"},
            {"label": "My overdue activities", "value": g("activities", "overdue"),
             "sub": "%s due today" % g("activities", "today"),
             "tone": "bad" if g("activities", "overdue") else "good", "section": "activities"},
            {"label": "AI work to review", "value": len(g("agents", "review", [])),
             "sub": "%s overdue · %s blocked" % (g("agents", "overdue_total"), g("agents", "blocked")),
             "tone": "warn" if g("agents", "review", []) else "muted", "section": "agents"},
            {"label": "Delivery overdue", "value": g("delivery", "overdue_total"),
             "sub": "client project tasks", "tone": "bad" if g("delivery", "overdue_total") else "good",
             "section": "delivery"},
            {"label": "System health", "value": g("health", "problems"),
             "sub": "jobs late or off", "tone": "bad" if g("health", "problems") else "good", "section": "health"},
        ]
