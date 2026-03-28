"""
Sequence Runner
===============
Advances a lead to its next campaign sequence step.
Called by the hourly cron job via crm.lead.action_run_nurture_sequences().

Step execution dispatch:
  email     → EmailService.send_step_email()
  whatsapp  → WhatsAppService.send_step_whatsapp()
  activity  → mail.activity created on lead
"""

import datetime
import logging

from odoo import fields

from .email_service import EmailService
from .whatsapp_service import WhatsAppService
from .scoring_engine import ScoringEngine

_logger = logging.getLogger(__name__)


class SequenceRunner:
    def __init__(self, env):
        self.env = env
        self.email_svc = EmailService(env)
        self.wa_svc = WhatsAppService(env)
        self.scoring = ScoringEngine(env)

    def advance(self, lead):
        """
        Execute the next pending step for the lead.
        If no more steps remain, marks the lead's nurture_stage as 'nurturing'
        (sequence complete — manual follow-up expected).
        """
        campaign = lead.nurture_campaign_id
        if not campaign:
            return

        next_step = self._get_next_step(lead, campaign)
        if not next_step:
            # All steps done
            if lead.nurture_stage not in ("responded", "qualified", "converted", "dead"):
                lead.write({"nurture_stage": "nurturing", "next_followup_date": False})
            _logger.info("Sequence complete for lead %s (campaign: %s)", lead.id, campaign.name)
            return

        _logger.info(
            "Advancing lead %s → step %s (%s / %s)",
            lead.id, next_step.step_number, next_step.name, next_step.channel,
        )

        success = self._execute_step(lead, next_step, campaign)

        # Update lead state
        now = fields.Datetime.now()
        today = fields.Date.today()
        next_date = today + datetime.timedelta(days=next_step.delay_days or 1)

        vals = {
            "nurture_sequence_step": next_step.step_number,
            "last_outreach_date": now,
            "next_followup_date": next_date,
        }
        if lead.nurture_stage in ("new", "enrolled"):
            vals["nurture_stage"] = "contacted" if next_step.step_number == 1 else "nurturing"
        elif lead.nurture_stage == "contacted":
            vals["nurture_stage"] = "nurturing"

        lead.write(vals)

        # Apply per-step score
        if next_step.score_on_send and success:
            channel_event = "email_sent" if next_step.channel == "email" else "whatsapp_sent"
            self.scoring.apply_event(lead, channel_event)

    def _get_next_step(self, lead, campaign):
        """Return the next active step after lead's current step number."""
        return self.env["lead.nurture.step"].search(
            [
                ("campaign_id", "=", campaign.id),
                ("step_number", ">", lead.nurture_sequence_step),
                ("active", "=", True),
            ],
            order="step_number asc",
            limit=1,
        )

    def _execute_step(self, lead, step, campaign):
        if step.channel == "email":
            return self.email_svc.send_step_email(lead, step, campaign)

        if step.channel == "whatsapp":
            return self.wa_svc.send_step_whatsapp(lead, step, campaign)

        if step.channel == "activity":
            return self._create_activity(lead, step, campaign)

        _logger.warning("Unknown channel '%s' in step %s", step.channel, step.id)
        return False

    def _create_activity(self, lead, step, campaign):
        try:
            activity_type = step.activity_type_id
            if not activity_type:
                activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
            if not activity_type:
                _logger.warning("No activity type configured for step %s", step.id)
                return False

            deadline = fields.Date.today() + datetime.timedelta(days=step.activity_deadline_days or 2)
            user = campaign.user_id or self.env.user

            lead.activity_schedule(
                activity_type_id=activity_type.id,
                date_deadline=deadline,
                summary=step.activity_summary or step.name,
                note=step.activity_note or f"Campaign: {campaign.name} — Step {step.step_number}",
                user_id=user.id,
            )
            self.env["lead.nurture.log"].create({
                "lead_id": lead.id,
                "campaign_id": campaign.id,
                "step_id": step.id,
                "channel": "activity",
                "status": "sent",
                "timestamp": fields.Datetime.now(),
                "subject": step.activity_summary or step.name,
            })
            return True
        except Exception:
            _logger.exception("Activity creation failed for lead %s step %s", lead.id, step.id)
            return False
