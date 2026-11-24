from odoo import _, api, fields, models
from odoo.exceptions import UserError

# The onboarding gate from docs/project/phase1/02-WORKFLOW.md §3.
# Each row: code, label, why it is a gate, what a gap blocks, who owns it
# ("am" = the engagement's account manager, "pm" = the Solutions project manager).
GATE_CHECKS = [
    ("legal_entity", "Correct legal client entity",
     "The invoice and the contract must name the same entity.", "kickoff", "am"),
    ("client_contacts", "Named client contacts, with roles",
     "Acceptance needs a named approver, not 'the client'.", "kickoff", "am"),
    ("scope", "Agreed scope and exclusions approved",
     "Exclusions stop the first change request becoming an argument.",
     "kickoff", "am"),
    ("deliverables", "Contracted deliverables recorded",
     "The milestone plan is built from these.", "delivery", "am"),
    ("acceptance", "Acceptance method per deliverable",
     "Decide how 'done' is proved before doing the work.", "delivery", "am"),
    ("schedule", "Schedule assumptions recorded",
     "A date without its assumption is a promise nobody can keep.",
     "kickoff", "am"),
    ("payment", "Payment milestones recorded",
     "Billing eligibility is derived from these.", "none", "am"),
    ("confidentiality", "Confidentiality and access requirements",
     "Decides whether a subcontractor may see anything at all.",
     "delivery", "am"),
    ("solutions_owner", "Solutions project linked, with a project manager",
     "Unowned projects are how delivery drifts.", "kickoff", "pm"),
]
# Checks with nothing in the database to verify yet: they need a written note
# saying where the evidence is.
NOTE_REQUIRED = ("deliverables", "acceptance", "schedule", "payment")


class C2pOnboardingCheck(models.Model):
    _name = "c2p.onboarding.check"
    _description = "C2P Onboarding Check"
    _order = "project_id, sequence, id"

    project_id = fields.Many2one(
        "project.project", string="Engagement", required=True, index=True,
        ondelete="cascade", domain="[('c2p_layer', '=', 'portfolio')]")
    partner_id = fields.Many2one(
        related="project_id.partner_id", string="Client", store=True,
        index=True)
    company_id = fields.Many2one(
        related="project_id.company_id", store=True, index=True)
    code = fields.Char(required=True, readonly=True)
    name = fields.Char(string="Check", required=True)
    why = fields.Char(string="Why it is a gate")
    sequence = fields.Integer(default=10)
    state = fields.Selection(
        [("open", "Open"), ("done", "Done"), ("na", "Not applicable")],
        default="open", required=True, index=True, copy=False)
    owner_id = fields.Many2one(
        "res.users", string="Owner", index=True,
        help="The C2P person responsible for closing this item.")
    due_date = fields.Date(string="Due")
    blocks = fields.Selection(
        [("kickoff", "Blocks kickoff"), ("delivery", "Blocks delivery"),
         ("none", "Does not block")],
        string="If missing", default="none", required=True)
    is_overdue = fields.Boolean(compute="_compute_is_overdue")
    note = fields.Char(
        string="Evidence",
        help="Where the evidence is: a document reference, a section, a date.")
    na_reason = fields.Char(string="Reason not applicable")
    done_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    done_on = fields.Datetime(readonly=True, copy=False)

    _project_code_unique = models.Constraint(
        "UNIQUE(project_id, code)",
        "This engagement already has that onboarding check.")

    @api.depends("due_date", "state")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for check in self:
            check.is_overdue = bool(
                check.state == "open" and check.due_date
                and check.due_date < today)

    @api.constrains("project_id")
    def _check_portfolio(self):
        for check in self:
            if check.project_id.c2p_layer != "portfolio":
                raise UserError(_(
                    "Onboarding checks belong to the Consultants engagement "
                    "(portfolio project)."))

    def write(self, vals):
        if not self.env.context.get("c2p_onboarding_transition"):
            if any(k in vals for k in ("state", "done_by_id", "done_on", "code")):
                raise UserError(_(
                    "Use Done, Not applicable or Reopen so the check is "
                    "verified and signed."))
            if self.filtered(lambda c: c.project_id.c2p_onboarded_on):
                raise UserError(_(
                    "Onboarding is confirmed for this engagement. A Portfolio "
                    "Manager must reopen it before a check is changed."))
        return super().write(vals)

    def _c2p_set_state(self, state):
        done = state in ("done", "na")
        self.with_context(c2p_onboarding_transition=True).write({
            "state": state,
            "done_by_id": self.env.uid if done else False,
            "done_on": fields.Datetime.now() if done else False,
        })

    def _c2p_guard_open_engagement(self):
        for check in self:
            if check.project_id.c2p_onboarded_on:
                raise UserError(_(
                    "Onboarding is confirmed for %s. A Portfolio Manager must "
                    "reopen it first.", check.project_id.display_name))

    # ── evidence ─────────────────────────────────────────────────────────
    def _c2p_missing_evidence(self):
        """Why this check cannot be ticked yet, or False when it can.

        Where the database holds the fact, the fact is checked. Where it does
        not (deliverables, acceptance, schedule, payment have no model yet), a
        written note is required instead of pretending to verify.
        """
        self.ensure_one()
        project = self.project_id
        client = project.partner_id.commercial_partner_id
        if self.code == "legal_entity":
            if not client.is_company or not (client.c2p_legal_name or "").strip():
                return _("the client must be a company with its legal name "
                         "recorded")
        elif self.code == "client_contacts":
            roles = client.c2p_contact_ids.mapped("c2p_contact_role")
            if "approver" not in roles:
                return _("the client needs a named contact with the role "
                         "'Acceptance approver'")
        elif self.code == "scope":
            if project.c2p_scope_state != "approved":
                return _("the scope has not been approved")
        elif self.code == "confidentiality":
            nda = client.c2p_document_ids.filtered(lambda d: d.code == "nda")
            if not nda or nda.filtered(
                    lambda d: d.state not in ("received", "verified", "na")):
                return _("the NDA / confidentiality document must be received, "
                         "verified or marked not applicable")
        elif self.code == "solutions_owner":
            if not project.c2p_counterpart_id:
                return _("no Solutions project is linked as the counterpart")
            if not project.c2p_delivery_lead_id:
                return _("the Solutions project has no project manager")
        elif self.code in NOTE_REQUIRED and not (self.note or "").strip():
            return _("write where the evidence is in the note")
        return False

    def action_done(self):
        self._c2p_guard_open_engagement()
        for check in self:
            missing = check._c2p_missing_evidence()
            if missing:
                raise UserError(_(
                    "'%(check)s' cannot be marked done: %(why)s.",
                    check=check.name, why=missing))
        self._c2p_set_state("done")
        return True

    def action_not_applicable(self):
        self._c2p_guard_open_engagement()
        for check in self:
            if not (check.na_reason or "").strip():
                raise UserError(_(
                    "'%s' needs a reason before it can be marked not "
                    "applicable.", check.name))
        self._c2p_set_state("na")
        return True

    def action_reopen(self):
        self._c2p_guard_open_engagement()
        self._c2p_set_state("open")
        return True
