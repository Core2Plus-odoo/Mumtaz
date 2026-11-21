from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class C2pMeeting(models.Model):
    """Minutes of a meeting.

    A record of what was discussed and decided, and the single source of the
    action items that follow from it. Confirming the minutes freezes the
    narrative fields: once people have been sent a decision, editing the record
    of that decision silently is how minutes stop being evidence.
    """

    _name = "c2p.meeting"
    _description = "C2P Meeting Minutes"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "meeting_date desc, id desc"
    _rec_name = "display_name"

    reference = fields.Char(
        string="Reference", readonly=True, copy=False, index=True,
        default=lambda self: _("New"))
    title = fields.Char(string="Subject", required=True, tracking=True)
    display_name = fields.Char(compute="_compute_display_name", store=True)

    meeting_date = fields.Datetime(
        string="Held On", required=True, tracking=True,
        default=fields.Datetime.now)
    duration_minutes = fields.Integer(string="Duration (minutes)")
    location = fields.Char(string="Location or Link")

    project_id = fields.Many2one(
        "project.project", string="Project", index=True, tracking=True,
        help="The project these minutes belong to. Action items default to it.")
    milestone_id = fields.Many2one(
        "project.milestone", string="Milestone",
        domain="[('project_id', '=', project_id)]",
        help="The delivery gate this meeting concerned, where relevant.")
    company_id = fields.Many2one(
        "res.company", string="Company", required=True, index=True,
        default=lambda self: self.env.company)

    organiser_id = fields.Many2one(
        "res.users", string="Chaired By", required=True, tracking=True,
        default=lambda self: self.env.user)
    # Partners rather than users, because external attendees are the common
    # case for client meetings and every internal user has a partner anyway.
    attendee_ids = fields.Many2many(
        "res.partner", string="Attendees", tracking=True)
    absentee_ids = fields.Many2many(
        "res.partner", "c2p_meeting_absentee_rel", "meeting_id", "partner_id",
        string="Apologies")

    agenda = fields.Html(string="Agenda", sanitize=True)
    discussion = fields.Html(string="Discussion", sanitize=True)
    decisions = fields.Html(
        string="Decisions", sanitize=True,
        help="What was decided, as distinct from what was discussed. This is "
             "the part that gets quoted back.")

    action_ids = fields.One2many(
        "c2p.meeting.action", "meeting_id", string="Action Items")
    action_count = fields.Integer(compute="_compute_action_stats")
    action_open_count = fields.Integer(compute="_compute_action_stats")
    action_converted_count = fields.Integer(compute="_compute_action_stats")

    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed"),
         ("cancelled", "Cancelled")],
        default="draft", required=True, tracking=True, index=True)
    confirmed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    confirmed_at = fields.Datetime(readonly=True, copy=False)

    _reference_unique = models.Constraint(
        "UNIQUE(reference)",
        "Two sets of minutes cannot share a reference.")

    @api.depends("reference", "title")
    def _compute_display_name(self):
        for meeting in self:
            ref = meeting.reference or ""
            meeting.display_name = f"{ref} {meeting.title or ''}".strip()

    @api.depends("action_ids.state")
    def _compute_action_stats(self):
        for meeting in self:
            actions = meeting.action_ids
            meeting.action_count = len(actions)
            meeting.action_open_count = len(
                actions.filtered(lambda a: a.state in ("draft", "proposed")))
            meeting.action_converted_count = len(
                actions.filtered(lambda a: a.state == "converted"))

    @api.constrains("milestone_id", "project_id")
    def _check_milestone_project(self):
        for meeting in self:
            if meeting.milestone_id and meeting.project_id and \
                    meeting.milestone_id.project_id != meeting.project_id:
                raise ValidationError(_(
                    "Milestone %(ms)s belongs to project %(other)s, not "
                    "%(this)s.",
                    ms=meeting.milestone_id.display_name,
                    other=meeting.milestone_id.project_id.display_name,
                    this=meeting.project_id.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("reference") or vals["reference"] == _("New"):
                vals["reference"] = self.env["ir.sequence"].next_by_code(
                    "c2p.meeting") or _("New")
        return super().create(vals_list)

    # The narrative is evidence once confirmed. Action items stay editable,
    # because following them up is the point.
    FROZEN_AFTER_CONFIRM = (
        "title", "meeting_date", "attendee_ids", "absentee_ids",
        "agenda", "discussion", "decisions", "project_id", "milestone_id",
    )

    def write(self, vals):
        locked = self.filtered(lambda m: m.state == "confirmed")
        if locked and not self.env.user.has_group(
                "c2p_meeting_actions.group_c2p_meeting_approver"):
            touched = set(vals) & set(self.FROZEN_AFTER_CONFIRM)
            if touched:
                raise UserError(_(
                    "These minutes are confirmed, so %(fields)s cannot be "
                    "changed. Ask an approver to reopen them, which is "
                    "recorded.", fields=", ".join(sorted(touched))))
        return super().write(vals)

    def action_confirm(self):
        for meeting in self:
            if meeting.state != "draft":
                raise UserError(_("Only draft minutes can be confirmed."))
            if not meeting.attendee_ids:
                raise UserError(_(
                    "Minutes without attendees are not minutes. Record who "
                    "was there before confirming."))
            meeting.write({
                "state": "confirmed",
                "confirmed_by_id": self.env.uid,
                "confirmed_at": fields.Datetime.now(),
            })
        return True

    def action_reopen(self):
        """Reopen confirmed minutes. Approver-only, and it leaves a trail."""
        if not self.env.user.has_group(
                "c2p_meeting_actions.group_c2p_meeting_approver"):
            raise UserError(_("Only a meeting approver can reopen confirmed "
                              "minutes."))
        for meeting in self.filtered(lambda m: m.state == "confirmed"):
            meeting.write({"state": "draft", "confirmed_by_id": False,
                           "confirmed_at": False})
            meeting.message_post(body=_("Minutes reopened for editing."))
        return True

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True

    def action_view_actions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Action Items"),
            "res_model": "c2p.meeting.action",
            "domain": [("meeting_id", "=", self.id)],
            "views": [[False, "list"], [False, "form"]],
            "context": {"default_meeting_id": self.id},
        }

    def action_convert_approved(self):
        """Convert every approved action on these minutes. Idempotent."""
        self.ensure_one()
        approved = self.action_ids.filtered(lambda a: a.state == "approved")
        if not approved:
            raise UserError(_("No approved action items are waiting to be "
                              "converted."))
        approved.action_create_task()
        return True
