import logging

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Meta rejects a free-text ("text") message to anyone who has not messaged the
# business in the last 24h — it must be a pre-approved template outside that
# window. None of the five structured transitions below have a real customer
# reply before they fire, so they are business-initiated by definition and
# need a template. `_render_body` already produces the English copy; what is
# missing is Meta's approval of a template that carries it. Each of these
# names is meant to be registered, verbatim, in Meta Business Manager (or as
# a Twilio Content Template) with exactly one body variable — the simplest
# shape to get approved, and the one the code below actually sends.
META_API_VERSION = "v21.0"
META_LANG_CODE = {"en": "en_US", "ur": "ur"}


class ResCompanyWhatsApp(models.Model):
    """WhatsApp send transport, configured per company.

    `faizy.whatsapp.message` only ever queues; nothing here runs on create.
    `_cron_send_queued` drains the queue through `_get_provider()` /
    `_send_whatsapp()`, so turning this on or swapping providers is a Settings
    change, never a code change — exactly the interface docs/00-decisions.md
    §2 asked for (Meta direct as the target, Twilio as the fallback, one flag).
    """

    _inherit = "res.company"

    faizy_whatsapp_provider = fields.Selection(
        [("none", "Not configured"), ("meta", "Meta Cloud API"), ("twilio", "Twilio")],
        string="WhatsApp Provider",
        default="none",
        help="Which transport actually sends queued WhatsApp messages. 'Not "
        "configured' leaves everything queued, same as today.",
    )

    # Meta Cloud API — direct.
    faizy_whatsapp_meta_token = fields.Char(
        string="Meta Access Token",
        help="Permanent access token for the WhatsApp Business app (System User token, "
        "not the 24h test token).",
    )
    faizy_whatsapp_meta_phone_id = fields.Char(
        string="Meta Phone Number ID",
        help="The WhatsApp Business phone number's numeric ID, from Meta Business Manager "
        "— not the phone number itself.",
    )

    # Twilio — launch fallback, per docs/00-decisions.md §2.
    faizy_whatsapp_twilio_sid = fields.Char(string="Twilio Account SID")
    faizy_whatsapp_twilio_token = fields.Char(string="Twilio Auth Token")
    faizy_whatsapp_twilio_from = fields.Char(
        string="Twilio WhatsApp Sender",
        help="The Twilio number enabled for WhatsApp, e.g. +14155238886.",
    )

    def _faizy_whatsapp_configured(self):
        """Whether enough credentials exist to even attempt a send."""
        self.ensure_one()
        if self.faizy_whatsapp_provider == "meta":
            return bool(self.faizy_whatsapp_meta_token and self.faizy_whatsapp_meta_phone_id)
        if self.faizy_whatsapp_provider == "twilio":
            return bool(
                self.faizy_whatsapp_twilio_sid
                and self.faizy_whatsapp_twilio_token
                and self.faizy_whatsapp_twilio_from
            )
        return False

    # ── Dispatch ─────────────────────────────────────────────────────────

    def _send_whatsapp(self, message):
        """Send one faizy.whatsapp.message. Raises on failure; the caller
        (faizy.whatsapp.message.action_send) records the error on the row."""
        self.ensure_one()
        if self.faizy_whatsapp_provider == "meta":
            return self._send_whatsapp_meta(message)
        if self.faizy_whatsapp_provider == "twilio":
            return self._send_whatsapp_twilio(message)
        raise UserError(self.env._("No WhatsApp provider configured."))

    def _send_whatsapp_meta(self, message):
        self.ensure_one()
        digits = "".join(ch for ch in message.phone if ch.isdigit())
        url = (
            f"https://graph.facebook.com/{META_API_VERSION}/"
            f"{self.faizy_whatsapp_meta_phone_id}/messages"
        )
        headers = {
            "Authorization": f"Bearer {self.faizy_whatsapp_meta_token}",
            "Content-Type": "application/json",
        }
        if message.template_name:
            # One body variable carrying the whole rendered text — see the
            # module docstring on why the template is assumed that shape.
            payload = {
                "messaging_product": "whatsapp",
                "to": digits,
                "type": "template",
                "template": {
                    "name": message.template_name,
                    "language": {"code": META_LANG_CODE.get(message.lang, "en_US")},
                    "components": [
                        {"type": "body", "parameters": [{"type": "text", "text": message.body}]}
                    ],
                },
            }
        else:
            # Free text. Meta accepts this only inside a 24h customer-initiated
            # session; outside it this call fails loudly with Meta's own error
            # (e.g. #131047), which is correct — a visible failed row beats a
            # silent drop.
            payload = {
                "messaging_product": "whatsapp",
                "to": digits,
                "type": "text",
                "text": {"body": message.body},
            }
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        data = self._parse_json(response)
        if response.status_code >= 400:
            error = (data.get("error") or {}).get("message") or response.text
            raise UserError(self.env._("Meta Cloud API: %(error)s", error=error))
        message_id = (data.get("messages") or [{}])[0].get("id")
        return {"message_id": message_id}

    def _send_whatsapp_twilio(self, message):
        self.ensure_one()
        digits = "".join(ch for ch in message.phone if ch.isdigit())
        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{self.faizy_whatsapp_twilio_sid}/Messages.json"
        )
        # Twilio's WhatsApp Content Templates are addressed by a ContentSid,
        # not the human template_name faizy.whatsapp.message carries — those
        # only exist once a template is actually built in the Twilio Console.
        # Until then this always sends free text, which Twilio (like Meta)
        # only delivers inside a customer-initiated session; business-initiated
        # sends on Twilio need that Content Template work as a follow-up.
        body = {
            "From": f"whatsapp:{self.faizy_whatsapp_twilio_from}",
            "To": f"whatsapp:+{digits}",
            "Body": message.body,
        }
        response = requests.post(
            url,
            data=body,
            auth=(self.faizy_whatsapp_twilio_sid, self.faizy_whatsapp_twilio_token),
            timeout=15,
        )
        data = self._parse_json(response)
        if response.status_code >= 300:
            error = data.get("message") or response.text
            raise UserError(self.env._("Twilio: %(error)s", error=error))
        return {"message_id": data.get("sid")}

    @api.model
    def _parse_json(self, response):
        try:
            return response.json()
        except ValueError:
            return {}
