from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .project_task import (
    PORTFOLIO_BLOCKED,
    PORTFOLIO_CLIENT_REVIEW,
    PORTFOLIO_DONE,
    PORTFOLIO_IN_PROGRESS,
)

# Defaults for the health thresholds, overridable in Settings.
DEFAULT_THRESHOLDS = {
    "red_milestone_overdue_days": 7,
    "red_blocker_days": 14,
    "red_slippage_days": 21,
    "red_inactive_days": 14,
    "amber_blocker_days": 7,
    "amber_inactive_days": 7,
}


class ProjectProject(models.Model):
    _inherit = "project.project"

    # ── Layer and pairing ────────────────────────────────────────────────
    c2p_layer = fields.Selection(
        [("portfolio", "Portfolio (Consultants milestones)"),
         ("delivery", "Delivery (Solutions)"),
         ("template", "Template / playbook"),
         ("internal", "Internal")],
        string="C2P Layer", index=True, copy=False,
        help="Templates and internal projects are excluded from every dashboard.")
    c2p_counterpart_id = fields.Many2one(
        "project.project", string="Counterpart Project", copy=False, index=True,
        help="Links a portfolio project to its delivery project and back.")

    # ── Engagement (portfolio only) ──────────────────────────────────────
    engagement_type = fields.Selection(
        [("erp", "ERP Implementation"), ("custom", "Custom Development"),
         ("support", "Support"), ("consulting", "Consulting"),
         ("other", "Other")],
        string="Engagement Type")
    account_manager_id = fields.Many2one("res.users", string="Account Manager")
    client_contact_id = fields.Many2one("res.partner", string="Client Contact")
    start_date = fields.Date(string="Start Date")
    baseline_golive_date = fields.Date(string="Baseline Go-Live")
    forecast_golive_date = fields.Date(string="Forecast Go-Live")
    golive_slippage_days = fields.Integer(
        compute="_compute_golive_slippage_days", store=True)

    # ── Commercials (portfolio only, Portfolio Manager only) ─────────────
    # Every field here carries groups= so a Delivery Lead or Member cannot read
    # an AED figure anywhere, including over RPC.
    COMMERCIAL_GROUP = "c2p_project_tracker.group_c2p_portfolio_manager"

    # Deliberately NOT named currency_id / sale_order_id: project.project may
    # already carry those (sale_project, analytic), and adding groups= to a
    # standard field would strip it from every non-manager and can break stock
    # views. A c2p_ prefix keeps the restriction to fields this module owns.
    c2p_currency_id = fields.Many2one(
        "res.currency", string="Contract Currency",
        default=lambda self: self.env.company.currency_id,
        groups=COMMERCIAL_GROUP)
    contract_value = fields.Monetary(
        string="Contract Value", currency_field="c2p_currency_id",
        groups=COMMERCIAL_GROUP, tracking=True)
    amount_received = fields.Monetary(
        string="Received (manual)", currency_field="c2p_currency_id",
        groups=COMMERCIAL_GROUP, tracking=True,
        help="Fallback when no sale order is linked, or when it is not invoiced "
             "through Odoo.")
    amount_received_effective = fields.Monetary(
        string="Received", currency_field="c2p_currency_id",
        compute="_compute_commercials", store=True, groups=COMMERCIAL_GROUP,
        help="Paid customer invoices for the linked sale order when there are "
             "any, otherwise the manual figure.")
    amount_outstanding = fields.Monetary(
        string="Outstanding", currency_field="c2p_currency_id",
        compute="_compute_commercials", store=True, groups=COMMERCIAL_GROUP)

    subcontract_pct = fields.Float(
        string="Subcontract %", default=60.0, groups=COMMERCIAL_GROUP,
        help="Share of project revenue payable to C2P Solutions. The group "
             "default is 60%, leaving 40% with C2P Consultants.")
    subcontract_value = fields.Monetary(
        string="Payable to Solutions", currency_field="c2p_currency_id",
        compute="_compute_commercials", store=True, groups=COMMERCIAL_GROUP)
    subcontract_paid = fields.Monetary(
        string="Paid to Solutions", currency_field="c2p_currency_id",
        groups=COMMERCIAL_GROUP, tracking=True)
    subcontract_outstanding = fields.Monetary(
        string="Owed to Solutions", currency_field="c2p_currency_id",
        compute="_compute_commercials", store=True, groups=COMMERCIAL_GROUP)
    consultants_margin = fields.Monetary(
        string="Consultants Margin", currency_field="c2p_currency_id",
        compute="_compute_commercials", store=True, groups=COMMERCIAL_GROUP,
        help="The Consultants share earned on money actually collected, not on "
             "the contract value — an uncollected invoice has earned nothing.")
    commercials_missing = fields.Boolean(
        compute="_compute_commercials", store=True, groups=COMMERCIAL_GROUP)

    c2p_sale_order_id = fields.Many2one(
        "sale.order", string="Sale Order", groups=COMMERCIAL_GROUP,
        help="Optional. When set and invoiced, Received is taken from its paid "
             "customer invoices instead of the manual field.")

    # ── Health ───────────────────────────────────────────────────────────
    rag_status = fields.Selection(
        [("green", "Green"), ("amber", "Amber"), ("red", "Red"),
         ("grey", "No data")],
        string="RAG", compute="_compute_health", store=True, index=True)
    rag_reasons = fields.Text(
        string="RAG Reasons", compute="_compute_health", store=True,
        help="Why the status is what it is, one factor per line.")
    health_score = fields.Integer(compute="_compute_health", store=True)
    rag_override = fields.Selection(
        [("green", "Green"), ("amber", "Amber"), ("red", "Red")],
        string="RAG Override", copy=False)
    rag_override_reason = fields.Char(copy=False)

    progress_pct = fields.Float(
        string="Weighted Progress", compute="_compute_milestone_state",
        store=True, group_operator="avg")
    current_milestone_id = fields.Many2one(
        "project.task", string="Current Milestone",
        compute="_compute_milestone_state", store=True)
    next_milestone_date = fields.Date(
        compute="_compute_milestone_state", store=True)
    overdue_milestones_count = fields.Integer(
        compute="_compute_milestone_state", store=True)

    last_activity_date = fields.Datetime(
        compute="_compute_delivery_activity", store=True)
    days_since_activity = fields.Integer(
        compute="_compute_delivery_activity", store=True)
    open_blockers_count = fields.Integer(
        string="Client Blockers", compute="_compute_delivery_activity", store=True)
    overdue_tasks_count = fields.Integer(
        compute="_compute_delivery_activity", store=True)

    _counterpart_unique = models.Constraint(
        "UNIQUE(c2p_counterpart_id)",
        "Two projects cannot share the same counterpart project.")

    # ── Constraints ──────────────────────────────────────────────────────
    @api.constrains("c2p_counterpart_id", "c2p_layer")
    def _check_counterpart_pairing(self):
        """A pair is exactly one portfolio and one delivery project, and the
        link must be reciprocal — the portfolio view reads the delivery side
        through it, so a half-formed pair silently reports nothing."""
        for project in self:
            counterpart = project.c2p_counterpart_id
            if not counterpart:
                continue
            if counterpart == project:
                raise ValidationError(
                    _("A project cannot be its own counterpart."))
            layers = {project.c2p_layer, counterpart.c2p_layer}
            if layers != {"portfolio", "delivery"}:
                raise ValidationError(_(
                    "A counterpart pair must be one portfolio project and one "
                    "delivery project, but %(a)s is %(la)s and %(b)s is %(lb)s.",
                    a=project.name, la=project.c2p_layer or _("unset"),
                    b=counterpart.name, lb=counterpart.c2p_layer or _("unset")))

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        projects._c2p_mirror_counterpart()
        return projects

    def write(self, vals):
        res = super().write(vals)
        if "c2p_counterpart_id" in vals:
            self._c2p_mirror_counterpart()
        return res

    def _c2p_mirror_counterpart(self):
        """Keep the link reciprocal without recursing back into write()."""
        for project in self:
            counterpart = project.c2p_counterpart_id
            if counterpart and counterpart.c2p_counterpart_id != project:
                super(ProjectProject, counterpart).write(
                    {"c2p_counterpart_id": project.id})

    # ── Cross-company access ─────────────────────────────────────────────
    def _c2p_delivery_project(self):
        """The delivery project for a portfolio project, read with sudo.

        Delivery lives in another company, so a Consultants-only user cannot
        read it directly. Callers must only return aggregates from this — never
        task detail — which is why it is private.
        """
        self.ensure_one()
        if self.c2p_layer != "portfolio":
            return self.browse()
        return self.sudo().c2p_counterpart_id

    def _c2p_milestones(self):
        """Portfolio milestone tasks, in code order."""
        self.ensure_one()
        return self.env["project.task"].search(
            [("project_id", "=", self.id), ("c2p_is_milestone", "=", True)],
            order="c2p_code, id")

    # ── Computes ─────────────────────────────────────────────────────────
    @api.depends("contract_value", "amount_received", "subcontract_pct",
                 "subcontract_paid", "c2p_sale_order_id",
                 "c2p_sale_order_id.invoice_ids.payment_state",
                 "c2p_sale_order_id.invoice_ids.amount_total",
                 "c2p_sale_order_id.invoice_ids.state",
                 "c2p_sale_order_id.invoice_ids.move_type")
    def _compute_commercials(self):
        for project in self:
            received = project.amount_received
            invoices = project.c2p_sale_order_id.invoice_ids.filtered(
                lambda m: m.move_type == "out_invoice"
                and m.state == "posted" and m.payment_state == "paid")
            if invoices:
                # A linked, invoiced SO is authoritative; the manual figure is
                # only a fallback for work billed outside Odoo.
                received = sum(invoices.mapped("amount_total"))

            project.amount_received_effective = received
            project.amount_outstanding = project.contract_value - received
            project.subcontract_value = (
                project.contract_value * project.subcontract_pct / 100.0)
            project.subcontract_outstanding = (
                project.subcontract_value - project.subcontract_paid)
            project.consultants_margin = (
                received * (100.0 - project.subcontract_pct) / 100.0)
            project.commercials_missing = (
                project.c2p_layer == "portfolio" and not project.contract_value)

    @api.constrains("subcontract_pct")
    def _check_subcontract_pct(self):
        for project in self:
            if not 0.0 <= project.subcontract_pct <= 100.0:
                raise ValidationError(
                    _("The subcontract share must be between 0 and 100%."))

    @api.depends("baseline_golive_date", "forecast_golive_date")
    def _compute_golive_slippage_days(self):
        for project in self:
            if project.baseline_golive_date and project.forecast_golive_date:
                project.golive_slippage_days = (
                    project.forecast_golive_date - project.baseline_golive_date).days
            else:
                project.golive_slippage_days = 0

    @api.depends("task_ids.stage_id", "task_ids.date_deadline",
                 "task_ids.weight", "task_ids.c2p_is_milestone")
    def _compute_milestone_state(self):
        today = fields.Date.context_today(self)
        for project in self:
            milestones = project._c2p_milestones() if project.id else project.browse()
            if not milestones:
                project.progress_pct = 0.0
                project.current_milestone_id = False
                project.next_milestone_date = False
                project.overdue_milestones_count = 0
                continue
            total = sum(m.weight or 1.0 for m in milestones)
            done = sum((m.weight or 1.0) for m in milestones
                       if (m.stage_id.name or "").strip().lower() == PORTFOLIO_DONE)
            project.progress_pct = (done / total * 100.0) if total else 0.0

            open_ms = milestones.filtered(
                lambda m: (m.stage_id.name or "").strip().lower() != PORTFOLIO_DONE)
            project.current_milestone_id = open_ms[:1].id if open_ms else False
            dated = open_ms.filtered("date_deadline").sorted("date_deadline")
            project.next_milestone_date = dated[:1].date_deadline if dated else False
            project.overdue_milestones_count = len(dated.filtered(
                lambda m: m.date_deadline < today))

    @api.depends("c2p_counterpart_id")
    def _compute_delivery_activity(self):
        """Aggregate the delivery side. Reads with sudo because delivery is in
        another company, and returns only counts and a timestamp."""
        today = fields.Date.context_today(self)
        Task = self.env["project.task"].sudo()
        for project in self:
            delivery = project._c2p_delivery_project() if project.id else project.browse()
            if not delivery:
                project.last_activity_date = False
                project.days_since_activity = 0
                project.open_blockers_count = 0
                project.overdue_tasks_count = 0
                continue
            tasks = Task.search([("project_id", "=", delivery.id)])
            writes = tasks.mapped("write_date")
            project.last_activity_date = max(writes) if writes else False
            project.days_since_activity = (
                (fields.Datetime.now() - project.last_activity_date).days
                if project.last_activity_date else 0)
            project.open_blockers_count = len(
                tasks.filtered(lambda t: t._is_waiting_on_client()))
            project.overdue_tasks_count = len(tasks.filtered(
                lambda t: t.date_deadline and t.date_deadline < today
                and not t._is_done_stage()))

    def _c2p_thresholds(self):
        """Health thresholds from Settings, falling back to the defaults."""
        param = self.env["ir.config_parameter"].sudo()
        out = {}
        for key, default in DEFAULT_THRESHOLDS.items():
            raw = param.get_param(f"c2p_project_tracker.{key}")
            try:
                out[key] = int(raw) if raw else default
            except (TypeError, ValueError):
                out[key] = default
        return out

    @api.depends("progress_pct", "overdue_milestones_count", "open_blockers_count",
                 "days_since_activity", "golive_slippage_days", "rag_override")
    def _compute_health(self):
        today = fields.Date.context_today(self)
        th = self._c2p_thresholds()
        for project in self:
            if project.c2p_layer != "portfolio":
                project.rag_status = "grey"
                project.rag_reasons = False
                project.health_score = 0
                continue

            red, amber = [], []
            milestones = project._c2p_milestones() if project.id else project.browse()
            open_ms = milestones.filtered(
                lambda m: (m.stage_id.name or "").strip().lower() != PORTFOLIO_DONE)

            worst_overdue = 0
            for m in open_ms.filtered("date_deadline"):
                worst_overdue = max(worst_overdue, (today - m.date_deadline).days)
            if worst_overdue > th["red_milestone_overdue_days"]:
                red.append(_("A milestone is %s days overdue.") % worst_overdue)
            elif worst_overdue >= 1:
                amber.append(_("A milestone is %s days overdue.") % worst_overdue)

            blocker_age = project._c2p_oldest_blocker_days()
            if blocker_age > th["red_blocker_days"]:
                red.append(_("A client blocker is %s days old.") % blocker_age)
            elif blocker_age >= th["amber_blocker_days"]:
                amber.append(_("A client blocker is %s days old.") % blocker_age)

            if project.golive_slippage_days > th["red_slippage_days"]:
                red.append(_("Go-live has slipped %s days.")
                           % project.golive_slippage_days)

            if open_ms and project.days_since_activity > th["red_inactive_days"]:
                red.append(_("No delivery activity for %s days.")
                           % project.days_since_activity)
            elif open_ms and project.days_since_activity >= th["amber_inactive_days"]:
                amber.append(_("No delivery activity for %s days.")
                             % project.days_since_activity)

            undated = len(open_ms.filtered(lambda m: not m.date_deadline))
            if undated:
                amber.append(_("%s open milestones have no deadline.") % undated)

            if not milestones:
                amber.append(_("No milestones are defined."))

            # Read commercials with sudo: the health of a project is visible to
            # the Delivery Lead even though the figures behind it are not, so
            # the reason text deliberately states no amounts.
            money = project.sudo()
            if money.commercials_missing:
                amber.append(_("Commercials are missing."))
            elif (money.contract_value
                  and money.amount_outstanding > money.contract_value / 2.0
                  and project.progress_pct > 50.0):
                amber.append(_(
                    "More than half the contract is outstanding while delivery "
                    "is past halfway."))

            status = "red" if red else ("amber" if amber else "green")
            reasons = red + amber
            if project.rag_override:
                status = project.rag_override
                reasons = [_("Overridden: %s")
                           % (project.rag_override_reason or _("no reason given"))] + reasons

            project.rag_status = status
            project.rag_reasons = "\n".join(f"• {r}" for r in reasons) or _(
                "• No issues detected.")
            # Each red factor costs 20, each amber 8, floored at zero.
            project.health_score = max(0, 100 - 20 * len(red) - 8 * len(amber))

    def _c2p_oldest_blocker_days(self):
        """Age in days of the longest-standing client blocker on the delivery
        side, or 0. Sudo read, count only."""
        self.ensure_one()
        delivery = self._c2p_delivery_project()
        if not delivery:
            return 0
        today = fields.Date.context_today(self)
        tasks = self.env["project.task"].sudo().search(
            [("project_id", "=", delivery.id), ("waiting_since", "!=", False)])
        ages = [(today - t.waiting_since).days for t in tasks
                if t._is_waiting_on_client()]
        return max(ages) if ages else 0

    # ── Sync engine ──────────────────────────────────────────────────────
    def _c2p_portfolio_stage(self, lower_name):
        """A portfolio project's stage by name. Each project owns its own
        project.task.type records, so stages cannot be addressed by id."""
        self.ensure_one()
        for stage in self.env["project.task.type"].search(
                [("project_ids", "in", self.id)]):
            if (stage.name or "").strip().lower() == lower_name:
                return stage
        return self.env["project.task.type"].browse()

    def _c2p_sync_portfolio_milestones(self):
        """Push delivery state onto the portfolio milestones.

        Accepts portfolio or delivery projects; delivery ones are resolved to
        their counterpart. Honours sync_locked. Returns the number of
        milestones changed.
        """
        changed = 0
        History = self.env["c2p.milestone.history"]
        Task = self.env["project.task"].sudo()

        for project in self:
            portfolio = project
            if project.c2p_layer == "delivery":
                portfolio = project.sudo().c2p_counterpart_id
            if not portfolio or portfolio.c2p_layer != "portfolio":
                continue

            for milestone in portfolio._c2p_milestones():
                if milestone.sync_locked or not milestone.delivery_milestone_id:
                    continue
                dm = milestone.delivery_milestone_id.sudo()
                tasks = Task.search([("milestone_id", "=", dm.id)])
                counts = {
                    "done": len(tasks.filtered(lambda t: t._is_done_stage())),
                    "waiting": len(tasks.filtered(lambda t: t._is_waiting_on_client())),
                }
                counts["open"] = len(tasks) - counts["done"]

                old_stage = milestone.stage_id
                old_deadline = milestone.date_deadline
                vals = {}

                # Deadline: only propagate a real date. The delivery milestones
                # currently carry no deadlines, and blanking the portfolio side
                # would destroy the baseline comparison.
                if dm.deadline and dm.deadline != milestone.date_deadline:
                    vals["date_deadline"] = dm.deadline
                    if not milestone.baseline_deadline:
                        vals["baseline_deadline"] = dm.deadline

                target = self._c2p_target_stage_name(dm, tasks, counts)
                if target:
                    stage = portfolio._c2p_portfolio_stage(target)
                    if stage and stage != milestone.stage_id:
                        vals["stage_id"] = stage.id

                if not vals:
                    continue

                milestone.with_context(c2p_sync=True).write(vals)
                row = History.log(milestone, old_stage, old_deadline, counts)
                if row:
                    changed += 1
                    # Internal note only: mt_note with no partner_ids never
                    # emails anyone, which matters on client-followed projects.
                    milestone.message_post(
                        body=_("Auto-sync: %(old)s → %(new)s "
                               "(%(done)s done / %(open)s open / %(waiting)s "
                               "waiting on client)",
                               old=old_stage.name or _("none"),
                               new=milestone.stage_id.name or _("none"),
                               done=counts["done"], open=counts["open"],
                               waiting=counts["waiting"]),
                        subtype_xmlid="mail.mt_note")
        return changed

    @api.model
    def _c2p_target_stage_name(self, delivery_milestone, tasks, counts):
        """The portfolio stage a milestone should be in, by the agreed order of
        precedence. Returns None to leave the stage alone."""
        if delivery_milestone.is_reached:
            return PORTFOLIO_DONE
        if counts["waiting"]:
            return PORTFOLIO_BLOCKED
        if tasks and counts["done"] == len(tasks):
            return PORTFOLIO_CLIENT_REVIEW
        if any(t._is_done_stage() or t._is_in_flight() for t in tasks):
            return PORTFOLIO_IN_PROGRESS
        return None

    @api.model
    def _c2p_cron_sync(self):
        """Hourly safety net for changes the write hooks missed."""
        projects = self.search([("c2p_layer", "=", "portfolio")])
        changed = projects._c2p_sync_portfolio_milestones()
        projects._compute_health()
        return changed
