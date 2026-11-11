"""The kiosk: a public door that reads the shelf and writes one request;
a person confirms, and only then the shop's records move."""
import json

from odoo.exceptions import UserError
from odoo.tests import HttpCase, tagged

from odoo.addons.mumtaz_jewellery_crm.tests.test_tray import TrayCase


@tagged('post_install', '-at_install')
class TestKioskRequest(TrayCase):

    def setUp(self):
        super().setUp()
        self.Req = self.env['jewellery.kiosk.request']
        self.serial = self.lots[0].name

    def test_a_request_is_not_a_reservation(self):
        out = self.Req.create_public('viewing', self.serial, 'Hind Walk-in', '+971 50 000 9001', preferred_time='Thursday')
        self.assertTrue(out['reference'].startswith('KSK/'))
        self.assertIn('Nothing is reserved', out['message'])
        rec = self.Req.search([('name', '=', out['reference'])])
        self.assertEqual(rec.state, 'requested')
        self.assertFalse(rec.partner_id)
        self.assertFalse(rec.order_id)
        self.assertTrue(self.env['jewellery.tray']._lot_available(self.lots[0]))
        self.assertGreater(rec.price_quoted, 0)

    def test_validation_and_the_daily_cap(self):
        with self.assertRaises(UserError):
            self.Req.create_public('viewing', self.serial, 'H', '123')
        with self.assertRaises(UserError):
            self.Req.create_public('delivery', self.serial, 'Hind', '+971500009001', address='x', slot='morning')
        with self.assertRaises(UserError):
            self.Req.create_public('viewing', 'NO-SUCH-SERIAL', 'Hind', '+971500009001')
        self.env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.kiosk_daily_cap', '2')
        self.Req.create_public('viewing', self.serial, 'Hind', '+971500009001')
        self.Req.create_public('viewing', self.serial, 'Hind', '+971500009001')
        with self.assertRaises(UserError):
            self.Req.create_public('viewing', self.serial, 'Hind', '+971500009001')

    def test_confirm_creates_client_opportunity_and_priced_draft_without_moving_stock(self):
        out = self.Req.create_public('delivery', self.serial, 'Sumaya Online', '+971500009002',
                                     address='Villa 12, Street 4, Jumeirah 1, Dubai', slot='afternoon', lang='ar', channel='web')
        rec = self.Req.search([('name', '=', out['reference'])]).with_user(self.staff)
        self.assertTrue(rec.delivery_date)
        rec.action_confirm()
        self.assertEqual(rec.state, 'confirmed')
        self.assertEqual(rec.partner_id.phone, '+971500009002')
        self.assertEqual(rec.partner_id.jewellery_tier, 'standard')
        self.assertEqual(rec.lead_id.type, 'opportunity')
        self.assertEqual(rec.order_id.state, 'draft')
        line = rec.order_id.order_line
        self.assertEqual(line.jewellery_lot_id, self.lots[0])
        self.assertTrue(line.jewellery_rate_per_gram)
        self.assertEqual(self.lots[0].product_qty, 1.0)      # still on the shelf
        self.assertTrue(rec.lead_id.activity_ids)              # the delivery to-do
        # a second request from the same phone finds the same client
        out2 = self.Req.create_public('viewing', self.lots[1].name, 'Sumaya Online', '+971500009002')
        rec2 = self.Req.search([('name', '=', out2['reference'])]).with_user(self.staff)
        rec2.action_confirm()
        self.assertEqual(rec2.partner_id, rec.partner_id)

    def test_decline_and_sold_piece(self):
        out = self.Req.create_public('viewing', self.serial, 'Hind', '+971500009003')
        rec = self.Req.search([('name', '=', out['reference'])]).with_user(self.staff)
        rec.action_decline('Piece sold this morning')
        self.assertEqual(rec.state, 'declined')
        with self.assertRaises(UserError):
            rec.action_confirm()

    def test_requests_join_the_decision_queue(self):
        self.Req.create_public('delivery', self.serial, 'Hind', '+971500009004', address='Villa 1, Street 2, Dubai', slot='morning')
        queue = self.env['jewellery.ai.agent'].with_user(self.staff).decisions_queue(safe=True)
        req = [q for q in queue if q['kind'] == 'request']
        self.assertTrue(req)
        self.assertNotIn('Hind', req[0]['detail'])


@tagged('post_install', '-at_install')
class TestKioskPublicHttp(HttpCase, TrayCase):

    def get(self, path, status=200):
        resp = self.url_open('/jawhar/public/kiosk' + path)
        self.assertEqual(resp.status_code, status, resp.text[:300])
        return resp.json()

    def test_shelf_and_rate_are_public_and_carry_no_ids(self):
        rate = self.get('/rate')['data']['rate']
        self.assertEqual(rate['rate_per_gram'], 245.80)
        out = self.get('/pieces?karat=22&limit=3')['data']
        self.assertTrue(out['items'])
        for p in out['items']:
            self.assertNotIn('id', p)
            self.assertGreater(p['price_incl_vat'], 0)
        one = self.get('/pieces/%s' % out['items'][0]['serial'])['data']
        self.assertEqual(one['rate_per_gram'], 245.80)
        self.get('/pieces/NOPE', status=404)
        self.assertEqual(self.get('/pieces?q=bangle&max_price=1')['data']['total'], 0)

    def test_request_through_the_door(self):
        serial = self.lots[2].name
        resp = self.url_open('/jawhar/public/kiosk/request', data=json.dumps({
            'kind': 'viewing', 'serial': serial, 'name': 'Hind Walk-in', 'phone': '+971500009005', 'preferred_time': 'Thursday'}),
            headers={'Content-Type': 'application/json'})
        self.assertEqual(resp.status_code, 201, resp.text[:300])
        data = resp.json()['data']
        self.assertTrue(data['reference'].startswith('KSK/'))
        self.assertNotIn('id', data)
        bad = self.url_open('/jawhar/public/kiosk/request', data=json.dumps({'kind': 'viewing', 'serial': serial, 'name': 'H', 'phone': '1'}),
                            headers={'Content-Type': 'application/json'})
        self.assertEqual(bad.status_code, 400)
