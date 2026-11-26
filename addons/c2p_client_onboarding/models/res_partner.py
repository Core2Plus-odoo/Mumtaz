from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .c2p_client_document import STANDARD_DOCUMENTS


class ResPartner(models.Model):
    """The client master record is the existing client partner.

    Nothing here is a second client. Engagements are the client's existing
    portfolio projects, read through the standard partner link.
    """

    _inherit = "res.partner"

    c2p_is_client = fields.Boolean(
        string="C2P Client", index=True,
        help="Shows this company in the C2P client master list.")
    c2p_legal_name = fields.Char(
        string="Legal Entity Name",
        help="Exactly as it appears on the contract and the invoice.")
    c2p_contact_role = fields.Selection(
        [("sponsor", "Sponsor"), ("approver", "Acceptance approver"),
         ("project_lead", "Client project lead"), ("finance", "Finance"),
         ("it", "IT / systems"), ("key_user", "Key user")],
        string="Role in Engagement")
    c2p_contact_ids = fields.One2many(
        "res.partner", "parent_id", string="Client Contacts",
        domain=[("type", "=", "contact")])
    c2p_engagement_ids = fields.One2many(
        "project.project", "partner_id", string="Engagements",
        domain=[("c2p_layer", "=", "portfolio")])
    c2p_instance_ids = fields.One2many(
        "c2p.client.instance", "partner_id", string="Instances")
    c2p_document_ids = fields.One2many(
        "c2p.client.document", "partner_id", string="Required Documents")
    c2p_access_ids = fields.One2many(
        "c2p.client.access", "partner_id", string="Access Register")
    c2p_onboarding_state = fields.Selection(
        [("no_engagement", "No engagement"), ("not_started", "Not started"),
         ("in_progress", "In progress"), ("ready", "Ready to confirm"),
         ("onboarded", "Onboarded")],
        string="Onboarding Status", compute="_compute_c2p_onboarding_state",
        store=True, index=True)

    c2p_next_action = fields.Char(
        string="Next Required Action", compute="_compute_c2p_next_action",
        groups="c2p_project_tracker.group_c2p_delivery_member")
    c2p_milestone_ids = fields.Many2many(
        "project.milestone", string="Milestones",
        compute="_compute_c2p_milestone_ids")

    @api.onchange("c2p_is_client")
    def _onchange_c2p_is_client(self):
        # A starting value from what is already on the record, to be checked
        # against the contract rather than retyped.
        if self.c2p_is_client and not self.c2p_legal_name:
            self.c2p_legal_name = self.name

    def _compute_c2p_milestone_ids(self):
        Milestone = self.env["project.milestone"]
        for partner in self:
            projects = partner.project_ids.filtered(
                lambda p: p.c2p_layer in ("portfolio", "delivery"))
            partner.c2p_milestone_ids = Milestone.search(
                [("project_id", "in", projects.ids)], order="deadline, id")

    def _compute_c2p_next_action(self):
        """One sentence: the single thing that should happen next.

        Kickoff blockers come first, then delivery blockers, then everything
        else, each by due date — the order somebody should actually work in.
        """
        today = fields.Date.context_today(self)
        rank = {"kickoff": 0, "delivery": 1, "none": 2}
        for partner in self:
            engagements = partner.c2p_engagement_ids.filtered(
                lambda p: p.c2p_layer == "portfolio")
            if not engagements:
                partner.c2p_next_action = _(
                    "Link this client to its Consultants engagement: set it "
                    "as the customer on the portfolio project.")
                continue
            action = False
            for eng in engagements.sorted("id"):
                if eng.c2p_onboarding_state == "not_started":
                    action = _("Start the onboarding checklist on %s.",
                               eng.display_name)
                elif eng.c2p_onboarding_state == "ready":
                    action = _("Portfolio Manager to confirm onboarding on %s.",
                               eng.display_name)
                elif eng.c2p_onboarding_state == "in_progress":
                    todo = eng.c2p_onboarding_check_ids.filtered(
                        lambda c: c.state == "open").sorted(
                        lambda c: (rank[c.blocks], c.due_date or today, c.id))
                    first = todo[:1]
                    label = dict(first._fields["blocks"].selection)[first.blocks]
                    action = _(
                        "%(check)s — owner %(owner)s, due %(due)s. "
                        "%(blocks)s. %(more)s open in total.",
                        check=first.name,
                        owner=first.owner_id.name or _("nobody yet"),
                        due=first.due_date or _("no date"),
                        blocks=label, more=len(todo))
                if action:
                    break
            if not action:
                expired = partner.c2p_access_ids.filtered("is_expired")
                waiting = partner.c2p_document_ids.filtered(
                    lambda d: d.state in ("required", "requested"))
                if expired:
                    action = _("Revoke or renew %s expired access record(s).",
                               len(expired))
                elif waiting:
                    action = _("Collect %(n)s outstanding document(s), "
                               "starting with: %(first)s.",
                               n=len(waiting), first=waiting[0].name)
                else:
                    action = _("Nothing outstanding.")
            partner.c2p_next_action = action

    @api.depends("c2p_engagement_ids.c2p_onboarding_state",
                 "c2p_engagement_ids.c2p_layer")
    def _compute_c2p_onboarding_state(self):
        """The least-advanced engagement decides: a client with one onboarded
        engagement and one barely started is not 'onboarded'."""
        order = ["not_started", "in_progress", "ready", "onboarded"]
        for partner in self:
            states = partner.c2p_engagement_ids.filtered(
                lambda p: p.c2p_layer == "portfolio"
            ).mapped("c2p_onboarding_state")
            states = [s for s in states if s]
            partner.c2p_onboarding_state = (
                min(states, key=order.index) if states else "no_engagement")

    def action_c2p_add_standard_documents(self):
        """Add whichever standard document rows are missing. Idempotent:
        UNIQUE(partner_id, code) is the guarantee."""
        Document = self.env["c2p.client.document"]
        for partner in self:
            if not partner.is_company:
                raise UserError(_(
                    "The client master record is the company, not a contact."))
            have = set(partner.c2p_document_ids.mapped("code"))
            Document.create([
                {"partner_id": partner.id, "code": code, "name": name,
                 "sequence": seq}
                for seq, (code, name) in enumerate(STANDARD_DOCUMENTS, start=1)
                if code not in have])
        return True
