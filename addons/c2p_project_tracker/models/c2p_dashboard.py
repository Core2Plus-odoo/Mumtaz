from odoo import _, api, fields, models
from odoo.exceptions import AccessError

MANAGER_GROUP = "c2p_project_tracker.group_c2p_portfolio_manager"
MEMBER_GROUP = "c2p_project_tracker.group_c2p_delivery_member"

# Ranked by how much a delay costs, not by recency: a client blocker nobody is
# chasing outranks a report that is merely late.
ATTENTION_WEIGHTS = {
    "overdue_milestone": 100,
    "blocker": 90,
    "stale": 70,
    "receivable": 60,
    "no_deadline": 40,
    "commercials": 30,
}


class C2pDashboard(models.AbstractModel):
    """Server side of the two dashboards.

    An AbstractModel rather than methods on project.project: these are
    read-only aggregations for a UI, and keeping them apart makes the security
    boundary explicit — every entry point re-checks the group, because a client
    action's menu visibility is not an access control.
    """

    _name = "c2p.dashboard"
    _description = "C2P Tracker Dashboard Data"

    # ── Guards ───────────────────────────────────────────────────────────
    @api.model
    def _check_member(self):
        if not self.env.user.has_group(MEMBER_GROUP):
            raise AccessError(_("You do not have access to the Project Tracker."))

    @api.model
    def _may_see_money(self):
        return self.env.user.has_group(MANAGER_GROUP)

    # ── Portfolio dashboard ──────────────────────────────────────────────
    @api.model
    def portfolio_data(self, rag_filter=None, engagement_type=None,
                       account_manager_id=None):
        """Everything the portfolio dashboard renders, in one call.

        Commercial figures are omitted entirely — not zeroed — when the caller
        is not a Portfolio Manager, so a non-manager cannot infer them from the
        response shape.
        """
        self._check_member()
        if not self._may_see_money() and not self.env.user.has_group(MANAGER_GROUP):
            # The portfolio view is the Managing Partner's. A Delivery Lead has
            # the delivery dashboard instead.
            raise AccessError(_(
                "The Portfolio dashboard is restricted to Portfolio Managers. "
                "Use Project Tracker → Delivery."))

        domain = [("c2p_layer", "=", "portfolio")]
        if rag_filter:
            domain.append(("rag_status", "=", rag_filter))
        if engagement_type:
            domain.append(("engagement_type", "=", engagement_type))
        if account_manager_id:
            domain.append(("account_manager_id", "=", int(account_manager_id)))

        projects = self.env["project.project"].search(domain, order="rag_status, name")
        money = self._may_see_money()

        return {
            "currency": self.env.company.currency_id.symbol or "",
            "kpis": self._portfolio_kpis(projects, money),
            "rag_counts": self._rag_counts(projects),
            "rows": [self._portfolio_row(p, money) for p in projects],
            "roadmap": self._roadmap(projects),
            "attention": self._attention(projects, money),
            "trends": self._trends(projects),
            "filters": self._filter_options(),
            "synced_at": fields.Datetime.to_string(fields.Datetime.now()),
            "show_money": money,
        }

    @api.model
    def _portfolio_kpis(self, projects, money):
        kpis = {
            "engagements": len(projects),
            "progress_pct": round(
                sum(projects.mapped("progress_pct")) / len(projects), 1
            ) if projects else 0.0,
            "overdue_milestones": sum(projects.mapped("overdue_milestones_count")),
            "blockers": sum(projects.mapped("open_blockers_count")),
        }
        if money:
            kpis.update({
                "portfolio_value": sum(projects.mapped("contract_value")),
                "collected": sum(projects.mapped("amount_received_effective")),
                "outstanding": sum(projects.mapped("amount_outstanding")),
                "payable_to_solutions": sum(
                    projects.mapped("subcontract_outstanding")),
                "consultants_margin": sum(projects.mapped("consultants_margin")),
            })
        return kpis

    @api.model
    def _rag_counts(self, projects):
        counts = {"red": 0, "amber": 0, "green": 0, "grey": 0}
        for project in projects:
            counts[project.rag_status or "grey"] += 1
        return counts

    @api.model
    def _portfolio_row(self, project, money):
        """One engagement. `initials` stands in for a client logo, which Odoo
        does not reliably hold for a partner."""
        partner = project.partner_id
        initials = "".join(
            word[0] for word in (partner.name or project.name or "?").split()[:2]
        ).upper()
        row = {
            "id": project.id,
            "name": project.name,
            "client": partner.name or "",
            "initials": initials,
            "engagement_type": dict(
                project._fields["engagement_type"].selection
            ).get(project.engagement_type, ""),
            "rag": project.rag_status or "grey",
            "rag_reasons": (project.rag_reasons or "").splitlines(),
            "health_score": project.health_score,
            "progress_pct": round(project.progress_pct, 1),
            "current_milestone": project.current_milestone_id.name or "",
            "next_milestone_date": project.next_milestone_date and
            fields.Date.to_string(project.next_milestone_date) or "",
            "baseline_golive": project.baseline_golive_date and
            fields.Date.to_string(project.baseline_golive_date) or "",
            "forecast_golive": project.forecast_golive_date and
            fields.Date.to_string(project.forecast_golive_date) or "",
            "slippage_days": project.golive_slippage_days,
            "days_since_activity": project.days_since_activity,
            "blockers": project.open_blockers_count,
            "milestones": [
                {
                    "id": m.id,
                    "code": m.c2p_code or "",
                    "name": m.name,
                    "stage": m.stage_id.name or "",
                    "deadline": m.date_deadline and
                    fields.Date.to_string(m.date_deadline) or "",
                    "baseline": m.baseline_deadline and
                    fields.Date.to_string(m.baseline_deadline) or "",
                    "slippage_days": m.slippage_days,
                }
                for m in project._c2p_milestones()
            ],
        }
        if money:
            row.update({
                "contract_value": project.contract_value,
                "received": project.amount_received_effective,
                "outstanding": project.amount_outstanding,
                "commercials_missing": project.commercials_missing,
            })
        return row

    @api.model
    def _roadmap(self, projects):
        """One swimlane per engagement, with the date window to scale against.

        Only milestones that have a date can be placed; the rest are returned
        separately so the UI can say so rather than silently dropping them —
        which matters here, where every milestone currently lacks a deadline.
        """
        lanes, dates = [], []
        for project in projects:
            placed, undated = [], []
            for m in project._c2p_milestones():
                stage = (m.stage_id.name or "").strip().lower()
                entry = {
                    "id": m.id,
                    "code": m.c2p_code or "",
                    "name": m.name,
                    "stage": m.stage_id.name or "",
                    "status": ("done" if stage == "done" else
                               "blocked" if stage == "blocked" else
                               "review" if stage == "client review" else
                               "active" if stage == "in progress" else "pending"),
                    "deadline": m.date_deadline and
                    fields.Date.to_string(m.date_deadline) or "",
                    "baseline": m.baseline_deadline and
                    fields.Date.to_string(m.baseline_deadline) or "",
                }
                if m.date_deadline:
                    placed.append(entry)
                    dates.append(m.date_deadline)
                    if m.baseline_deadline:
                        dates.append(m.baseline_deadline)
                else:
                    undated.append(entry)
            lanes.append({
                "project_id": project.id,
                "name": project.name,
                "rag": project.rag_status or "grey",
                "milestones": placed,
                "undated_count": len(undated),
            })
        today = fields.Date.context_today(self)
        return {
            "lanes": lanes,
            "start": fields.Date.to_string(min(dates)) if dates else "",
            "end": fields.Date.to_string(max(dates)) if dates else "",
            "today": fields.Date.to_string(today),
            "has_dates": bool(dates),
        }

    @api.model
    def _attention(self, projects, money):
        """What needs a decision today, ranked by cost of delay."""
        today = fields.Date.context_today(self)
        items = []

        def add(kind, project, text, action=None):
            items.append({
                "kind": kind,
                "weight": ATTENTION_WEIGHTS[kind],
                "project_id": project.id,
                "project": project.name,
                "text": text,
                "action": action or "project",
            })

        for project in projects:
            for m in project._c2p_milestones():
                if m.date_deadline and m.date_deadline < today and \
                        (m.stage_id.name or "").strip().lower() != "done":
                    add("overdue_milestone", project,
                        _("%(code)s is %(days)s days overdue",
                          code=m.c2p_code or m.name,
                          days=(today - m.date_deadline).days),
                        action="milestones")
            blocker_age = project._c2p_oldest_blocker_days()
            if blocker_age >= 10:
                add("blocker", project,
                    _("A client blocker is %s days old", blocker_age),
                    action="blockers")
            if project.days_since_activity >= 7:
                add("stale", project,
                    _("No delivery activity for %s days",
                      project.days_since_activity))
            undated = len([m for m in project._c2p_milestones()
                           if not m.date_deadline
                           and (m.stage_id.name or "").strip().lower() != "done"])
            if undated:
                add("no_deadline", project,
                    _("%s open milestones have no deadline", undated),
                    action="milestones")
            if money:
                if project.commercials_missing:
                    add("commercials", project, _("Commercials are not recorded"))
                elif (project.contract_value
                      and project.progress_pct > 50.0
                      and project.amount_outstanding > project.contract_value / 2.0):
                    add("receivable", project,
                        _("Delivery is past halfway with most of the contract "
                          "still outstanding"))

        items.sort(key=lambda i: (-i["weight"], i["project"]))
        return items

    @api.model
    def _trends(self, projects):
        """Milestones completed per week and mean slippage, from the history.

        There is deliberately no money series: nothing records historical
        balances, so a collected-vs-outstanding trend would be invented. It
        needs a periodic snapshot before it can be drawn honestly.
        """
        if not projects:
            return {"weeks": [], "completed": [], "slippage": [], "money": None}

        History = self.env["c2p.milestone.history"]
        rows = History.search([("project_id", "in", projects.ids)],
                              order="change_date")
        weeks, completed, slippage_sum, slippage_n = [], {}, {}, {}
        for row in rows:
            week = row.change_date.date().isocalendar()
            key = f"{week[0]}-W{week[1]:02d}"
            if key not in completed:
                weeks.append(key)
                completed[key] = 0
                slippage_sum[key] = 0
                slippage_n[key] = 0
            if (row.new_stage_id.name or "").strip().lower() == "done":
                completed[key] += 1
            if row.old_deadline and row.new_deadline:
                slippage_sum[key] += (row.new_deadline - row.old_deadline).days
                slippage_n[key] += 1
        return {
            "weeks": weeks,
            "completed": [completed[w] for w in weeks],
            "slippage": [
                round(slippage_sum[w] / slippage_n[w], 1) if slippage_n[w] else 0
                for w in weeks
            ],
            "money": None,
        }

    @api.model
    def _filter_options(self):
        managers = self.env["project.project"].search(
            [("c2p_layer", "=", "portfolio"),
             ("account_manager_id", "!=", False)]).mapped("account_manager_id")
        return {
            "account_managers": [{"id": u.id, "name": u.name} for u in managers],
            "engagement_types": [
                {"value": value, "label": label} for value, label
                in self.env["project.project"]._fields["engagement_type"].selection
            ],
        }

    # ── Delivery dashboard ───────────────────────────────────────────────
    @api.model
    def delivery_data(self):
        """Team load and hygiene. Carries no commercial field at all."""
        self._check_member()
        today = fields.Date.context_today(self)
        Task = self.env["project.task"]

        base = [("project_id.c2p_layer", "=", "delivery")]
        open_tasks = Task.search(base + [("stage_id.fold", "=", False)])

        # Planned effort is allocated_hours on current Odoo, planned_hours on
        # older releases. Probe once rather than crash the whole dashboard on a
        # field rename.
        hours_field = next(
            (name for name in ("allocated_hours", "planned_hours")
             if name in Task._fields), None)

        load = {}
        for task in open_tasks:
            for user in (task.user_ids or Task.env["res.users"]):
                entry = load.setdefault(
                    user.id, {"name": user.name, "open": 0, "overdue": 0,
                              "hours": 0.0})
                entry["open"] += 1
                entry["hours"] += (getattr(task, hours_field, 0.0) or 0.0
                                   if hours_field else 0.0)
                if task.date_deadline and task.date_deadline < today:
                    entry["overdue"] += 1
        unassigned = len(open_tasks.filtered(lambda t: not t.user_ids))

        hygiene = [
            ("No assignee", [("user_ids", "=", False)]),
            ("No deadline", [("date_deadline", "=", False)]),
            ("No milestone", [("milestone_id", "=", False)]),
            ("Blocked without a reason", [("waiting_since", "!=", False),
                                          ("blocked_reason", "=", False)]),
        ]
        return {
            "team_load": sorted(load.values(), key=lambda e: -e["open"]),
            "unassigned": unassigned,
            "hygiene": [
                {"label": label,
                 "count": Task.search_count(base + extra),
                 "domain": base + extra}
                for label, extra in hygiene
            ],
            "milestones_without_deadline": self.env["project.milestone"].search_count(
                [("project_id.c2p_layer", "=", "delivery"),
                 ("deadline", "=", False)]),
            "due_this_week": Task.search_count(
                base + [("stage_id.fold", "=", False),
                        ("date_deadline", ">=", today),
                        ("date_deadline", "<=", fields.Date.add(today, days=7))]),
            "overdue": Task.search_count(
                base + [("stage_id.fold", "=", False),
                        ("date_deadline", "<", today)]),
            "synced_at": fields.Datetime.to_string(fields.Datetime.now()),
        }
