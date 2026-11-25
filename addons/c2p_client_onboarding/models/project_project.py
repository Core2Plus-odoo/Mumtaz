from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .c2p_onboarding_check import GATE_CHECKS

MANAGER_GROUP = "c2p_project_tracker.group_c2p_portfolio_manager"
SCOPE_FIELDS = ("c2p_scope_reference", "c2p_scope_version",
                "c2p_scope_summary", "c2p_scope_exclusions")
PROTECTED = ("c2p_scope_state", "c2p_scope_approved_by_id",
             "c2p_scope_approved_on", "c2p_onboarded_by_id", "c2p_onboarded_on")


class ProjectProject(models.Model):
    """Scope and onboarding on the existing portfolio project.

    The portfolio project is the Consultants engagement and its counterpart is
    the Solutions project. Everything here hangs off that pair; nothing in this
    file creates a project.
    """

    _inherit = "project.project"

    # ── Approved scope ───────────────────────────────────────────────────
    c2p_scope_reference = fields.Char(
        string="Contract / Order Reference", tracking=True,
        help="The signed contract or approved order this scope comes from.")
    c2p_scope_version = fields.Char(string="Scope Version", tracking=True)
    c2p_scope_summary = fields.Text(string="Agreed Scope")
    c2p_scope_exclusions = fields.Text(string="Exclusions")
    c2p_scope_state = fields.Selection(
        [("draft", "Not approved"), ("approved", "Approved")],
        string="Scope Status", default="draft", copy=False, tracking=True)
    c2p_scope_approved_by_id = fields.Many2one(
        "res.users", string="Scope Approved By", copy=False, readonly=True)
    c2p_scope_approved_on = fields.Datetime(
        string="Scope Approved On", copy=False, readonly=True)

    # ── Responsible staff ────────────────────────────────────────────────
    c2p_delivery_lead_id = fields.Many2one(
        "res.users", string="Solutions Project Manager",
        compute="_compute_c2p_delivery_lead_id",
        help="The project manager of the paired Solutions project.")

    # ── Onboarding ───────────────────────────────────────────────────────
    c2p_onboarding_check_ids = fields.One2many(
        "c2p.onboarding.check", "project_id", string="Onboarding Checklist")
    c2p_onboarding_state = fields.Selection(
        [("not_started", "Not started"), ("in_progress", "In progress"),
         ("ready", "Ready to confirm"), ("onboarded", "Onboarded")],
        string="Onboarding", compute="_compute_c2p_onboarding", store=True,
        index=True)
    c2p_onboarding_progress = fields.Integer(
        string="Checklist %", compute="_compute_c2p_onboarding", store=True)
    c2p_onboarded_by_id = fields.Many2one(
        "res.users", string="Onboarding Confirmed By", copy=False,
        readonly=True)
    c2p_onboarded_on = fields.Datetime(
        string="Onboarding Confirmed On", copy=False, readonly=True)

    @api.depends("c2p_layer", "c2p_counterpart_id", "c2p_counterpart_id.user_id")
    def _compute_c2p_delivery_lead_id(self):
        for project in self:
            # The tracker's own helper: the Solutions project sits in another
            # company, and only the manager's name is taken from it.
            delivery = project._c2p_delivery_project()
            project.c2p_delivery_lead_id = delivery.user_id

    @api.depends("c2p_onboarding_check_ids.state", "c2p_onboarded_on")
    def _compute_c2p_onboarding(self):
        for project in self:
            checks = project.c2p_onboarding_check_ids
            closed = checks.filtered(lambda c: c.state in ("done", "na"))
            project.c2p_onboarding_progress = (
                round(100 * len(closed) / len(checks)) if checks else 0)
            if project.c2p_onboarded_on:
                project.c2p_onboarding_state = "onboarded"
            elif not checks:
                project.c2p_onboarding_state = "not_started"
            elif len(closed) == len(checks):
                project.c2p_onboarding_state = "ready"
            else:
                project.c2p_onboarding_state = "in_progress"

    def write(self, vals):
        if not self.env.context.get("c2p_onboarding_transition"):
            if any(name in vals for name in PROTECTED):
                raise UserError(_(
                    "Scope approval and onboarding confirmation are recorded "
                    "by their buttons, not by editing the fields."))
            if any(name in vals for name in SCOPE_FIELDS) and \
                    self.filtered(lambda p: p.c2p_scope_state == "approved"):
                raise UserError(_(
                    "This scope is approved. Reopen it before changing it, so "
                    "the change is visible and re-approved."))
        return super().write(vals)

    def _c2p_require_manager(self):
        if not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(_(
                "Only a Portfolio Manager can approve scope or confirm "
                "onboarding."))

    def _c2p_require_portfolio(self):
        for project in self:
            if project.c2p_layer != "portfolio":
                raise UserError(_(
                    "%s is not a Consultants engagement (portfolio project). "
                    "Scope and onboarding are recorded on the engagement.",
                    project.display_name))

    # ── Scope approval ───────────────────────────────────────────────────
    def action_c2p_approve_scope(self):
        self._c2p_require_manager()
        self._c2p_require_portfolio()
        for project in self:
            missing = [label for name, label in (
                ("c2p_scope_reference", _("contract or order reference")),
                ("c2p_scope_summary", _("agreed scope")),
                ("c2p_scope_exclusions", _("exclusions")),
            ) if not (project[name] or "").strip()]
            if missing:
                raise UserError(_(
                    "The scope cannot be approved without: %s.",
                    ", ".join(missing)))
            project.with_context(c2p_onboarding_transition=True).write({
                "c2p_scope_state": "approved",
                "c2p_scope_approved_by_id": self.env.uid,
                "c2p_scope_approved_on": fields.Datetime.now(),
            })
        return True

    def action_c2p_reopen_scope(self):
        self._c2p_require_manager()
        self.with_context(c2p_onboarding_transition=True).write({
            "c2p_scope_state": "draft",
            "c2p_scope_approved_by_id": False,
            "c2p_scope_approved_on": False,
        })
        # An approved-scope check cannot stay ticked against an open scope.
        self.c2p_onboarding_check_ids.filtered(
            lambda c: c.code == "scope" and c.state == "done"
        )._c2p_set_state("open")
        return True

    # ── Checklist ────────────────────────────────────────────────────────
    def action_c2p_start_onboarding_checklist(self):
        """Create whichever gate checks this engagement does not have yet.

        Safe to press twice: UNIQUE(project_id, code) is the guarantee, and
        only the missing codes are created.
        """
        self._c2p_require_portfolio()
        Check = self.env["c2p.onboarding.check"]
        for project in self:
            if not project.partner_id:
                raise UserError(_(
                    "%s has no client. Set the customer on the engagement "
                    "first.", project.display_name))
            have = set(project.c2p_onboarding_check_ids.mapped("code"))
            # Owners and dates come from what the engagement already records,
            # so nobody types them twice; both stay editable.
            owners = {
                "am": project.account_manager_id or project.user_id,
                "pm": project.c2p_delivery_lead_id
                or project.account_manager_id or project.user_id,
            }
            today = fields.Date.context_today(self)
            due = max(project.start_date or today, today)
            Check.create([
                {"project_id": project.id, "code": code, "name": name,
                 "why": why, "sequence": seq, "blocks": blocks,
                 "owner_id": owners[role].id, "due_date": due}
                for seq, (code, name, why, blocks, role)
                in enumerate(GATE_CHECKS, start=1)
                if code not in have])
        return True

    def action_c2p_confirm_onboarding(self):
        """Record that the gate was passed, by whom and when.

        This links nothing and creates nothing. Creating the Solutions project
        stays wherever it is created today; a second creation path is exactly
        what the pairing constraint exists to prevent.
        """
        self._c2p_require_manager()
        self._c2p_require_portfolio()
        for project in self:
            if project.c2p_onboarding_state != "ready":
                raise UserError(_(
                    "Onboarding for %s cannot be confirmed: every check must "
                    "be done or marked not applicable with a reason.",
                    project.display_name))
            project.with_context(c2p_onboarding_transition=True).write({
                "c2p_onboarded_by_id": self.env.uid,
                "c2p_onboarded_on": fields.Datetime.now(),
            })
        return True

    # ── Client email: drafted here, sent by a person ─────────────────────
    def action_c2p_draft_welcome_email(self):
        """Open the standard composer with the welcome email drafted.

        Nothing is sent by this method. It refuses to draft from unverified
        facts, then hands a named user the ordinary Odoo composer: they see the
        recipients and the text, change either, and press Send themselves.
        """
        self.ensure_one()
        self._c2p_require_portfolio()
        client = self.partner_id.commercial_partner_id
        missing = []
        if self.c2p_scope_state != "approved":
            missing.append(_("the scope is not approved"))
        if not self.c2p_delivery_lead_id:
            missing.append(_("no Solutions project manager is linked"))
        recipients = client.c2p_contact_ids.filtered(
            lambda c: c.email and c.c2p_contact_role in (
                "sponsor", "approver", "project_lead"))
        if not recipients:
            missing.append(_(
                "no sponsor, approver or project lead contact has an email "
                "address"))
        if missing:
            raise UserError(_(
                "The welcome email is drafted from verified project data, and "
                "some of it is missing: %s.", "; ".join(missing)))
        template = self.env.ref(
            "c2p_client_onboarding.mail_template_c2p_welcome")
        return {
            "type": "ir.actions.act_window",
            "name": _("Review welcome email before sending"),
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_model": "project.project",
                "default_res_ids": self.ids,
                "default_template_id": template.id,
                "default_composition_mode": "comment",
                "default_partner_ids": recipients.ids,
                "default_email_layout_xmlid": "mail.mail_notification_light",
            },
        }

    def action_c2p_reopen_onboarding(self):
        self._c2p_require_manager()
        self.with_context(c2p_onboarding_transition=True).write({
            "c2p_onboarded_by_id": False, "c2p_onboarded_on": False})
        return True
