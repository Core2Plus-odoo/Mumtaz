from datetime import datetime, time

from markupsafe import Markup
from psycopg2 import IntegrityError, errorcodes

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class C2pMeetingAction(models.Model):
    """An action item arising from a meeting.

    Carries a durable reference of its own, so it can be cited outside Odoo and
    still be found, and converts into exactly one ``project.task``.
    """

    _name = "c2p.meeting.action"
    _description = "C2P Meeting Action Item"
    _inherit = ["mail.thread"]
    _order = "meeting_id desc, sequence, id"

    reference = fields.Char(
        string="Reference", readonly=True, copy=False, index=True,
        help="Durable identity, e.g. MOM/2026/0007-A3. Stable for the life of "
             "the action and stamped onto the task it creates.")
    name = fields.Char(string="Action", required=True, tracking=True)
    sequence = fields.Integer(default=10)
    notes = fields.Text(string="Context")

    meeting_id = fields.Many2one(
        "c2p.meeting", string="Minutes", required=True, index=True,
        ondelete="cascade")
    project_id = fields.Many2one(
        "project.project", string="Project", index=True,
        compute="_compute_project_id", store=True, readonly=False,
        help="Defaults to the meeting's project; override for cross-project "
             "actions.")
    milestone_id = fields.Many2one(
        "project.milestone", string="Milestone",
        domain="[('project_id', '=', project_id)]")
    parent_task_id = fields.Many2one(
        "project.task", string="Related Task",
        domain="[('project_id', '=', project_id)]",
        help="An existing task this action concerns. The created task becomes "
             "its subtask.")
    company_id = fields.Many2one(
        related="meeting_id.company_id", store=True, index=True)

    user_id = fields.Many2one(
        "res.users", string="Responsible", required=True, tracking=True,
        default=lambda self: self.env.user)
    date_deadline = fields.Date(string="Target Date", tracking=True)

    state = fields.Selection(
        [("draft", "Draft"), ("proposed", "Proposed"),
         ("approved", "Approved"), ("rejected", "Rejected"),
         ("converted", "Converted to Task")],
        default="draft", required=True, tracking=True, index=True)

    proposed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    proposed_at = fields.Datetime(readonly=True, copy=False)
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    rejection_reason = fields.Char(readonly=True, copy=False, tracking=True)

    task_id = fields.Many2one(
        "project.task", string="Task", readonly=True, copy=False, index=True,
        ondelete="set null",
        help="The task this action became. Set once and never reassigned.")
    task_state = fields.Selection(
        related="task_id.state", string="Task Status", readonly=True)

    _reference_unique = models.Constraint(
        "UNIQUE(reference)",
        "Two action items cannot share a reference.")
    # One task is never claimed by two actions. The guard against one action
    # creating two tasks lives on project.task — see project_task.py.
    _task_unique = models.Constraint(
        "UNIQUE(task_id)",
        "That task already came from another action item.")

    @api.depends("meeting_id.project_id")
    def _compute_project_id(self):
        for action in self:
            if not action.project_id:
                action.project_id = action.meeting_id.project_id

    @api.constrains("milestone_id", "project_id")
    def _check_milestone_project(self):
        for action in self:
            if action.milestone_id and action.project_id and \
                    action.milestone_id.project_id != action.project_id:
                raise ValidationError(_(
                    "Milestone %(ms)s does not belong to project %(proj)s.",
                    ms=action.milestone_id.display_name,
                    proj=action.project_id.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        actions = super().create(vals_list)
        actions._assign_references()
        return actions

    def _assign_references(self):
        """`<meeting reference>-A<n>`, numbered within the meeting.

        Derived rather than drawn from a global sequence so the reference says
        which minutes it came from. The UNIQUE constraint on `reference` is what
        makes a collision a database error rather than a silent duplicate.
        """
        for action in self.filtered(lambda a: not a.reference):
            meeting = action.meeting_id
            used = self.search([("meeting_id", "=", meeting.id),
                                ("reference", "!=", False)])
            taken = set()
            for other in used:
                tail = (other.reference or "").rsplit("-A", 1)
                if len(tail) == 2 and tail[1].isdigit():
                    taken.add(int(tail[1]))
            n = 1
            while n in taken:
                n += 1
            action.reference = f"{meeting.reference or 'MOM'}-A{n}"

    # ── approval ────────────────────────────────────────────────────────
    def action_propose(self):
        for action in self:
            if action.state != "draft":
                raise UserError(_("Only a draft action can be proposed."))
            action.write({"state": "proposed",
                          "proposed_by_id": self.env.uid,
                          "proposed_at": fields.Datetime.now()})
        return True

    def action_approve(self):
        """Approve for conversion. Approver group only.

        Self-approval is permitted but never silent: it is written into the
        chatter explicitly, so an audit sees who proposed and approved the same
        item rather than having to infer it from two fields.
        """
        self._check_approver()
        for action in self:
            if action.state not in ("draft", "proposed"):
                raise UserError(_(
                    "Action %(ref)s is %(state)s, so it cannot be approved.",
                    ref=action.reference, state=action.state))
            action.write({"state": "approved",
                          "approved_by_id": self.env.uid,
                          "approved_at": fields.Datetime.now(),
                          "rejection_reason": False})
            if action.proposed_by_id and action.proposed_by_id.id == self.env.uid:
                action.message_post(body=_(
                    "Approved by the same user who proposed it."))
        return True

    def action_reject(self, reason=None):
        self._check_approver()
        reason = (reason or "").strip()
        if not reason:
            raise UserError(_("A rejection needs a reason — the point is that "
                              "the proposer knows what to change."))
        for action in self:
            if action.state == "converted":
                raise UserError(_(
                    "Action %s already became a task, so it cannot be "
                    "rejected. Cancel the task instead.", action.reference))
            action.write({"state": "rejected", "rejection_reason": reason,
                          "approved_by_id": self.env.uid,
                          "approved_at": fields.Datetime.now()})
        return True

    def _check_approver(self):
        if not self.env.user.has_group(
                "c2p_meeting_actions.group_c2p_meeting_approver"):
            raise UserError(_("Only a meeting approver can approve or reject "
                              "action items."))

    # ── conversion: the idempotent part ─────────────────────────────────
    def action_create_task(self):
        """Create this action's task, exactly once, safely under concurrency.

        Three layers, in order of how much they are trusted:

        1. `task_id` already set — nothing to do. Cheap and covers the ordinary
           repeat click.
        2. A task already carries this action's reference — adopt it. This
           covers the case where a previous attempt created the task but its
           write of `task_id` was lost to a rollback, which a Python-only guard
           would never notice and which would otherwise produce a second task.
        3. Otherwise create inside a savepoint and flush. If a concurrent
           transaction won the race, the UNIQUE constraint on
           `project.task.c2p_meeting_action_ref` raises a unique violation; the
           savepoint keeps the rest of the transaction usable, and we adopt the
           winner's task instead of creating a rival.

        Layer 3 is the one the requirement actually asks for: two simultaneous
        requests cannot both insert, because the database refuses the second.
        A check-then-create in Python cannot make that promise.
        """
        Task = self.env["project.task"]
        created = Task.browse()
        for action in self:
            if action.state not in ("approved", "converted"):
                raise UserError(_(
                    "Action %(ref)s is %(state)s. Only an approved action "
                    "becomes a task.",
                    ref=action.reference, state=action.state))
            if not action.reference:
                raise UserError(_("Action has no reference, so it cannot be "
                                  "converted safely."))
            if action.task_id:
                created |= action.task_id
                continue

            existing = Task.with_context(active_test=False).search(
                [("c2p_meeting_action_ref", "=", action.reference)], limit=1)
            if existing:
                action._adopt_task(existing)
                created |= existing
                continue

            vals = action._task_values()
            try:
                with self.env.cr.savepoint():
                    task = Task.create(vals)
                    # Force the INSERT now, inside the savepoint, so a losing
                    # race surfaces here instead of at commit.
                    self.env.flush_all()
            except IntegrityError as exc:
                if exc.pgcode != errorcodes.UNIQUE_VIOLATION:
                    raise
                # The cache believes in a task that was rolled back.
                self.env.invalidate_all()
                task = Task.with_context(active_test=False).search(
                    [("c2p_meeting_action_ref", "=", action.reference)],
                    limit=1)
                if not task:
                    raise UserError(_(
                        "Action %s could not be converted: a unique conflict "
                        "occurred but no existing task carries its reference. "
                        "This needs looking at rather than retrying.",
                        action.reference)) from exc
            action._adopt_task(task)
            created |= task
        return created

    def _task_values(self):
        self.ensure_one()
        project = self.project_id or self.meeting_id.project_id
        if not project:
            raise UserError(_(
                "Action %s has no project, so there is nowhere to create the "
                "task.", self.reference))
        vals = {
            "name": self.name,
            "project_id": project.id,
            "user_ids": [(6, 0, [self.user_id.id])] if self.user_id else False,
            "date_deadline": self._task_deadline(),
            "description": self._task_description(),
            "c2p_meeting_action_ref": self.reference,
        }
        if self.milestone_id:
            vals["milestone_id"] = self.milestone_id.id
        if self.parent_task_id:
            vals["parent_id"] = self.parent_task_id.id
        return vals

    def _task_deadline(self):
        """The action's target date as a task deadline.

        project.task.date_deadline is a Datetime in Odoo 19. A bare date is
        stored as midnight UTC, which is the previous day for anyone west of
        Greenwich. Noon UTC is the same calendar date in every timezone from
        UTC-11 to UTC+11, so the task is due on the day the minutes say.
        """
        self.ensure_one()
        if not self.date_deadline:
            return False
        return datetime.combine(self.date_deadline, time(12, 0))

    def _task_description(self):
        """Keep the provenance on the task itself.

        Someone opening the task months later should be able to see which
        meeting it came from without knowing this module exists.

        The meeting title and the action's notes are user-entered, so they are
        escaped: `Markup(...) % value` escapes the operand while leaving the
        surrounding tags live. f-string interpolation here would store whatever
        markup somebody typed into the minutes.
        """
        self.ensure_one()
        meeting = self.meeting_id
        when = fields.Datetime.to_string(meeting.meeting_date) \
            if meeting.meeting_date else ""
        parts = [
            Markup("<p><b>%s:</b> %s — %s</p>") % (
                _("From minutes"), meeting.reference or "", meeting.title or ""),
            Markup("<p><b>%s:</b> %s</p>") % (_("Held on"), when),
            Markup("<p><b>%s:</b> %s</p>") % (
                _("Action reference"), self.reference or ""),
        ]
        if self.notes:
            parts.append(Markup("<p>%s</p>") % self.notes)
        return Markup("").join(parts)

    def _adopt_task(self, task):
        self.ensure_one()
        self.write({"task_id": task.id, "state": "converted"})
        self.message_post(body=_(
            "Converted to task %s.", task.display_name or task.name))
        task.message_post(body=_(
            "Created from meeting action %(ref)s (%(meeting)s).",
            ref=self.reference,
            meeting=self.meeting_id.display_name or ""))

    def action_open_task(self):
        self.ensure_one()
        if not self.task_id:
            raise UserError(_("This action has not been converted yet."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "project.task",
            "res_id": self.task_id.id,
            "views": [[False, "form"]],
        }
