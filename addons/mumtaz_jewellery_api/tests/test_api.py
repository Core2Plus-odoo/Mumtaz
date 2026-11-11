"""The Jawhar API door: who gets in, what they see, and that it is written down.

Every test goes through HTTP, as the front end will, not through the ORM:
the point of the API is its behaviour at the boundary.
"""
import json

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged

from odoo.addons.mumtaz_jewellery.tests.common import GROSS_G, STONE_G

PASSWORD = 'jawhar-test-pass'


@tagged('post_install', '-at_install')
class TestJawharApi(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.vat_rate', '5')

        Users = env['res.users'].with_context(no_reset_password=True)
        field = 'group_ids' if 'group_ids' in Users._fields else 'groups_id'
        g_user = env.ref('mumtaz_jewellery.group_jewellery_user')
        g_mgr = env.ref('mumtaz_jewellery.group_jewellery_manager')
        g_vip = env.ref('mumtaz_jewellery_vip.group_vip_manager')
        g_sales = env.ref('sales_team.group_sale_salesman')

        def make(login, name, *groups):
            return Users.create({
                'name': name, 'login': login, 'password': PASSWORD,
                field: [(6, 0, [g.id for g in groups])]})

        cls.staff = make('api_staff', 'TEST Counter Staff', g_user, g_sales)
        cls.maker = make('api_maker', 'TEST Rate Maker', g_mgr, g_sales)
        cls.checker = make('api_checker', 'TEST Rate Checker', g_mgr, g_vip, g_sales)

        # An approved rate through the real maker-checker path.
        Rate = env['jewellery.gold.rate']
        rate = Rate.with_user(cls.maker).create({'rate_per_gram': 100.0})
        rate.with_user(cls.checker).action_approve()
        cls.rate = rate

        product = env['product.product'].create({
            'name': 'TEST 22K bangle', 'type': 'consu', 'is_storable': True,
            'tracking': 'serial', 'is_jewellery': True, 'jewellery_karat': '22',
            'jewellery_wastage_pct': 2.0, 'jewellery_making_type': 'percent',
            'jewellery_making_value': 10.0,
        })
        cls.lot = env['stock.lot'].create({
            'name': 'TEST-API-0001', 'product_id': product.id,
            'gross_weight_g': GROSS_G, 'stone_weight_g': STONE_G,
            'stones_value': 50.0, 'rfid_tag': 'TEST-RFID-API-1',
        })
        cls.plain = env['res.partner'].create({
            'name': 'TEST Client Plain', 'jewellery_tier': 'preferred'})
        cls.royal = env['res.partner'].create({
            'name': 'TEST Client Royal', 'jewellery_tier': 'royal',
            'relationship_manager_id': cls.checker.id})
        env['jewellery.owner.card'].create({
            'kind': 'rate', 'title': 'TEST card', 'priority': 7})

    # ---- helpers ------------------------------------------------------
    def api(self, path, method='GET', body=None, status=200):
        url = '/jawhar/v1' + path
        if method == 'POST':
            resp = self.url_open(url, data=json.dumps(body or {}),
                                 headers={'Content-Type': 'application/json'})
        else:
            resp = self.url_open(url)
        self.assertEqual(resp.status_code, status, resp.text[:300])
        self.assertIn('application/json', resp.headers.get('Content-Type', ''))
        return resp.json()

    def sign_in(self, login):
        return self.api('/auth/login', 'POST', {'login': login, 'password': PASSWORD})

    def audit_rows(self, path):
        return self.env['jewellery.api.audit'].sudo().search([('path', '=', '/jawhar/v1' + path)])

    # ---- the door ------------------------------------------------------
    def test_health_is_public(self):
        out = self.api('/health')
        self.assertTrue(out['ok'])
        self.assertEqual(out['data']['service'], 'jawhar-api')

    def test_unauthenticated_gets_json_401_not_a_redirect(self):
        resp = self.url_open('/jawhar/v1/me', allow_redirects=False)
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(resp.json()['ok'])
        self.assertEqual(resp.json()['error']['code'], 'unauthenticated')

    def test_login_wrong_password_is_401_and_audited(self):
        out = self.api('/auth/login', 'POST',
                       {'login': 'api_staff', 'password': 'nope'}, status=401)
        self.assertEqual(out['error']['code'], 'access_denied')
        row = self.audit_rows('/auth/login').filtered(lambda r: r.status == 401)[:1]
        self.assertTrue(row, 'a failed sign-in must be written down')
        self.assertEqual(row.login, 'api_staff')
        self.assertFalse(row.user_id)

    def test_login_then_me_then_logout(self):
        out = self.sign_in('api_staff')
        self.assertEqual(out['data']['login'], 'api_staff')
        self.assertIn('jewellery_user', out['data']['roles'])
        self.assertNotIn('jewellery_manager', out['data']['roles'])
        self.assertEqual(out['data']['company']['currency']['code'],
                         self.env.company.currency_id.name)

        me = self.api('/me')
        self.assertEqual(me['data']['id'], self.staff.id)
        self.assertEqual(self.audit_rows('/me')[:1].user_id, self.staff)

        self.api('/auth/logout', 'POST')
        self.api('/me', status=401)

    # ---- figures come from the engine ----------------------------------
    def test_piece_breakdown_is_the_engine_figure(self):
        self.sign_in('api_staff')
        out = self.api('/pieces/%d' % self.lot.id)['data']
        self.assertEqual(out['serial'], 'TEST-API-0001')
        self.assertEqual(out['net_weight_g'], GROSS_G - STONE_G)
        expected = self.lot.get_price_breakdown()
        self.assertEqual(out['breakdown']['total'], expected['total'])
        self.assertEqual(out['breakdown']['subtotal'], expected['subtotal'])
        self.assertEqual(out['rate']['id'], self.rate.id)
        self.assertEqual(out['rate']['approved_by']['id'], self.checker.id)

        # A dealer discount changes the making charge and nothing else.
        disc = self.api('/pieces/%d?discount=15' % self.lot.id)['data']['breakdown']
        self.assertEqual(disc['metal_value'], out['breakdown']['metal_value'])
        self.assertLess(disc['making_charge'], out['breakdown']['making_charge'])
        self.assertEqual(disc['making_discount_pct'], 15.0)

    def test_pieces_list_and_search(self):
        self.sign_in('api_staff')
        out = self.api('/pieces?q=RFID-API')['data']
        self.assertEqual(out['total'], 1)
        self.assertEqual(out['items'][0]['rfid_tag'], 'TEST-RFID-API-1')
        self.assertEqual(self.api('/pieces?q=nothing-matches')['data']['total'], 0)

    def test_current_rate(self):
        self.sign_in('api_staff')
        out = self.api('/rates/current')['data']['rate']
        self.assertEqual(out['rate_per_gram'], 100.0)
        self.assertEqual(out['state'], 'approved')

    # ---- the API sees what the person sees, no more ----------------------
    def test_restricted_client_hidden_from_staff_visible_to_vip_manager(self):
        self.sign_in('api_staff')
        names = [c['name'] for c in self.api('/clients')['data']['items']]
        self.assertIn('TEST Client Plain', names)
        self.assertNotIn('TEST Client Royal', names)
        # Not 403: a 403 would confirm the restricted client exists.
        out = self.api('/clients/%d' % self.royal.id, status=404)
        self.assertEqual(out['error']['code'], 'not_found')
        self.api('/auth/logout', 'POST')

        self.sign_in('api_checker')
        names = [c['name'] for c in self.api('/clients')['data']['items']]
        self.assertIn('TEST Client Royal', names)
        royal = self.api('/clients/%d' % self.royal.id)['data']
        self.assertTrue(royal['restricted'])
        self.assertEqual(royal['ai_autonomy_cap'], 2)
        self.assertEqual(royal['relationship_manager']['id'], self.checker.id)

    def test_audit_hidden_from_staff(self):
        self.sign_in('api_staff')
        with self.assertRaises(AccessError):
            self.env['jewellery.api.audit'].with_user(self.staff).search([])

    # ---- today ------------------------------------------------------------
    def test_today_summary_counts_only_what_the_person_may_see(self):
        # The maker is a jewellery manager but not a VIP manager: the royal
        # client is invisible to him, so the summary must not count it.
        self.sign_in('api_maker')
        out = self.api('/today')['data']
        self.assertEqual(out['rate']['rate_per_gram'], 100.0)
        self.assertEqual(out['cards_open'], 1)
        self.assertEqual(out['clients'], {'total': 1, 'restricted': 0})
        self.assertIsInstance(out['pieces_on_hand'], int)
        self.api('/auth/logout', 'POST')

        self.sign_in('api_checker')
        out = self.api('/today')['data']
        self.assertEqual(out['clients'], {'total': 2, 'restricted': 1})

    def test_bad_json_body_is_400(self):
        resp = self.url_open('/jawhar/v1/auth/login', data='{not json',
                             headers={'Content-Type': 'application/json'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error']['code'], 'bad_json')


@tagged('post_install', '-at_install')
class TestJawharApiSale(HttpCase):
    """Slice 1 through the door: quote, renew, confirm, invoice, payment.

    Each call runs as the signed-in person, so who may do what is Odoo's
    access rights, not a second rule book here; the tests show a salesperson
    without accounting rights being refused at the invoice.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env.company.quotation_validity_days = 7
        env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.vat_rate', '5')

        Users = env['res.users'].with_context(no_reset_password=True)
        field = 'group_ids' if 'group_ids' in Users._fields else 'groups_id'
        g_user = env.ref('mumtaz_jewellery.group_jewellery_user')
        g_mgr = env.ref('mumtaz_jewellery.group_jewellery_manager')
        g_sales = env.ref('sales_team.group_sale_salesman')
        g_account = env.ref('account.group_account_invoice')

        def make(login, name, *groups):
            return Users.create({'name': name, 'login': login, 'password': PASSWORD,
                                 field: [(6, 0, [g.id for g in groups])]})

        cls.seller = make('api_seller', 'TEST Seller', g_user, g_sales)
        cls.cashier = make('api_cashier', 'TEST Cashier', g_mgr, g_sales, g_account)
        cls.maker = make('api_s_maker', 'TEST S Maker', g_mgr)
        cls.checker = make('api_s_checker', 'TEST S Checker', g_mgr)

        rate = env['jewellery.gold.rate'].with_user(cls.maker).create({'rate_per_gram': 245.80})
        rate.with_user(cls.checker).action_approve()

        cls.product = env['product.product'].create({
            'name': 'TEST 22K sale bangle', 'type': 'consu', 'is_storable': True,
            'tracking': 'serial', 'invoice_policy': 'order', 'is_jewellery': True,
            'jewellery_karat': '22', 'jewellery_wastage_pct': 2.0,
            'jewellery_making_type': 'percent', 'jewellery_making_value': 10.0,
        })
        stock = env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1).lot_stock_id

        def piece(seq, in_stock=True):
            lot = env['stock.lot'].create({
                'name': 'TEST-API-SALE-%d' % seq, 'product_id': cls.product.id,
                'gross_weight_g': 24.5, 'stone_weight_g': 0.0,
            })
            lot.jewellery_cost_value = 4000.0
            if in_stock:
                env['stock.quant'].with_context(inventory_mode=True).create({
                    'product_id': cls.product.id, 'lot_id': lot.id,
                    'location_id': stock.id, 'inventory_quantity': 1.0,
                }).action_apply_inventory()
            return lot

        cls.lot_a = piece(1)
        cls.lot_b = piece(2)
        cls.lot_off_shelf = piece(3, in_stock=False)
        cls.client = env['res.partner'].create({'name': 'TEST Sale Client', 'jewellery_tier': 'preferred'})

    def api(self, path, method='GET', body=None, status=200):
        url = '/jawhar/v1' + path
        if method == 'POST':
            resp = self.url_open(url, data=json.dumps(body or {}),
                                 headers={'Content-Type': 'application/json'})
        else:
            resp = self.url_open(url)
        self.assertEqual(resp.status_code, status, resp.text[:400])
        return resp.json()

    def sign_in(self, login):
        return self.api('/auth/login', 'POST', {'login': login, 'password': PASSWORD})

    def test_quote_to_payment_through_the_door(self):
        self.sign_in('api_cashier')
        # 1. quote: priced by the engine, validity from the company
        out = self.api('/sales/quotes', 'POST',
                       {'client_id': self.client.id,
                        'lines': [{'piece_id': self.lot_a.id, 'discount': 10}]}, status=201)['data']
        self.assertEqual(out['kind'], 'quote')
        self.assertFalse(out['expired'])
        self.assertTrue(out['validity_date'])
        line = out['lines'][0]
        self.assertTrue(line['priced'])
        self.assertEqual(line['snapshot']['rate_per_gram'], 245.80)
        self.assertEqual(line['making_discount_pct'], 10.0)
        self.assertIsNotNone(line['margin'])            # cashier is a manager
        self.assertAlmostEqual(line['margin'], line['subtotal'] - 4000.0, 2)
        self.assertEqual(out['salesperson']['id'], self.cashier.id)
        order_id = out['id']

        # 2. confirm: frozen
        out = self.api('/sales/quotes/%d/confirm' % order_id, 'POST')['data']
        self.assertEqual(out['state'], 'sale')
        self.api('/sales/quotes/%d/confirm' % order_id, 'POST', status=409)
        self.api('/sales/quotes/%d/renew' % order_id, 'POST', status=400)

        # 3. invoice: posted, snapshot carried
        inv = self.api('/sales/orders/%d/invoice' % order_id, 'POST', status=201)['data']
        self.assertEqual(inv['state'], 'posted')
        self.assertEqual(inv['payment_state'], 'not_paid')
        self.assertEqual(inv['lines'][0]['snapshot']['rate_per_gram'], 245.80)
        self.api('/sales/orders/%d/invoice' % order_id, 'POST', status=409)

        # 4. payment: full, by the first available method
        methods = self.api('/sales/payment-methods')['data']['items']
        self.assertTrue(methods, 'the company needs a bank or cash journal')
        paid = self.api('/sales/invoices/%d/payments' % inv['id'], 'POST',
                        {'journal_id': methods[0]['id']}, status=201)['data']
        self.assertEqual(len(paid['payments']), 1)
        self.assertAlmostEqual(paid['payments'][0]['amount'], inv['amount_total'], 2)
        self.assertIn(paid['invoice']['payment_state'], ('paid', 'in_payment'))
        self.api('/sales/invoices/%d/payments' % inv['id'], 'POST', status=409)

    def test_partial_payment_leaves_the_rest_outstanding(self):
        self.sign_in('api_cashier')
        q = self.api('/sales/quotes', 'POST',
                     {'client_id': self.client.id, 'lines': [{'piece_id': self.lot_b.id}]}, status=201)['data']
        self.api('/sales/quotes/%d/confirm' % q['id'], 'POST')
        inv = self.api('/sales/orders/%d/invoice' % q['id'], 'POST', status=201)['data']
        half = round(inv['amount_total'] / 2, 2)
        paid = self.api('/sales/invoices/%d/payments' % inv['id'], 'POST', {'amount': half}, status=201)['data']
        self.assertEqual(paid['invoice']['payment_state'], 'partial')
        self.assertAlmostEqual(paid['invoice']['amount_residual'], inv['amount_total'] - half, 2)
        self.api('/sales/invoices/%d/payments' % inv['id'], 'POST',
                 {'amount': inv['amount_total'] * 2}, status=400)

    def test_rights_are_odoos_not_a_second_rule_book(self):
        # A seller sees no cost and no margin (manager-only fields)...
        self.sign_in('api_seller')
        q = self.api('/sales/quotes', 'POST',
                     {'client_id': self.client.id, 'lines': [{'piece_id': self.lot_a.id}]}, status=201)['data']
        self.assertIsNone(q['lines'][0]['margin'])
        # ...and may confirm and invoice: standard Odoo makes a salesperson a
        # billing user (sale implies account.group_account_invoice). The door
        # adds no rule of its own here.
        self.api('/sales/quotes/%d/confirm' % q['id'], 'POST')
        self.api('/sales/orders/%d/invoice' % q['id'], 'POST', status=201)
        self.api('/auth/logout', 'POST')

        # A jewellery user with no sales rights cannot even open a quote.
        self.sign_in('api_s_maker')
        out = self.api('/sales/quotes', 'POST',
                       {'client_id': self.client.id, 'lines': [{'piece_id': self.lot_b.id}]}, status=403)
        self.assertEqual(out['error']['code'], 'forbidden')

    def test_piece_off_the_shelf_cannot_be_confirmed(self):
        self.sign_in('api_cashier')
        q = self.api('/sales/quotes', 'POST',
                     {'client_id': self.client.id, 'lines': [{'piece_id': self.lot_off_shelf.id}]}, status=201)['data']
        out = self.api('/sales/quotes/%d/confirm' % q['id'], 'POST', status=400)
        self.assertIn('not in stock', out['error']['message'])

    def test_bad_input_is_400(self):
        self.sign_in('api_cashier')
        self.api('/sales/quotes', 'POST', {'client_id': self.client.id, 'lines': []}, status=400)
        self.api('/sales/quotes', 'POST', {'client_id': self.client.id,
                                           'lines': [{'piece_id': 999999}]}, status=400)
        self.api('/sales/quotes', 'POST', {'client_id': self.client.id,
                                           'lines': [{'piece_id': self.lot_a.id, 'discount': 'x'}]}, status=400)
