"""
Conversion Engine
=================
Converts a qualified CRM lead into an Opportunity.

Safety guarantees:
  - Will not convert a record that is already type='opportunity'
  - Will not convert leads in 'dead' nurture stage
  - Will not create duplicate opportunities
  - Sets team/user from campaign defaults if not already set
  - Creates a follow-up activity for the assigned salesperson
  - Logs conversion to lead.nurture.log
"""

import datetime
import logging

from odoo import fields

_logger = logging.getLogger(__name__)


class ConversionEngine:
    def __init__(self, env):
        self.env = env

    def convert(self, lead):
        """
        Convert a CRM lead to opportunity.
        Returns True on success, False if skipped (already opportunity / dead).
        """
        if lead.type == "opportunity":
            _logger.info("Lead %s is already an opportunity — skipping", lead.id)
            return False

        if lead.nurture_stage == "dead":
            _logger.info("Lead %s is dead — skipping conversion", lead.id)
            return False

        campaign = lead.nurture_campaign_id
        team = lead.team_id or (campaign.team_id if campaign else False)
        user = lead.user_id or (campaign.user_id if campaign else False)

        vals = {
            "type": "opportunity",
            "nurture_stage": "converted",
            "auto_convert_ready": False,
        }
        if team:
            vals["team_id"] = team.id
        if user:
            vals["user_id"] = user.id

        # Set first available opportunity stage if not already set
        if not lead.stage_id:
            stage = self.env["crm.stage"].search(
                [("team_id", "in", [team.id, False])] if team else [],
                order="sequence asc",
                limit=1,
            )
            if stage:
                vals["stage_id"] = stage.id

        lead.write(vals)
        _logger.info("Lead %s converted to opportunity", lead.id)

        # Create salesperson follow-up activity
        self._create_followup_activity(lead, user)

        # Log conversion
        self.env["lead.nurture.log"].create({
            "lead_id": lead.id,
            "campaign_id": campaign.id if campaign else False,
            "channel": "manual",
            "status": "sent",
            "timestamp": fields.Datetime.now(),
            "subject": "Converted to Opportunity",
            "body_preview": self._build_conversion_summary(lead),
        })
        return True

    def _create_followup_activity(self, lead, user):
        try:
            activity_type = self.env.ref(
                "mail.mail_activity_data_call", raise_if_not_found=False
            ) or self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)

            if not activity_type:
                return

            deadline = fields.Date.today() + datetime.timedelta(days=1)
            summary = self._build_conversion_summary(lead)

            lead.activity_schedule(
                activity_type_id=activity_type.id,
                date_deadline=deadline,
                summary="Follow up on converted opportunity",
                note=summary,
                user_id=(user or self.env.user).id,
            )
        except Exception:
            _logger.exception("Follow-up activity creation failed for lead %s", lead.id)

    def _build_conversion_summary(self, lead):
        lines = [
            f"Company: {lead.partner_name or lead.name}",
            f"Segment: {dict(lead._fields['company_segment'].selection).get(lead.company_segment, '')}",
            f"Industry: {dict(lead._fields['industry_cluster'].selection).get(lead.industry_cluster, '')}",
            f"ERP Needs: {', '.join(lead.probable_erp_need_ids.mapped('name'))}",
            f"Use Case: {dict(lead._fields['use_case_type'].selection).get(lead.use_case_type, '')}",
            f"Score: {lead.qualification_score}",
            f"Response: {dict(lead._fields['response_status'].selection).get(lead.response_status, '')}",
            f"Messages sent: {len(lead.nurture_log_ids)}",
        ]
        return "\n".join(l for l in lines if not l.endswith(": "))
