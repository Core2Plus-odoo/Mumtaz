from datetime import datetime, time

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

LEAD_GROUP = "c2p_project_tracker.group_c2p_delivery_lead"
IN_SCOPE = ("date", "reassign", "task")
# Fields that may only move through the action methods once a change exists.
SEALED = ("state", "decided_by_id", "decided_on", "previous_value",
          "new_value", "change_request_id", "proposed_by_id", "proposed_on",
          "direct_edit", "baseline_deadline")
# What the proposer wrote. Frozen once a decision has been made.
PROPOSAL = ("change_type", "task_id", "milestone_id", "reason", "new_deadline",
            "new_user_id", "name", "details")


class C2pPlanChange(models.Model):
    """A proposed or applied change to the approved delivery plan.

    This is the audit record the plan is changed *through*: the previous and
    new values are captured by the code at the moment of applying, not typed
    by anyone.
    """

    _name = "c2p.plan.change"
    _description = "C2P Plan Change"
    _inherit = ["mail.thread"]
    _order = "id desc"
    _rec_name = "reference"

    reference = fields.Char(readonly=True, copy=False, index=True)
    name = fields.Char(string="Summary")
    change_type = fields.Selection(
        [("date", "Date change"), ("reassign", "Reassign work"),
         ("task", "Adjust task within approved scope"),
         ("scope", "Scope, price or contract change")],
        string="Kind of Change", required=True, default="date", tracking=True)

    task_id = fields.Many2one(
        "project.task", string="Task", index=True, ondelete="restrict")
    milestone_id = fields.Many2one(
        "project.milestone", string="Milestone", index=True,
        ondelete="restrict")
    project_id = fields.Many2one(
        "project.project", string="Solutions Project",
        compute="_compute_project_id", store=True, index=True)
    company_id = fields.Many2one(
        related="project_id.company_id", store=True, index=True)
    affected_deliverables = fields.Char(
        string="Affects", compute="_compute_project_id", store=True)

    reason = fields.Char(required=True, tracking=True)
    details = fields.Text(string="What should change")
    new_deadline = fields.Date(string="Proposed Date")
    new_user_id = fields.Many2one("res.users", string="Proposed Assignee")

    proposed_by_id = fields.Many2one(
        "res.users", string="Proposed By", readonly=True, copy=False,
        default=lambda self: self.env.user, index=True)
    proposed_on = fields.Datetime(
        readonly=True, copy=False, default=fields.Datetime.now)

    previous_value = fields.Char(readonly=True, copy=False)
    new_value = fields.Char(readonly=True, copy=False)
    baseline_deadline = fields.Date(
        string="Original Baseline", readonly=True, copy=False,
        help="The date first committed, kept whatever the forecast becomes.")

    state = fields.Selection(
        [("proposed", "Awaiting decision"), ("approved", "Approved and applied"),
         ("rejected", "Rejected"),
         ("escalated", "Sent to Consultants for approval")],
        default="proposed", required=True, index=True, tracking=True,
        copy=False)
    decided_by_id = fields.Many2one(
        "res.users", string="Decided By", readonly=True, copy=False)
    decided_on = fields.Datetime(readonly=True, copy=False)
    decision_note = fields.Char(string="Decision Note")
    direct_edit = fields.Boolean(
        string="Direct Edit", readonly=True, copy=False,
        help="The delivery owner changed the plan directly; this row was "
             "written automatically so the change is still on record.")
    change_request_id = fields.Many2one(
        "c2p.change.request", string="Consultants Change Request",
        readonly=True, copy=False, index=True)
    change_request_state = fields.Selection(
        related="change_request_id.state", string="Consultants Decision")

    _change_request_unique = models.Constraint(
        "UNIQUE(change_request_id)",
        "That change request already belongs to another plan change.")

    @api.depends("task_id", "milestone_id")
    def _compute_project_id(self):
        for change in self:
            change.project_id = (change.task_id.project_id
                                 or change.milestone_id.project_id)
            milestone = change.milestone_id or change.task_id.milestone_id
            parts = [p for p in (milestone.name, change.task_id.name) if p]
            change.affected_deliverables = " / ".join(parts)

    @api.constrains("task_id", "milestone_id", "change_type", "new_deadline",
                    "new_user_id")
    def _check_target(self):
        for change in self:
            if not change.task_id and not change.milestone_id:
                raise ValidationError(_(
                    "Say which task or milestone the change is about."))
            if change.direct_edit:
                continue
            if change.change_type == "date" and not change.new_deadline:
                raise ValidationError(_("A date change needs the proposed date."))
            if change.change_type == "reassign" and not (
                    change.task_id and change.new_user_id):
                raise ValidationError(_(
                    "A reassignment needs the task and the proposed assignee."))

    @api.model_create_multi
    def create(self, vals_list):
        labels = dict(self._fields["change_type"].selection)
        for vals in vals_list:
            if not vals.get("reference"):
                vals["reference"] = self.env["ir.sequence"].next_by_code(
                    "c2p.plan.change") or "PC-NEW"
            if not self.env.context.get("c2p_plan_change"):
                # A proposal is always the caller's own, made now, undecided.
                for name in SEALED:
                    vals.pop(name, None)
            if not vals.get("name"):
                target = (self.env["project.task"].browse(vals.get("task_id"))
                          or self.env["project.milestone"].browse(
                              vals.get("milestone_id")))
                vals["name"] = "%s: %s" % (
                    labels.get(vals.get("change_type") or "date"),
                    target.display_name or "")
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("c2p_plan_change"):
            if any(name in vals for name in SEALED):
                raise UserError(_(
                    "A plan change is decided with Approve, Reject or Send to "
                    "Consultants, so the decision is signed."))
            if any(name in vals for name in PROPOSAL) and self.filtered(
                    lambda c: c.state != "proposed"):
                raise UserError(_(
                    "This change has been decided and is now part of the "
                    "audit history. Raise a new change instead."))
        return super().write(vals)

    def unlink(self):
        raise UserError(_(
            "Plan changes are the audit history of the plan and are not "
            "deleted. Reject one that should not go ahead."))

    def action_submit_proposal(self):
        """The form's Submit button. Pressing it saves the record, and a saved
        proposal is already awaiting a decision, so there is nothing more to
        do here."""
        return True

    # ── decisions ────────────────────────────────────────────────────────
    def _require_lead(self):
        if not self.env.user.has_group(LEAD_GROUP):
            raise AccessError(_(
                "Only the delivery owner can decide a plan change."))

    def _decide(self, state, extra=None):
        vals = {"state": state, "decided_by_id": self.env.uid,
                "decided_on": fields.Datetime.now()}
        vals.update(extra or {})
        self.with_context(c2p_plan_change=True).write(vals)

    def _require_proposed(self):
        for change in self:
            if change.state != "proposed":
                raise UserError(_(
                    "%s has already been decided.", change.reference))

    def action_approve(self):
        """Approve an in-scope change and apply it to the plan."""
        self._require_lead()
        self._require_proposed()
        for change in self:
            if change.change_type not in IN_SCOPE:
                raise UserError(_(
                    "%s changes scope, price or a contractual commitment. "
                    "The delivery owner cannot approve it: send it to "
                    "Consultants.", change.reference))
            change._decide("approved", change._apply())
        return True

    def action_reject(self):
        self._require_lead()
        self._require_proposed()
        for change in self:
            if not (change.decision_note or "").strip():
                raise UserError(_(
                    "Write a decision note first, so the proposer knows why "
                    "%s was rejected.", change.reference))
        self._decide("rejected")
        return True

    def action_send_to_consultants(self):
        """Hand a scope change to Consultants as one standard change request.

        Nothing in the plan changes here. The request is created once — the
        link is unique — and the engagement's own approval flow takes over.
        """
        self._require_lead()
        self._require_proposed()
        for change in self:
            if change.change_request_id:
                continue
            # sudo: the engagement is in the Consultants company; only its id is used
            portfolio = change.project_id.sudo().c2p_counterpart_id
            if not portfolio or portfolio.c2p_layer != "portfolio":
                raise UserError(_(
                    "%s is not linked to a Consultants engagement, so there "
                    "is nobody to send this to.",
                    change.project_id.display_name))
            body = Markup("<p><b>%s</b> %s</p><p>%s</p><p>%s</p>") % (
                _("Raised from plan change"), change.reference,
                change.reason, change.details or "")
            # sudo: a delivery owner may read change requests but not create them; this creates one draft for Consultants to decide
            request = self.env["c2p.change.request"].sudo().create({
                "name": change.name, "project_id": portfolio.id,
                "description": body,
                "requested_by_id": change.proposed_by_id.partner_id.id,
            })
            change._decide("escalated", {"change_request_id": request.id})
            change._notify_account_owner(_(
                "Scope change %(ref)s needs a Consultants decision: "
                "%(name)s.", ref=request.reference, name=change.name))
        return True

    # ── applying ─────────────────────────────────────────────────────────
    def _apply(self):
        """Change the plan and return the before/after to store."""
        self.ensure_one()
        ctx = {"c2p_plan_change": True}
        if self.change_type == "date":
            if self.milestone_id and not self.task_id:
                ms = self.milestone_id
                old = ms.deadline
                baseline = ms.c2p_baseline_deadline or old
                ms.with_context(**ctx).write({
                    "deadline": self.new_deadline,
                    "c2p_baseline_deadline": baseline})
                self._notify_account_owner(_(
                    "Milestone %(ms)s moved from %(old)s to %(new)s "
                    "(baseline %(base)s). Reason: %(why)s",
                    ms=ms.name, old=old or _("no date"), new=self.new_deadline,
                    base=baseline or _("not set"), why=self.reason))
                return {"previous_value": str(old or ""),
                        "new_value": str(self.new_deadline),
                        "baseline_deadline": baseline}
            task = self.task_id
            old = task.date_deadline and task.date_deadline.date()
            task.with_context(**ctx).write({
                "date_deadline": datetime.combine(self.new_deadline, time(12))})
            return {"previous_value": str(old or ""),
                    "new_value": str(self.new_deadline),
                    "baseline_deadline": old}
        if self.change_type == "reassign":
            task = self.task_id
            old = ", ".join(task.user_ids.mapped("name"))
            task.with_context(**ctx).write(
                {"user_ids": [(6, 0, [self.new_user_id.id])]})
            return {"previous_value": old, "new_value": self.new_user_id.name}
        # An in-scope task adjustment is described, approved and then made by
        # the delivery owner; there is no single field to move.
        return {"new_value": self.details or self.name}

    def _notify_account_owner(self, text):
        """Tell the Consultants account owner, on the engagement itself."""
        self.ensure_one()
        # sudo: the engagement is in the Consultants company; posts one note and one activity, reads nothing back
        portfolio = self.project_id.sudo().c2p_counterpart_id
        if not portfolio:
            return
        owner = portfolio.account_manager_id or portfolio.user_id
        # Posted across the company boundary, so say who actually did it.
        text = _("%(who)s: %(text)s", who=self.env.user.name, text=text)
        portfolio.message_post(body=text, subtype_xmlid="mail.mt_note")
        if owner:
            portfolio.activity_schedule(
                "mail.mail_activity_data_todo", user_id=owner.id,
                summary=_("Plan change %s", self.reference), note=text)

    # ── direct edits by the delivery owner ───────────────────────────────
    @api.model
    def _log_direct_edit(self, change_type, previous, new, task=None,
                         milestone=None, baseline=None):
        reason = self.env.context.get("c2p_plan_reason") or _(
            "No reason recorded (direct edit)")
        return self.with_context(c2p_plan_change=True).create({
            "change_type": change_type,
            "task_id": task.id if task else False,
            "milestone_id": milestone.id if milestone else False,
            "reason": reason, "direct_edit": True, "state": "approved",
            "proposed_by_id": self.env.uid, "decided_by_id": self.env.uid,
            "proposed_on": fields.Datetime.now(),
            "decided_on": fields.Datetime.now(),
            "previous_value": previous, "new_value": new,
            "baseline_deadline": baseline,
        })
