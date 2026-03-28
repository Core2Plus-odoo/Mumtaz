"""
WhatsApp Service
================
Provider-agnostic WhatsApp sending abstraction.

Concrete providers:
  - WhatsAppCloudProvider  (Meta Cloud API)
  - TwilioProvider         (Twilio WhatsApp)
  - ManualProvider         (log-only, no actual send)

Usage:
    svc = WhatsAppService(env)
    svc.send_step_whatsapp(lead, step)
"""

import logging

from odoo import fields

_logger = logging.getLogger(__name__)


# ── Base provider ──────────────────────────────────────────────────────────

class BaseWhatsAppProvider:
    def send(self, to_number, message, template=None):
        """
        Send a WhatsApp message.

        :param to_number: recipient phone number (E.164 format preferred)
        :param message: rendered message text
        :param template: lead.whatsapp.template record (for provider template name)
        :returns: (success: bool, provider_ref: str)
        """
        raise NotImplementedError


# ── WhatsApp Cloud API (Meta) ─────────────────────────────────────────────

class WhatsAppCloudProvider(BaseWhatsAppProvider):
    def __init__(self, provider_rec):
        self.phone_number_id = provider_rec.wa_phone_number_id
        self.access_token = provider_rec.wa_access_token
        self.api_version = provider_rec.wa_api_version or "v18.0"

    def send(self, to_number, message, template=None):
        try:
            import requests as req
        except ImportError:
            return False, "requests library not installed"

        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        # Use approved template if available, else freeform text
        if template and template.wa_template_name:
            payload = {
                "messaging_product": "whatsapp",
                "to": self._normalize_number(to_number),
                "type": "template",
                "template": {
                    "name": template.wa_template_name,
                    "language": {"code": template.wa_template_language or "en_US"},
                },
            }
        else:
            payload = {
                "messaging_product": "whatsapp",
                "to": self._normalize_number(to_number),
                "type": "text",
                "text": {"body": message},
            }

        resp = req.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            ref = resp.json().get("messages", [{}])[0].get("id", "")
            return True, ref
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"

    def _normalize_number(self, number):
        """Strip non-digits except leading +."""
        import re
        n = re.sub(r"[^\d+]", "", number or "")
        if n and not n.startswith("+"):
            n = "+" + n
        return n


# ── Twilio ────────────────────────────────────────────────────────────────

class TwilioProvider(BaseWhatsAppProvider):
    def __init__(self, provider_rec):
        self.account_sid = provider_rec.twilio_account_sid
        self.auth_token = provider_rec.twilio_auth_token
        self.from_number = provider_rec.twilio_from_number

    def send(self, to_number, message, template=None):
        try:
            import requests as req
        except ImportError:
            return False, "requests library not installed"

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        to_wa = to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}"
        data = {
            "From": self.from_number,
            "To": to_wa,
            "Body": message,
        }
        resp = req.post(url, data=data, auth=(self.account_sid, self.auth_token), timeout=15)
        if resp.status_code in (200, 201):
            ref = resp.json().get("sid", "")
            return True, ref
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"


# ── Manual (log-only) ─────────────────────────────────────────────────────

class ManualProvider(BaseWhatsAppProvider):
    def send(self, to_number, message, template=None):
        _logger.info("WhatsApp [MANUAL] → %s: %s", to_number, message[:100])
        return True, "manual"


# ── Factory ───────────────────────────────────────────────────────────────

def _get_concrete_provider(provider_rec):
    if not provider_rec:
        return ManualProvider(None) if True else None
    pt = provider_rec.provider_type
    if pt == "whatsapp_cloud":
        return WhatsAppCloudProvider(provider_rec)
    if pt == "twilio":
        return TwilioProvider(provider_rec)
    return ManualProvider(provider_rec)


# ── Service ───────────────────────────────────────────────────────────────

class WhatsAppService:
    def __init__(self, env):
        self.env = env

    def send_step_whatsapp(self, lead, step, campaign=None):
        """
        Send the WhatsApp message defined in step.wa_template_id.
        Returns True on success, False on failure.
        """
        wa_template = step.wa_template_id
        if not wa_template:
            _logger.warning("Step %s has no WhatsApp template", step.id)
            return False

        phone = lead.mobile or lead.phone
        if not phone:
            _logger.warning("Lead %s has no phone number — skipping WhatsApp step", lead.id)
            self._log(lead, step, campaign, "failed", subject="No phone number")
            return False

        message = wa_template.render_body(lead)
        provider_rec = wa_template.provider_id or self.env["lead.whatsapp.provider"].get_default_provider()
        provider = _get_concrete_provider(provider_rec)

        try:
            success, ref = provider.send(phone, message, template=wa_template)
        except Exception as exc:
            _logger.exception("WhatsApp send error for lead %s", lead.id)
            self._log(lead, step, campaign, "failed", subject=str(exc))
            return False

        status = "sent" if success else "failed"
        self._log(
            lead, step, campaign, status,
            subject=wa_template.name,
            body_preview=message[:300],
            provider_ref=ref,
        )
        return success

    def _log(self, lead, step, campaign, status, subject="", body_preview="", provider_ref="", score_change=0):
        self.env["lead.nurture.log"].create({
            "lead_id": lead.id,
            "campaign_id": campaign.id if campaign else (step.campaign_id.id if step else False),
            "step_id": step.id if step else False,
            "channel": "whatsapp",
            "status": status,
            "timestamp": fields.Datetime.now(),
            "subject": subject,
            "body_preview": body_preview,
            "provider_ref": provider_ref,
            "score_change": score_change,
        })
