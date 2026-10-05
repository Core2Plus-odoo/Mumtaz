from odoo import _, api, fields, models

SCALE = [("l", "Low"), ("m", "Medium"), ("h", "High")]
SCALE_VALUE = {"l": 1, "m": 2, "h": 3}


class C2pRaidItem(models.Model):
    """Risks, Assumptions, Issues, Dependencies and Decisions for an engagement.

    Odoo has no standard RAID log — project.task is the nearest thing and
    conflates "work to do" with "risk being carried", which is why this is a
    separate model rather than a task type.
    """

    _name = "c2p.raid.item"
    _description = "C2P RAID Item"
    _inherit = ["mail.thread"]
    _order = "score desc, raised_date desc, id desc"

    name = fields.Char(string="Title", required=True, tracking=True)
    project_id = fields.Many2one(
        "project.project", string="Engagement", required=True,
        ondelete="cascade", index=True,
        domain="[('c2p_layer', '=', 'portfolio')]", tracking=True)
    company_id = fields.Many2one(
        "res.company", related="project_id.company_id", store=True, index=True)

    item_type = fields.Selection(
        [("risk", "Risk"), ("assumption", "Assumption"), ("issue", "Issue"),
         ("dependency", "Dependency"), ("decision", "Decision")],
        string="Type", required=True, default="risk", tracking=True)
    description = fields.Html()
    owner_id = fields.Many2one("res.users", string="Owner", tracking=True)
    raised_date = fields.Date(default=fields.Date.context_today, required=True)
    due_date = fields.Date(tracking=True)

    impact = fields.Selection(SCALE, default="m", required=True, tracking=True)
    # Probability only applies to risks: an issue has already happened.
    probability = fields.Selection(SCALE, tracking=True)
    score = fields.Integer(compute="_compute_score", store=True)

    state = fields.Selection(
        [("open", "Open"), ("mitigating", "Mitigating"), ("closed", "Closed")],
        default="open", required=True, tracking=True)
    resolution = fields.Text()

    # A client dependency is usually a task sitting in Waiting on Client, so
    # the two can be joined up rather than tracked twice.
    blocked_task_id = fields.Many2one(
        "project.task", string="Blocked Delivery Task",
        help="The delivery task this dependency is holding up.")

    is_overdue = fields.Boolean(compute="_compute_is_overdue", search="_search_is_overdue")

    @api.depends("impact", "probability", "item_type")
    def _compute_score(self):
        for item in self:
            impact = SCALE_VALUE.get(item.impact, 0)
            if item.item_type == "risk":
                item.score = impact * SCALE_VALUE.get(item.probability, 1)
            else:
                # Non-risks have no probability, so impact alone scales them on
                # the same 1-9 range to keep sorting comparable.
                item.score = impact * 3

    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for item in self:
            item.is_overdue = bool(
                item.state != "closed" and item.due_date and item.due_date < today)

    def _search_is_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        domain = [("state", "!=", "closed"), ("due_date", "<", today)]
        if (operator == "=" and not value) or (operator == "!=" and value):
            return [("id", "not in", self.search(domain).ids)]
        return domain

    @api.onchange("item_type")
    def _onchange_item_type(self):
        if self.item_type != "risk":
            self.probability = False
        elif not self.probability:
            self.probability = "m"


class C2pChangeRequest(models.Model):
    """A scope change, and the audit trail for the contract value moving."""

    _name = "c2p.change.request"
    _description = "C2P Change Request"
    _inherit = ["mail.thread"]
    _order = "id desc"
    _rec_name = "reference"

    reference = fields.Char(copy=False, readonly=True, index=True)
    name = fields.Char(string="Summary", required=True, tracking=True)
    project_id = fields.Many2one(
        "project.project", string="Engagement", required=True,
        ondelete="cascade", index=True,
        domain="[('c2p_layer', '=', 'portfolio')]", tracking=True)
    company_id = fields.Many2one(
        "res.company", related="project_id.company_id", store=True, index=True)

    description = fields.Html()
    requested_by_id = fields.Many2one("res.partner", string="Requested By")
    impact_days = fields.Integer(string="Schedule Impact (days)", tracking=True)
    impact_amount = fields.Monetary(
        string="Commercial Impact", currency_field="currency_id", tracking=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id)

    state = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted to Client"),
         ("approved", "Approved"), ("rejected", "Rejected")],
        default="draft", required=True, tracking=True)
    approved_date = fields.Date(readonly=True, copy=False)
    # Records whether the contract value was already moved, so re-approving
    # cannot add the same amount twice.
    value_applied = fields.Boolean(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("reference"):
                vals["reference"] = self.env["ir.sequence"].next_by_code(
                    "c2p.change.request") or "CR-NEW"
        return super().create(vals_list)

    def action_submit(self):
        self.write({"state": "submitted"})

    def action_reject(self):
        self.write({"state": "rejected"})

    def action_approve(self):
        """Approve and move the contract value once, logging it on the project.

        Writing the project's commercials needs the Portfolio Manager group, so
        this is deliberately not sudo: approval is a manager's action.
        """
        for cr in self:
            cr.write({"state": "approved",
                      "approved_date": fields.Date.context_today(cr)})
            if cr.value_applied or not cr.impact_amount:
                continue
            project = cr.project_id
            before = project.contract_value
            project.contract_value = before + cr.impact_amount
            cr.value_applied = True
            project.message_post(
                body=_("Contract value changed by %(ref)s: %(before)s → "
                       "%(after)s.",
                       ref=cr.reference, before=before,
                       after=project.contract_value),
                subtype_xmlid="mail.mt_note")
        return True
