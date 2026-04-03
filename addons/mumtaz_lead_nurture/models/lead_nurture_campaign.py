from odoo import _, api, fields, models


class LeadNurtureCampaign(models.Model):
    """Defines a nurture campaign with target segment and sequence steps."""

    _name = "lead.nurture.campaign"
    _description = "Lead Nurture Campaign"
    _inherit = ["mail.thread"]
    _order = "name"
    _rec_name = "name"

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    description = fields.Text()

    # ── Targeting ──────────────────────────────────────────────────────
    target_segment = fields.Selection(
        [
            ("all", "All Segments"),
            ("micro", "Micro Business"),
            ("sme", "SME"),
            ("mid", "Mid-Market"),
            ("enterprise", "Enterprise"),
        ],
        default="all",
        tracking=True,
    )
    target_industry = fields.Char(help="Comma-separated industry keywords for targeting")
    target_geography = fields.Char(help="Country / region filter label")

    # ── Defaults for enrolled leads ────────────────────────────────────
    team_id = fields.Many2one("crm.team", string="Default Sales Team")
    user_id = fields.Many2one("res.users", string="Default Salesperson")

    # ── Qualification thresholds ───────────────────────────────────────
    qualification_threshold = fields.Integer(
        default=50,
        help="Nurture score needed to mark a lead as Qualified.",
    )
    auto_convert_threshold = fields.Integer(
        default=80,
        help="Nurture score that triggers automatic conversion to Opportunity.",
    )

    # ── Relations ──────────────────────────────────────────────────────
    step_ids = fields.One2many("lead.nurture.step", "campaign_id", string="Sequence Steps")
    lead_ids = fields.One2many("crm.lead", "nurture_campaign_id", string="Enrolled Leads")

    step_count = fields.Integer(compute="_compute_counts", string="Steps")
    lead_count = fields.Integer(compute="_compute_counts", string="Leads")
    qualified_count = fields.Integer(compute="_compute_counts", string="Qualified")
    converted_count = fields.Integer(compute="_compute_counts", string="Converted")

    @api.depends("step_ids", "lead_ids")
    def _compute_counts(self):
        for rec in self:
            rec.step_count = len(rec.step_ids)
            leads = rec.lead_ids
            rec.lead_count = len(leads)
            rec.qualified_count = len(leads.filtered(lambda l: l.nurture_stage == "qualified"))
            rec.converted_count = len(leads.filtered(lambda l: l.nurture_stage == "converted"))

    def action_view_leads(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Enrolled Leads"),
            "res_model": "crm.lead",
            "view_mode": "list,form",
            "domain": [("nurture_campaign_id", "=", self.id)],
            "context": {"default_nurture_campaign_id": self.id},
        }
