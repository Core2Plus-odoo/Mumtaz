"""AML and KYC: the threshold is finance's to confirm, the counter compares
cash with it, identity and screening decide at the crossing, and every
crossing is written down."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.mumtaz_jewellery_api.tests.test_api import TestJawharApiCounter
from odoo.addons.mumtaz_jewellery_sale.tests.test_counter import TestCounter


def _cash_journal(env, company):
    """A test database has no chart of accounts, hence no cash journal;
    the gate only ever looks at cash, so make one."""
    journal = env['account.journal'].search([('type', '=', 'cash'), ('company_id', '=', company.id)], limit=1)
    if not journal:
        journal = env['account.journal'].create({'name': 'TEST Cash', 'type': 'cash', 'code': 'TCSH', 'company_id': company.id})
    return journal


class AmlCase(TestCounter):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        field = 'group_ids' if 'group_ids' in cls.maker._fields else 'groups_id'
        g_acc = env.ref('account.group_account_invoice')
        cls.finance = cls.maker
        cls.finance.write({field: [(4, g_acc.id)]})
        cls.cash = _cash_journal(env, cls.company)
        cls.bank = env['account.journal'].search([('type', '=', 'bank'), ('company_id', '=', cls.company.id)], limit=1)
        cls.Event = env['jewellery.aml.event']
        for key in ('aml_cash_threshold', 'aml_cash_window_days', 'aml_confirmed_by', 'aml_confirmed_at'):
            env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.' + key, '')
        cls.today = fields.Date.context_today(env['res.partner'])

    def _order(self, lot, partner=None, user=None):
        order = self.env['sale.order'].with_user(user or self.maker).create({
            'partner_id': (partner or self.client_a).id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1, 'jewellery_lot_id': lot.id})],
        })
        order.order_line.action_price_from_rate()
        return order

    def _total(self, seq=90):
        return self._order(self._piece(seq)).amount_total


@tagged('post_install', '-at_install')
class TestAmlConfig(AmlCase):

    def test_no_threshold_until_finance_confirms_and_a_card_asks_for_it(self):
        self._approve_rate(245.80)
        cfg = self.Event.with_user(self.staff).config()
        self.assertFalse(cfg['configured'])
        self.assertFalse(cfg['can_configure'])
        self.env['jewellery.owner.card'].refresh()
        card = self.env['jewellery.owner.card'].sudo().search([('kind', '=', 'aml'), ('state', '=', 'open')])
        self.assertTrue(any('Confirm the AML cash threshold' in c.title for c in card))
        # nothing is checked: a cash sale of any size goes through
        order = self._order(self._piece(1))
        out = order.with_user(self.maker).action_counter_commit(journal=self.cash)
        self.assertEqual(out['order'].state, 'sale')
        self.assertFalse(self.Event.sudo().search([('kind', '=', 'threshold_crossed')]))

    def test_only_a_finance_manager_sets_it_and_it_is_dated_and_signed(self):
        with self.assertRaises(AccessError):
            self.Event.with_user(self.staff).set_threshold(10000)
        with self.assertRaises(AccessError):
            self.Event.with_user(self.checker).set_threshold(10000)   # manager, not accounting
        with self.assertRaises(UserError):
            self.Event.with_user(self.finance).set_threshold(-1)
        cfg = self.Event.with_user(self.finance).set_threshold(10000, window_days=365, note='Confirmed for the demo tenant.')
        self.assertTrue(cfg['configured'])
        self.assertEqual((cfg['threshold'], cfg['window_days'], cfg['confirmed_by']['name']), (10000.0, 365, 'TEST Maker'))
        self.assertTrue(cfg['confirmed_at'])
        ev = self.Event.sudo().search([('kind', '=', 'config')], limit=1)
        self.assertEqual((ev.threshold, ev.window_days, ev.user_id), (10000.0, 365, self.finance))
        self.env['jewellery.owner.card'].refresh()
        self.assertFalse(self.env['jewellery.owner.card'].sudo().search([('kind', '=', 'aml'), ('state', '=', 'open'),
                                                                        ('title', 'ilike', 'Confirm the AML')]))
        self.assertFalse(self.Event.with_user(self.finance).set_threshold(0)['configured'])


@tagged('post_install', '-at_install')
class TestKyc(AmlCase):

    def test_identity_keeps_only_type_last4_and_expiry(self):
        p = self.client_a.with_user(self.staff)
        with self.assertRaises(UserError):
            p.action_verify_identity('emirates_id', '784-1990-1234567-1', self.today + timedelta(days=100))
        with self.assertRaises(UserError):
            p.action_verify_identity('emirates_id', '6712', self.today - timedelta(days=1))
        with self.assertRaises(UserError):
            p.action_verify_identity('drivers', '6712', self.today + timedelta(days=100))
        p.action_verify_identity('emirates_id', '67a1', self.today + timedelta(days=100), note='Seen at the counter.')
        self.assertEqual((p.kyc_status, p.kyc_id_type, p.kyc_id_last4), ('verified', 'emirates_id', '67A1'))
        self.assertEqual(p.kyc_verified_by_id, self.staff)
        self.assertFalse(p.kyc_expired)
        self.assertTrue(any('ending 67A1' in (m.body or '') for m in p.message_ids))
        ev = self.Event.sudo().search([('kind', '=', 'kyc_verified'), ('partner_id', '=', p.id)])
        self.assertEqual(ev.kyc_id_last4, '67A1')
        self.assertNotIn('784', str(p.read(['kyc_id_last4', 'kyc_note'])))

    def test_screening_is_a_manager_decision(self):
        with self.assertRaises(AccessError):
            self.client_a.with_user(self.staff).action_record_screening('clear')
        with self.assertRaises(UserError):
            self.client_a.with_user(self.maker).action_record_screening('maybe')
        self.client_a.with_user(self.maker).action_record_screening('match', risk_band='high', note='Name match on list X.')
        self.assertEqual((self.client_a.aml_screening_status, self.client_a.aml_risk_band), ('match', 'high'))
        self.env['jewellery.owner.card'].refresh()
        self.assertTrue(self.env['jewellery.owner.card'].sudo().search([('kind', '=', 'aml'), ('title', 'ilike', 'screening match'),
                                                                       ('res_id', '=', self.client_a.id)]))

    def test_expiring_documents_make_a_card(self):
        self.client_b.with_user(self.staff).action_verify_identity('passport', 'P001', self.today + timedelta(days=10))
        self.env['jewellery.owner.card'].refresh()
        card = self.env['jewellery.owner.card'].sudo().search([('kind', '=', 'aml'), ('res_id', '=', self.client_b.id)])
        self.assertIn('expires soon', card.title)


@tagged('post_install', '-at_install')
class TestCounterGate(AmlCase):

    def setUp(self):
        super().setUp()
        self._approve_rate(245.80)
        self.total = self._total()
        # threshold a little above one piece: the first cash sale passes, the second crosses
        self.Event.with_user(self.finance).set_threshold(self.total * 1.5, window_days=365, note='test')

    def test_cash_below_the_threshold_passes_and_the_window_accumulates(self):
        o1 = self._order(self._piece(2))
        o1.with_user(self.maker).action_counter_commit(journal=self.cash)
        self.assertAlmostEqual(self.client_a.aml_cash_in_window(365), self.total, 1)
        checks = {c['key']: c for c in self.env['sale.order'].with_user(self.maker)._counter_extra_checks(
            partner=self.client_a, lot=self._piece(3), journal=self.cash, amount=None)}
        aml = checks['aml']
        self.assertFalse(aml['ok'])
        self.assertTrue(aml['detail']['crosses'])
        self.assertEqual(aml['detail']['reason'], 'kyc_required')
        self.assertIn('verified identity', aml['detail']['message'])

    def test_crossing_without_identity_refuses_and_nothing_happened(self):
        self._order(self._piece(4)).with_user(self.maker).action_counter_commit(journal=self.cash)
        o2 = self._order(self._piece(5))
        invoices = self.env['account.move'].search_count([('move_type', '=', 'out_invoice')])
        with self.assertRaises(UserError) as caught:
            o2.with_user(self.maker).action_counter_commit(journal=self.cash)
        self.assertIn('verified identity', str(caught.exception))
        self.assertEqual(o2.state, 'draft')
        self.assertEqual(self.env['account.move'].search_count([('move_type', '=', 'out_invoice')]), invoices)
        # a card or bank payment is not cash: the same sale goes through
        o2.with_user(self.maker).action_counter_commit(journal=self.bank)
        self.assertEqual(o2.state, 'sale')
        self.assertFalse(self.Event.sudo().search([('kind', '=', 'threshold_crossed'), ('order_id', '=', o2.id)]))

    def test_crossing_with_verified_identity_is_allowed_and_written_down(self):
        self._order(self._piece(6)).with_user(self.maker).action_counter_commit(journal=self.cash)
        self.client_a.with_user(self.staff).action_verify_identity('emirates_id', '1234', self.today + timedelta(days=400))
        o2 = self._order(self._piece(7))
        out = o2.with_user(self.maker).action_counter_commit(journal=self.cash)
        self.assertEqual(out['order'].state, 'sale')
        ev = self.Event.sudo().search([('kind', '=', 'threshold_crossed'), ('order_id', '=', o2.id)])
        self.assertEqual(len(ev), 1)
        self.assertAlmostEqual(ev.amount_cash, self.total, 1)
        self.assertAlmostEqual(ev.cash_window_before, self.total, 1)
        self.assertEqual((ev.kyc_status, ev.kyc_id_last4, ev.invoice_id), ('verified', '1234', out['invoice']))
        self.assertEqual(ev.user_id, self.maker)

    def test_a_deposit_counts_only_the_cash_taken_now(self):
        self._order(self._piece(8)).with_user(self.maker).action_counter_commit(journal=self.cash)
        o2 = self._order(self._piece(9))
        small = round(self.total * 0.2, 2)
        out = o2.with_user(self.maker).action_counter_commit(journal=self.cash, amount=small)   # below the line
        self.assertEqual(out['order'].state, 'sale')
        self.assertFalse(self.Event.sudo().search([('kind', '=', 'threshold_crossed'), ('order_id', '=', o2.id)]))

    def test_expired_document_and_screening_match_refuse(self):
        self._order(self._piece(10)).with_user(self.maker).action_counter_commit(journal=self.cash)
        p = self.client_a
        p.with_user(self.staff).action_verify_identity('passport', 'EXP1', self.today + timedelta(days=1))
        p.sudo().write({'kyc_id_expiry': self.today - timedelta(days=1)})
        self.assertTrue(p.kyc_expired)
        with self.assertRaises(UserError) as caught:
            self._order(self._piece(11)).with_user(self.maker).action_counter_commit(journal=self.cash)
        self.assertIn('expired', str(caught.exception))
        p.with_user(self.staff).action_verify_identity('passport', 'NEW1', self.today + timedelta(days=500))
        p.with_user(self.maker).action_record_screening('match', risk_band='high')
        with self.assertRaises(UserError) as caught:
            self._order(self._piece(12)).with_user(self.maker).action_counter_commit(journal=self.cash)
        self.assertIn('compliance decision', str(caught.exception))
        p.with_user(self.maker).action_record_screening('clear', risk_band='low', note='False positive, cleared.')
        out = self._order(self._piece(13)).with_user(self.maker).action_counter_commit(journal=self.cash)
        self.assertEqual(out['order'].state, 'sale')


@tagged('post_install', '-at_install')
class TestJawharApiAml(TestJawharApiCounter):
    """The gate through the door: config, identity, readiness and commit."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        field = 'group_ids' if 'group_ids' in cls.cashier._fields else 'groups_id'
        cls.cashier.write({field: [(4, cls.env.ref('account.group_account_invoice').id)]})
        cls.cash = _cash_journal(cls.env, cls.env.company)
        for key in ('aml_cash_threshold', 'aml_cash_window_days', 'aml_confirmed_by', 'aml_confirmed_at'):
            cls.env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.' + key, '')

    def test_config_identity_readiness_and_commit(self):
        self.sign_in('api_seller')
        self.assertFalse(self.api('/aml/config')['data']['configured'])
        self.assertEqual(self.api('/aml/config', 'POST', {'threshold': 100}, status=403)['error']['code'], 'forbidden')
        self.api('/auth/logout', 'POST')
        self.sign_in('api_cashier')
        price = self.api('/counter/piece?q=%s' % self.lot_a.name)['data']['breakdown']['total']
        cfg = self.api('/aml/config', 'POST', {'threshold': price * 0.5, 'window_days': 365, 'note': 'Confirmed.'})['data']
        self.assertTrue(cfg['configured'])
        self.assertEqual(cfg['confirmed_by']['name'], 'TEST Cashier')
        # readiness names the gate before the commit
        out = self.api('/counter/readiness?piece_id=%d&client_id=%d&journal_id=%d' % (self.lot_a.id, self.client.id, self.cash.id))['data']
        aml = next(c for c in out['checks'] if c['key'] == 'aml')
        self.assertFalse(aml['ok'])
        self.assertEqual(aml['detail']['reason'], 'kyc_required')
        self.assertFalse(out['ready'])
        err = self.api('/counter/commit', 'POST', {'client_id': self.client.id, 'piece_id': self.lot_a.id, 'journal_id': self.cash.id}, status=400)
        self.assertIn('verified identity', err['error']['message'])
        # identity: the number is never stored, only the last four
        bad = self.api('/clients/%d/kyc/verify' % self.client.id, 'POST', {'id_type': 'emirates_id', 'last4': '784199012345671', 'expiry': '2030-01-01'}, status=400)
        self.assertEqual(bad['error']['code'], 'invalid')
        expiry = (fields.Date.today() + timedelta(days=200)).isoformat()
        kyc = self.api('/clients/%d/kyc/verify' % self.client.id, 'POST', {'id_type': 'emirates_id', 'last4': '5671', 'expiry': expiry, 'note': 'Seen.'})['data']
        self.assertEqual((kyc['status'], kyc['id_last4'], kyc['verified_by']['name']), ('verified', '5671', 'TEST Cashier'))
        out = self.api('/counter/commit', 'POST', {'client_id': self.client.id, 'piece_id': self.lot_a.id, 'journal_id': self.cash.id}, status=201)['data']
        self.assertEqual(out['order']['state'], 'sale')
        events = self.api('/aml/events?kind=threshold_crossed')['data']['items']
        self.assertEqual(events[0]['client']['id'], self.client.id)
        self.assertEqual(events[0]['kyc']['id_last4'], '5671')
        self.assertAlmostEqual(events[0]['amount_cash'], out['invoice']['amount_total'], 1)
        self.assertEqual(self.api('/clients/%d/kyc' % self.client.id)['data']['status'], 'verified')
        scr = self.api('/clients/%d/kyc/screening' % self.client.id, 'POST', {'status': 'clear', 'risk_band': 'low'})['data']
        self.assertEqual((scr['screening'], scr['risk_band']), ('clear', 'low'))
        self.assertEqual(self.api('/aml/expiring?days=365')['data']['items'][0]['client']['id'], self.client.id)
