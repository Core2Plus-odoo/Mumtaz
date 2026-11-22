"""The client app: a code a person gives her, a token that reads only her
own things, consent she may withdraw, and a door that says the same to a
phone it does not know."""
import json
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import HttpCase, tagged

from odoo.addons.mumtaz_jewellery_api.tests.test_api import TestJawharApiSale
from odoo.addons.mumtaz_jewellery_crm.tests.test_tray import TrayCase


@tagged('post_install', '-at_install')
class TestClientSession(TrayCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client.write({'phone': '+971 50 123 4567'})
        cls.Session = cls.env['jewellery.client.session']
        cls.env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.client_code_echo', '0')

    def _code(self):
        self.Session.request_code('+971 50 123 4567')
        sess = self.Session.sudo().search([('phone', '=', '+971501234567')], order='id desc', limit=1)
        return sess, sess.code

    def test_a_code_is_issued_for_a_known_phone_and_the_same_answer_for_an_unknown_one(self):
        known = self.Session.request_code('+971 50 123 4567')
        unknown = self.Session.request_code('+971 50 000 0000')
        self.assertEqual(known['message'], unknown['message'])
        self.assertNotIn('code', known)                      # never in the answer unless the demo echo is on
        sess = self.Session.sudo().search([('phone', '=', '+971501234567')])
        self.assertEqual(len(sess), 1)
        self.assertEqual(len(sess.code), 6)
        self.assertEqual(sess.state, 'code')
        self.assertFalse(self.Session.sudo().search([('phone', '=', '+971500000000')]))
        # staff may read it to her
        self.assertEqual(self.Session.pending_codes(self.client)[0]['code'], sess.code)
        with self.assertRaises(UserError):
            self.Session.request_code('123')

    def test_three_codes_an_hour_then_silence(self):
        for _ in range(3):
            self.Session.request_code('+971 50 123 4567')
        self.Session.request_code('+971 50 123 4567')
        self.assertEqual(self.Session.sudo().search_count([('phone', '=', '+971501234567')]), 3)

    def test_verify_gives_a_token_five_misses_close_the_code(self):
        sess, code = self._code()
        for _ in range(4):
            self.assertFalse(self.Session.verify('+971 50 123 4567', '000000')['ok'])
        self.assertEqual(sess.attempts, 4)                        # a miss is a result, so the count survives
        out = self.Session.verify('+971 50 123 4567', code)
        self.assertTrue(out['token'])
        self.assertFalse(sess.code)
        self.assertEqual(sess.state, 'open')
        self.assertEqual(self.Session.by_token(out['token']), sess)
        self.assertFalse(self.Session.by_token('nope'))
        self.assertFalse(self.Session.verify('+971 50 123 4567', code)['ok'])        # used once
        sess2, code2 = self._code()
        for _ in range(5):
            self.assertFalse(self.Session.verify('+971 50 123 4567', '000000')['ok'])
        self.assertFalse(sess2.code)
        self.assertFalse(self.Session.verify('+971 50 123 4567', code2)['ok'])      # five misses closed it
        sess.action_revoke()
        self.assertFalse(self.Session.by_token(out['token']))

    def test_expired_codes_and_tokens_are_cleared(self):
        sess, code = self._code()
        sess.sudo().write({'code_expires': fields.Datetime.now() - timedelta(minutes=1)})
        self.assertFalse(self.Session.verify('+971 50 123 4567', code)['ok'])
        self.Session._cron_expire()
        self.assertFalse(sess.code)

    def test_she_reads_only_her_own_things(self):
        sess, code = self._code()
        self.Session.verify('+971 50 123 4567', code)
        # a sale to her, a tray for her, a request from her phone
        order = self.env['sale.order'].with_user(self.maker).create({
            'partner_id': self.client.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1, 'jewellery_lot_id': self.lots[0].id})]})
        order.order_line.action_price_from_rate()
        order.action_confirm()
        other = self.env['sale.order'].with_user(self.maker).create({
            'partner_id': self.private.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1, 'jewellery_lot_id': self.lots[1].id})]})
        other.order_line.action_price_from_rate()
        other.action_confirm()
        tray = self._tray()
        tray.action_build(limit=2)
        tray.action_share()
        self.env['jewellery.kiosk.request'].create_public('viewing', self.lots[3].name, 'Tray Client', '+971 50 123 4567')
        owned = sess.owned_pieces()
        self.assertEqual([p['serial'] for p in owned], [self.lots[0].name])
        self.assertGreater(owned[0]['metal_value_today'], 0)
        self.assertEqual(owned[0]['order'], order.name)
        self.assertEqual([t['name'] for t in sess.trays()], [tray.name])
        self.assertEqual(len(sess.requests()), 1)
        me = sess.me()
        self.assertEqual(me['first_name'], 'TEST')
        self.assertEqual(me['consent']['status'], 'unknown')


