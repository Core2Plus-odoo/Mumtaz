import hashlib
import hmac
import json

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestWebhook(HttpCase):

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('faizy_ai.wa_verify_token', 'verify-me')
        icp.set_param('faizy_ai.wa_app_secret', 's3cret')
        self.env['res.partner'].create({'name': 'Hamza', 'phone': '+971 50 123 4567'})
        self.payload = json.dumps({'entry': [{'changes': [{'value': {'messages': [{
            'id': 'wamid.web1', 'from': '971501234567', 'type': 'text',
            'text': {'body': 'Salam'}}]}}]}]}).encode()

    def _sig(self, body, secret='s3cret'):
        return 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def test_verify_handshake(self):
        ok = self.url_open('/faizy_ai/whatsapp/webhook?hub.mode=subscribe'
                           '&hub.verify_token=verify-me&hub.challenge=abc123')
        self.assertEqual((ok.status_code, ok.text), (200, 'abc123'))
        bad = self.url_open('/faizy_ai/whatsapp/webhook?hub.mode=subscribe'
                            '&hub.verify_token=nope&hub.challenge=abc123')
        self.assertEqual(bad.status_code, 403)

    def test_post_requires_valid_signature(self):
        url = '/faizy_ai/whatsapp/webhook'
        bad = self.url_open(url, data=self.payload,
                            headers={'X-Hub-Signature-256': self._sig(self.payload, 'wrong')})
        self.assertEqual(bad.status_code, 403)
        good = self.url_open(url, data=self.payload,
                             headers={'X-Hub-Signature-256': self._sig(self.payload),
                                      'Content-Type': 'application/json'})
        self.assertEqual(good.status_code, 200)
        rec = self.env['faizy.ai.inbound'].sudo().search([('wa_id', '=', 'wamid.web1')])
        self.assertEqual(len(rec), 1)
        self.assertTrue(rec.partner_id)
