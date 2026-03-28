import datetime
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LeadNurtureEnrollWizard(models.TransientModel):
    """Enroll one or more CRM leads into a nurture campaign."""

    _name = "lead.nurture.enroll.wizard"
    _description = "Enroll Leads in Campaign"

    lead_ids = fields.Many2many(
        "crm.lead",
        string="Leads to Enroll",
        required=True,
    )
    campaign_id = fields.Many2one(
        "lead.nurture.campaign",
        string="Campaign",
        required=True,
        domain=[("active", "=", True)],
    )
    outreach_channel = fields.Selection(
        [
            ("email", "Email"),
            ("whatsapp", "WhatsApp"),
            ("both", "Email + WhatsApp"),
        ],
        string="Outreach Channel",
        default="email",
    )
    start_immediately = fields.Boolean(
        string="Run First Step Now",
        default=False,
        help="Execute step 1 immediately after enrollment.",
    )

    # Summary
    lead_count = fields.Integer(compute="_compute_lead_count", string="Lead Count")
    already_enrolled_count = fields.Integer(compute="_compute_lead_count", string="Already Enrolled")

    @api.depends("lead_ids", "campaign_id")
    def _compute_lead_count(self):
        for rec in self:
            rec.lead_count = len(rec.lead_ids)
            if rec.campaign_id:
                rec.already_enrolled_count = len(
                    rec.lead_ids.filtered(lambda l: l.nurture_campaign_id == rec.campaign_id)
                )
            else:
                rec.already_enrolled_count = 0

    def action_enroll(self):
        self.ensure_one()
        if not self.campaign_id:
            raise UserError(_("Please select a campaign."))

        from ..services.scoring_engine import ScoringEngine
        from ..services.sequence_runner import SequenceRunner

        scoring = ScoringEngine(self.env)
        runner = SequenceRunner(self.env) if self.start_immediately else None

        today = fields.Date.today()
        first_step = self.env["lead.nurture.step"].search(
            [("campaign_id", "=", self.campaign_id.id), ("active", "=", True)],
            order="step_number asc",
            limit=1,
        )
        delay = first_step.delay_days if first_step else 0

        enrolled = 0
        for lead in self.lead_ids:
            if lead.nurture_campaign_id == self.campaign_id:
                continue  # already enrolled in this campaign

            lead.write({
                "nurture_campaign_id": self.campaign_id.id,
                "nurture_sequence_step": 0,
                "nurture_stage": "enrolled",
                "outreach_channel_pref": self.outreach_channel,
                "next_followup_date": today + datetime.timedelta(days=delay),
                "team_id": lead.team_id.id or self.campaign_id.team_id.id or lead.team_id.id,
                "user_id": lead.user_id.id or self.campaign_id.user_id.id or lead.user_id.id,
            })
            scoring.apply_event(lead, "lead_enrolled")
            enrolled += 1

            if runner:
                try:
                    runner.advance(lead)
                except Exception:
                    _logger.exception("Immediate step 1 failed for lead %s", lead.id)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Enrollment Complete"),
                "message": _(
                    "%d lead(s) enrolled in '%s'.", enrolled, self.campaign_id.name
                ),
                "type": "success",
                "sticky": False,
            },
        }
