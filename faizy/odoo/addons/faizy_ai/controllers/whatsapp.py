import hashlib
import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class FaizyAIWhatsapp(http.Controller):
    """Inbound WhatsApp (Meta Cloud API) webhook.

    Set two system parameters before pointing Meta at this URL:
      faizy_ai.wa_verify_token  (any secret string, also entered in the Meta console)
      faizy_ai.wa_app_secret    (the Meta app secret, used to check the signature)
    Webhook URL:  https://<your domain>/faizy_ai/whatsapp/webhook
    """

    @http.route('/faizy_ai/whatsapp/webhook', type='http', auth='public',
                methods=['GET'], csrf=False)
    def verify(self, **params):
        icp = request.env['ir.config_parameter'].sudo()
        token = icp.get_param('faizy_ai.wa_verify_token')
        given = params.get('hub.verify_token') or ''
        if (params.get('hub.mode') == 'subscribe' and token
                and hmac.compare_digest(token, given)):
            return request.make_response(params.get('hub.challenge', ''))
        return request.make_response('Forbidden', status=403)

    @http.route('/faizy_ai/whatsapp/webhook', type='http', auth='public',
                methods=['POST'], csrf=False)
    def receive(self, **kwargs):
        icp = request.env['ir.config_parameter'].sudo()
        secret = icp.get_param('faizy_ai.wa_app_secret')
        raw = request.httprequest.get_data()
        if not secret:
            return request.make_response('Not configured', status=403)
        sent = request.httprequest.headers.get('X-Hub-Signature-256', '')
        expected = 'sha256=' + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sent, expected):
            _logger.warning('faizy_ai: webhook signature mismatch')
            return request.make_response('Bad signature', status=403)
        try:
            payload = json.loads(raw.decode() or '{}')
        except ValueError:
            return request.make_response('Bad payload', status=400)
        request.env['faizy.ai.inbound'].sudo().process_whatsapp_payload(payload)
        return request.make_response('OK')
