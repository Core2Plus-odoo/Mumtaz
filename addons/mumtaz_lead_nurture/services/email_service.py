"""
Email Service
=============
Sends campaign sequence emails via Odoo native mail.template.
Logs each send to lead.nurture.log.
"""

import logging

from odoo import fields

_logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, env):
        self.env = env

    def send_step_email(self, lead, step, campaign=None):
        """
        Send the email defined in step.mail_template_id to the lead.
        Returns True on success, False on failure.
        """
        template = step.mail_template_id
        if not template:
            _logger.warning("Step %s has no email template — skipping", step.id)
            return False

        recipient = lead.email_from
        if not recipient:
            _logger.warning("Lead %s has no email address — skipping email step", lead.id)
            self._log(lead, step, campaign, "failed", subject="No email address")
            return False

        try:
            template.send_mail(lead.id, force_send=True, raise_exception=True)
            self._log(
                lead, step, campaign, "sent",
                subject=template.subject or step.name,
                body_preview=self._get_body_preview(template, lead),
            )
            return True
        except Exception as exc:
            _logger.exception("Email send failed for lead %s step %s", lead.id, step.id)
            self._log(lead, step, campaign, "failed", subject=str(exc))
            return False

    def _get_body_preview(self, template, lead):
        """Render a short preview of the email body."""
        try:
            rendered = template._render_field("body_html", [lead.id], compute_lang=True)
            html = rendered.get(lead.id, "")
            # Strip HTML tags for preview
            import re
            plain = re.sub(r"<[^>]+>", " ", html)
            plain = " ".join(plain.split())
            return plain[:300]
        except Exception:
            return ""

    def _log(self, lead, step, campaign, status, subject="", body_preview="", score_change=0):
        self.env["lead.nurture.log"].create({
            "lead_id": lead.id,
            "campaign_id": campaign.id if campaign else (step.campaign_id.id if step else False),
            "step_id": step.id if step else False,
            "channel": "email",
            "status": status,
            "timestamp": fields.Datetime.now(),
            "subject": subject,
            "body_preview": body_preview,
            "score_change": score_change,
        })