@tagged('post_install', '-at_install')
class TestClientDoor(HttpCase):

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.client_code_echo', '1')   # demo echo, so the test can sign in
        self.partner = self.env['res.partner'].create({'name': 'TEST Door Client', 'phone': '+971 55 100 2000', 'jewellery_tier': 'standard'})

    def post(self, path, body=None, token=None, status=200):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['X-Client-Token'] = token
        resp = self.url_open('/jawhar/client' + path, data=json.dumps(body or {}), headers=headers)
        self.assertEqual(resp.status_code, status, resp.text[:300])
        return resp.json()

    def get(self, path, token=None, status=200):
        resp = self.url_open('/jawhar/client' + path, headers={'X-Client-Token': token} if token else {})
        self.assertEqual(resp.status_code, status, resp.text[:300])
        return resp.json()

    def test_code_verify_home_consent_signout(self):
        self.assertEqual(self.get('/me', status=401)['error']['code'], 'unauthenticated')
        out = self.post('/code', {'phone': '+971 55 100 2000', 'lang': 'ar'})['data']
        self.assertEqual(len(out['code']), 6)
        self.assertEqual(self.post('/verify', {'phone': '+971 55 100 2000', 'code': '000000'}, status=400)['error']['code'], 'invalid')
        v = self.post('/verify', {'phone': '+971 55 100 2000', 'code': out['code']})['data']
        token = v['token']
        self.assertEqual(v['me']['first_name'], 'TEST')
        home = self.get('/home', token)['data']
        self.assertEqual(home['owned'], [])
        self.assertIn('rate', home)
        self.assertEqual(home['me']['consent']['status'], 'unknown')
        me = self.post('/consent', {'status': 'given'}, token)['data']
        self.assertEqual(me['consent']['status'], 'given')
        self.assertEqual(self.partner.consent_source, 'client_message')
        me = self.post('/consent', {'status': 'withdrawn'}, token)['data']
        self.assertEqual(me['consent']['status'], 'withdrawn')
        self.assertTrue(self.partner.no_marketing)
        self.get('/trays/999999', token, status=404)
        self.post('/signout', {}, token)
        self.get('/me', token, status=401)

    def test_the_echo_is_off_by_default(self):
        self.env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.client_code_echo', '0')
        out = self.post('/code', {'phone': '+971 55 100 2000'})['data']
        self.assertNotIn('code', out)


@tagged('post_install', '-at_install')
class TestJawharApiClientStaff(TestJawharApiSale):

    def test_staff_see_the_live_code_on_her_record(self):
        self.client.write({'phone': '+971 55 300 4000'})
        self.env['jewellery.client.session'].request_code('+971 55 300 4000')
        self.sign_in('api_seller')
        out = self.api('/clients/%d/app' % self.client.id)['data']
        self.assertEqual(len(out['codes']), 1)
        self.assertEqual(len(out['codes'][0]['code']), 6)
        self.assertEqual(out['open_sessions'], 0)
