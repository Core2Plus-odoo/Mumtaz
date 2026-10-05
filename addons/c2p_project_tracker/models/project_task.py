import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Portfolio milestones are named "M1 …", "M2 …". Portfolio projects also hold
# ordinary tasks — project 14 has 16 tasks for 8 milestones, project 16 has 11
# for 6 — so being in a portfolio project is NOT sufficient to be a milestone.
MILESTONE_CODE_RE = re.compile(r"^\s*(M\d+)\b", re.IGNORECASE)

# Stages are per-project records, not shared, so they are matched by name.
# Delivery stages: Backlog / To Do / In Progress / Waiting on Client / Review / Done
DELIVERY_BACKLOG = "backlog"
DELIVERY_WAITING = "waiting on client"
DELIVERY_DONE = "done"
DELIVERY_IN_FLIGHT = ("in progress", "review")

# Portfolio stages: Not Started / In Progress / Blocked / Client Review / Done
PORTFOLIO_NOT_STARTED = "not started"
PORTFOLIO_IN_PROGRESS = "in progress"
PORTFOLIO_BLOCKED = "blocked"
PORTFOLIO_CLIENT_REVIEW = "client review"
PORTFOLIO_DONE = "done"


class ProjectTask(models.Model):
    _inherit = "project.task"

    # ── Portfolio milestone fields ───────────────────────────────────────
    c2p_is_milestone = fields.Boolean(
        string="Is Portfolio Milestone", compute="_compute_c2p_is_milestone",
        store=True, index=True,
        help="A task in a portfolio project whose name starts with an M<number> "
             "code. Portfolio projects also contain ordinary tasks.")
    c2p_code = fields.Char(
        string="Milestone Code", compute="_compute_c2p_code",
        store=True, readonly=False, index=True,
        help="Parsed from the task name (M1, M2 …). Editable when the name does "
             "not follow the convention.")
    weight = fields.Float(
        string="Milestone Weight", default=1.0,
        help="Relative weight for the project's weighted progress. Equal "
             "weights give a simple done/total percentage.")

    baseline_deadline = fields.Date(
        string="Baseline Deadline", readonly=True, copy=False,
        help="The deadline first committed to. Set once, then only a Portfolio "
             "Manager may reset it, which is logged in the chatter.")
    slippage_days = fields.Integer(
        compute="_compute_slippage_days", store=True,
        help="Current deadline minus baseline. Positive means later than "
             "originally committed.")

    delivery_milestone_id = fields.Many2one(
        "project.milestone", string="Delivery Milestone", copy=False, index=True,
        help="The matching native milestone in the counterpart delivery "
             "project, matched by code.")
    sync_locked = fields.Boolean(
        string="Lock Auto-sync", copy=False,
        help="Stop the sync engine from touching this milestone's stage and "
             "deadline, so a manager's override survives.")

    # ── Billing (optional, per milestone) ────────────────────────────────
    billing_pct = fields.Float(string="Billing %")
    billing_amount = fields.Monetary(
        string="Billing Amount", currency_field="c2p_company_currency_id")
    # Prefixed for the same reason as the project fields: project.task may
    # already define company_currency_id through another module, and
    # redefining a standard field is a needless risk.
    c2p_company_currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True)
    invoice_status = fields.Selection(
        [("not_due", "Not Due"), ("due", "Due"),
         ("invoiced", "Invoiced"), ("paid", "Paid")],
        default="not_due", copy=False)

    # ── Delivery-side fields ────────────────────────────────────────────
    # Standard project.task already carries allocated_hours for planned effort,
    # so no estimated-hours field is added here.
    outsourced = fields.Boolean(
        help="Work given to a third party rather than the internal team.")
    vendor_id = fields.Many2one(
        "res.partner", string="Vendor",
        domain="[('is_company', '=', True)]",
        help="Who the work was outsourced to.")
    blocked_reason = fields.Char(
        string="Blocked Reason",
        help="Why the client is holding this up. Required in Waiting on Client.")
    waiting_since = fields.Date(
        string="Waiting Since", readonly=True, copy=False,
        help="Set when the task first enters Waiting on Client, cleared when it "
             "leaves, so the age of a client blocker is measurable.")

    # ── Computes ─────────────────────────────────────────────────────────
    @api.depends("name", "project_id.c2p_layer")
    def _compute_c2p_is_milestone(self):
        for task in self:
            task.c2p_is_milestone = bool(
                task.project_id.c2p_layer == "portfolio"
                and task.name and MILESTONE_CODE_RE.match(task.name))

    @api.depends("name", "c2p_is_milestone")
    def _compute_c2p_code(self):
        for task in self:
            if not task.c2p_is_milestone:
                task.c2p_code = False
                continue
            match = MILESTONE_CODE_RE.match(task.name or "")
            # Normalise to upper case so M1 and m1 match the same delivery
            # milestone.
            task.c2p_code = match.group(1).upper() if match else task.c2p_code

    @api.depends("date_deadline", "baseline_deadline")
    def _compute_slippage_days(self):
        for task in self:
            if task.date_deadline and task.baseline_deadline:
                task.slippage_days = (task.date_deadline - task.baseline_deadline).days
            else:
                task.slippage_days = 0

    # ── Stage helpers ────────────────────────────────────────────────────
    def _stage_name(self):
        """Lower-cased stage name, for the name-based matching this structure
        requires: each project owns its own project.task.type records, so stage
        ids cannot be hardcoded."""
        self.ensure_one()
        return (self.stage_id.name or "").strip().lower()

    def _is_waiting_on_client(self):
        return self._stage_name() == DELIVERY_WAITING

    def _is_done_stage(self):
        return self._stage_name() == DELIVERY_DONE or self.stage_id.fold

    def _is_in_flight(self):
        return self._stage_name() in DELIVERY_IN_FLIGHT

    # ── Hygiene and blocker bookkeeping ─────────────────────────────────
    @api.constrains("stage_id", "user_ids", "date_deadline", "milestone_id")
    def _check_delivery_hygiene(self):
        """A delivery task that has left Backlog must say who owns it, when it
        is due and which milestone it serves. Without these three the portfolio
        view cannot be trusted, so they are enforced rather than reported."""
        for task in self:
            if task.project_id.c2p_layer != "delivery":
                continue
            if not task.stage_id or task._stage_name() == DELIVERY_BACKLOG:
                continue
            missing = []
            if not task.user_ids:
                missing.append(_("an assignee"))
            if not task.date_deadline:
                missing.append(_("a deadline"))
            if not task.milestone_id:
                missing.append(_("a milestone"))
            if missing:
                raise ValidationError(_(
                    "Task %(task)s cannot leave Backlog without %(missing)s.\n"
                    "Set them on the task, or move it back to Backlog.",
                    task=task.name, missing=", ".join(missing)))

    @api.constrains("stage_id", "blocked_reason")
    def _check_blocked_reason(self):
        for task in self:
            if task.project_id.c2p_layer != "delivery":
                continue
            if task._is_waiting_on_client() and not task.blocked_reason:
                raise ValidationError(_(
                    "Task %(task)s is Waiting on Client, so it needs a Blocked "
                    "Reason saying what the client owes.", task=task.name))

    def write(self, vals):
        """Maintain waiting_since and the baseline, then resync the portfolio."""
        track_stage = "stage_id" in vals
        before = {}
        if track_stage:
            before = {t.id: t._is_waiting_on_client() for t in self}

        res = super().write(vals)

        if track_stage:
            for task in self:
                was_waiting = before.get(task.id, False)
                now_waiting = task._is_waiting_on_client()
                if now_waiting and not was_waiting:
                    task.waiting_since = fields.Date.context_today(task)
                elif was_waiting and not now_waiting:
                    task.waiting_since = False

        # A milestone's first real deadline becomes its baseline, so slippage is
        # measured against what was originally committed.
        if "date_deadline" in vals:
            for task in self.filtered(
                    lambda t: t.c2p_is_milestone and t.date_deadline
                    and not t.baseline_deadline):
                task.baseline_deadline = task.date_deadline

        if track_stage or {"milestone_id", "date_deadline"} & set(vals):
            delivery = self.filtered(
                lambda t: t.project_id.c2p_layer == "delivery")
            if delivery:
                delivery.project_id._c2p_sync_portfolio_milestones()
        return res

    def action_reset_baseline(self):
        """Clear the baseline so the next deadline re-establishes it. Restricted
        to Portfolio Managers and always logged, because resetting it erases the
        slippage history the portfolio view reports on."""
        if not self.env.user.has_group(
                "c2p_project_tracker.group_c2p_portfolio_manager"):
            raise UserError(_("Only a Portfolio Manager may reset a baseline."))
        for task in self:
            old = task.baseline_deadline
            task.baseline_deadline = False
            task.message_post(
                body=_("Baseline deadline reset (was %(old)s) by %(user)s.",
                       old=old or _("not set"), user=self.env.user.name),
                subtype_xmlid="mail.mt_note")
        return True
