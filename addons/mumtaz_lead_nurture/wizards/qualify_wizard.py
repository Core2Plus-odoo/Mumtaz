import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LeadNurtureQualifyWizard(models.TransientModel):
    """Manually qualify a lead: set response status, add score, optionally convert."""

    _name = "lead.nurture.qualify.wizard"
    _description = "Qualify Lead"

    lead_id = fields.Many2one("crm.lead", required=True, string="Lead")
    lead_name = fields.Char(related="lead_id.name", readonly=True)
    current_score = fields.Integer(related="lead_id.qualification_score", readonly=True)
    current_stage = fields.Selection(related="lead_id.nurture_stage", readonly=True)

    qualification_event = fields.Selection(
        [
            ("positive_reply", "Positive Reply"),
            ("demo_requested", "Demo Requested"),
            ("requirement_shared", "Requirement Shared"),
            ("manual_qualified", "Manual Qualification"),
            ("not_interested", "Not Interested"),
        ],
        string="Qualification Event",
        required=True,
        default="manual_qualified",
    )
    response_status = fields.Selection(
        [
            ("interested", "Interested"),
            ("demo_requested", "Demo Requested"),
            ("requirement_shared", "Requirement Shared"),
            ("not_interested", "Not Interested"),
        ],
        string="Response Status",
        default="interested",
    )
    notes = fields.Text(string="Notes / Summary")
    convert_to_opportunity = fields.Boolean(
        string="Convert to Opportunity Now",
        default=False,
    )

    # Preview
    score_delta = fields.Integer(compute="_compute_score_delta", string="Score Delta")
    projected_score = fields.Integer(compute="_compute_score_delta", string="Projected Score")

    @api.depends("qualification_event", "lead_id")
    def _compute_score_delta(self):
        from ..services.scoring_engine import DEFAULT_SCORES
        for rec in self:
            delta = DEFAULT_SCORES.get(rec.qualification_event, 0)
            rec.score_delta = delta
            rec.projected_score = max(0, (rec.lead_id.qualification_score or 0) + delta)

    def action_qualify(self):
        self.ensure_one()
        lead = self.lead_id
        if not lead:
            raise UserError(_("No lead selected."))

        from ..services.scoring_engine import ScoringEngine
        from ..services.conversion_engine import ConversionEngine

        scoring = ScoringEngine(self.env)
        scoring.apply_event(lead, self.qualification_event)

        vals = {"response_status": self.response_status}
        if self.qualification_event != "not_interested":
            vals["nurture_stage"] = "responded"
        lead.write(vals)

        # Log manual qualification note
        if self.notes:
            self.env["lead.nurture.log"].create({
                "lead_id": lead.id,
                "channel": "manual",
                "status": "replied",
                "timestamp": fields.Datetime.now(),
                "subject": f"Manual: {dict(self._fields['qualification_event'].selection)[self.qualification_event]}",
                "response_summary": self.notes,
                "score_change": self.score_delta,
            })

        if self.convert_to_opportunity:
            engine = ConversionEngine(self.env)
            engine.convert(lead)

        return {"type": "ir.actions.act_window_close"}
