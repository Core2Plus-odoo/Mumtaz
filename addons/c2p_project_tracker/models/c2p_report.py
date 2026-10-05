from odoo import fields, models
from odoo.tools import format_amount

RAG_LABEL = {"red": "Red", "amber": "Amber", "green": "Green", "grey": "No data"}


class ProjectProjectReport(models.Model):
    """Report payloads.

    QWeb's evaluation context is deliberately narrow — no `str()`, no
    formatting helpers — so every value these return is already a display
    string. Doing the formatting here also keeps currency rendering consistent
    with the rest of Odoo.
    """

    _inherit = "project.project"

    def _c2p_report_payload(self):
        """Aggregate for the executive summary.

        Called on whatever recordset the report was launched from: the
        portfolio projects among them, or all of them when the selection
        contains none (printing from a delivery project should still produce
        the portfolio view rather than an empty page).
        """
        projects = self.filtered(lambda p: p.c2p_layer == "portfolio")
        if not projects:
            projects = self.search([("c2p_layer", "=", "portfolio")])

        show_money = self.env.user.has_group(
            "c2p_project_tracker.group_c2p_portfolio_manager")

        def amount(value, project):
            return format_amount(self.env, value or 0.0,
                                 project.c2p_currency_id or self.env.company.currency_id)

        rows = []
        for project in projects:
            row = {
                "name": project.name,
                "client": project.partner_id.name or "",
                "rag": project.rag_status or "grey",
                "rag_label": RAG_LABEL.get(project.rag_status or "grey", ""),
                "reasons": [line.lstrip("• ").strip()
                            for line in (project.rag_reasons or "").splitlines()
                            if line.strip()],
                "health": project.health_score,
                "progress": round(project.progress_pct),
                "current": project.current_milestone_id.name or "",
                "next": project.next_milestone_date or "",
                "slip": project.golive_slippage_days,
                "slip_label": (f"{project.golive_slippage_days:+d}d"
                               if project.golive_slippage_days else "—"),
                "idle": project.days_since_activity,
            }
            if show_money:
                row.update({
                    "contract": amount(project.contract_value, project),
                    "received": amount(project.amount_received_effective, project),
                    "outstanding": amount(project.amount_outstanding, project),
                })
            rows.append(row)

        rag = {"red": 0, "amber": 0, "green": 0, "grey": 0}
        for project in projects:
            rag[project.rag_status or "grey"] += 1

        payload = {
            # Pass the date object: QWeb's t-esc renders it in the user's
            # format. Hand-formatting here would ignore their locale.
            "as_of": fields.Date.context_today(self),
            "count": len(projects),
            "progress": round(
                sum(projects.mapped("progress_pct")) / len(projects)
            ) if projects else 0,
            "overdue": sum(projects.mapped("overdue_milestones_count")),
            "blockers": sum(projects.mapped("open_blockers_count")),
            "rag": rag,
            "rows": rows,
            "attention": self.env["c2p.dashboard"]._attention(projects, show_money)
            if projects else [],
            "money": None,
        }
        if show_money and projects:
            company_currency = self.env.company.currency_id
            payload["money"] = {
                "value": format_amount(
                    self.env, sum(projects.mapped("contract_value")), company_currency),
                "collected": format_amount(
                    self.env, sum(projects.mapped("amount_received_effective")),
                    company_currency),
                "outstanding": format_amount(
                    self.env, sum(projects.mapped("amount_outstanding")),
                    company_currency),
                "payable": format_amount(
                    self.env, sum(projects.mapped("subcontract_outstanding")),
                    company_currency),
                "margin": format_amount(
                    self.env, sum(projects.mapped("consultants_margin")),
                    company_currency),
            }
        return payload

    def _c2p_client_status_payload(self):
        """One project, for the client. Carries no commercial figure at all —
        this document leaves the building."""
        self.ensure_one()
        milestones = self._c2p_milestones()

        # What the client owes us: delivery tasks parked in Waiting on Client,
        # plus any open RAID dependency. Read with sudo because delivery is in
        # another company, and only the reason text is surfaced.
        actions = []
        delivery = self.sudo().c2p_counterpart_id
        if delivery:
            tasks = self.env["project.task"].sudo().search(
                [("project_id", "=", delivery.id), ("waiting_since", "!=", False)])
            for task in tasks:
                if task._is_waiting_on_client():
                    actions.append({
                        "since": task.waiting_since or "",
                        "text": task.blocked_reason or task.name,
                    })
        for item in self.env["c2p.raid.item"].search(
                [("project_id", "=", self.id), ("item_type", "=", "dependency"),
                 ("state", "!=", "closed")]):
            actions.append({"since": item.raised_date or "", "text": item.name})

        return {
            "name": self.name,
            "client": self.partner_id.name or "",
            "as_of": fields.Date.context_today(self),
            "rag": self.rag_status or "grey",
            "rag_label": RAG_LABEL.get(self.rag_status or "grey", ""),
            "progress": round(self.progress_pct),
            "next": self.next_milestone_date or "",
            "milestones": [
                {
                    "code": m.c2p_code or "",
                    "name": m.name,
                    "stage": m.stage_id.name or "",
                    "deadline": m.date_deadline or "",
                }
                for m in milestones
            ],
            # Oldest first, undated last. The key must not mix a date with a
            # string, which would raise TypeError as soon as both kinds of
            # action were present.
            "client_actions": sorted(
                actions,
                key=lambda a: (a["since"] is False or a["since"] is None,
                               a["since"] or fields.Date.today())),
        }
