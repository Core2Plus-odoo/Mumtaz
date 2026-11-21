"""The website's one write, tested at the boundary: what goes in, what is
written, what comes back, what is refused."""
import json

from odoo.exceptions import UserError
from odoo.tests import HttpCase, tagged

URL = '/jawhar/public/site/demo-request'
GOOD = {'company': 'Dar Al Noor Jewellers', 'name': 'Hind Al Mansoori', 'email': 'hind@example.test',
        'phone': '+971 50 000 9100', 'country': 'ae', 'stores': '2-5', 'consent': True,
        'message': 'Three boutiques in Dubai, one in Sharjah.', 'lang': 'en', 'page': '/'}


@tagged('post_install', '-at_install')
class TestDemoRequest(HttpCase):

    def _post(self, payload, raw=None):
        data = raw if raw is not None else json.dumps(payload)
        return self.url_open(URL, data=data, headers={'Content-Type': 'application/json'}, timeout=30)

    def test_a_request_becomes_a_tagged_lead_with_consent_and_no_ids_leave(self):
        r = self._post(GOOD)
        self.assertEqual(r.status_code, 200, r.text)
        out = r.json()
        self.assertTrue(out['ok'])
        self.assertTrue(out['data']['reference'].startswith('DEMO/'))
        self.assertEqual(set(out['data']), {'reference'})
        rec = self.env['jewellery.demo.request'].search([('name', '=', out['data']['reference'])])
        self.assertEqual(rec.email, 'hind@example.test')
        self.assertEqual(rec.phone, '+971500009100')
        self.assertTrue(rec.consent_at)
        self.assertIn('agree', rec.consent_text)
        lead = rec.lead_id
        self.assertEqual(lead.type, 'lead')
        self.assertEqual(lead.email_from, 'hind@example.test')
        self.assertEqual(lead.partner_name, 'Dar Al Noor Jewellers')
        self.assertIn(self.env.ref('mumtaz_jewellery_website.tag_jawhar_demo'), lead.tag_ids)
        self.assertIn('2 to 5 stores', lead.description)

    def test_validation_consent_and_bad_json(self):
        r = self._post(dict(GOOD, consent=False))
        self.assertEqual(r.status_code, 400)
        self.assertIn('agree', r.json()['error']['message'])
        r = self._post(dict(GOOD, email='not-an-address'))
        self.assertEqual(r.status_code, 400)
        r = self._post(dict(GOOD, company='X'))
        self.assertEqual(r.status_code, 400)
        r = self._post(None, raw='[1,2')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error']['code'], 'bad_json')
        self.assertFalse(self.env['jewellery.demo.request'].search([('email', '=', 'not-an-address')]))

    def test_honeypot_is_thanked_and_ignored(self):
        before = self.env['jewellery.demo.request'].search_count([])
        r = self._post(dict(GOOD, email='bot@example.test', website='http://spam.example'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.env['jewellery.demo.request'].search_count([]), before)
        self.assertFalse(self.env['crm.lead'].search([('email_from', '=', 'bot@example.test')]))

    def test_daily_cap_per_contact(self):
        self.env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.demo_request_daily_cap', '2')
        payload = dict(GOOD, email='cap@example.test')
        self.assertEqual(self._post(payload).status_code, 200)
        self.assertEqual(self._post(payload).status_code, 200)
        r = self._post(payload)
        self.assertEqual(r.status_code, 429)
        # a different address is not affected
        self.assertEqual(self._post(dict(GOOD, email='other@example.test')).status_code, 200)

    def test_orm_validation_matches(self):
        Req = self.env['jewellery.demo.request']
        with self.assertRaises(UserError):
            Req.create_public('Dar', 'Hind', 'hind2@example.test', False)
        with self.assertRaises(UserError):
            Req.create_public('Dar', 'Hind', 'hind2@example.test', True, phone='123')
        out = Req.create_public('Dar', 'Hind', 'HIND3@Example.test', True, country='zz', stores='9', lang='ar-SA')
        rec = Req.search([('name', '=', out['reference'])])
        self.assertEqual((rec.email, rec.country, rec.stores, rec.lang), ('hind3@example.test', 'other', '1', 'ar'))
