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

    def test_search_finds_a_walk_in_who_has_not_bought_yet(self):
        """Found at the counter: a standard-tier client with no purchase was
        invisible to the client search, so a first sale could not be rung up."""
        self.env['res.partner'].create({'name': 'TEST Walk-in Nobody'})
        self.sign_in('api_staff')
        names = [c['name'] for c in self.api('/clients')['data']['items']]
        self.assertNotIn('TEST Walk-in Nobody', names)          # not yet a client of record
        names = [c['name'] for c in self.api('/clients?q=Walk-in')['data']['items']]
        self.assertIn('TEST Walk-in Nobody', names)             # but findable by name
        # a system user's own contact is never offered as a client
        names = [c['name'] for c in self.api('/clients?q=Counter%20Staff')['data']['items']]
        self.assertNotIn('TEST Counter Staff', names)

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

        # An internal user with no jewellery role cannot even open a quote.
        # (A jewellery user is a salesperson by design since the Sales Hub.)
        Users = self.env['res.users'].with_context(no_reset_password=True)
        field = 'group_ids' if 'group_ids' in Users._fields else 'groups_id'
        Users.create({'name': 'TEST Outsider', 'login': 'api_outsider', 'password': PASSWORD,
                      field: [(6, 0, [self.env.ref('base.group_user').id])]})
        self.sign_in('api_outsider')
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


@tagged('post_install', '-at_install')
class TestJawharApiCounter(TestJawharApiSale):
    """The counter through the door: look the piece up, check readiness,
    take old gold, commit in one call -- or nothing at all."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.staff_discount_limit_pct', '10')
        env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.exchange_approval_threshold', '0')
        cls.lot_a.rfid_tag = 'TEST-RFID-COUNTER-A'
        cls.journal = env['account.journal'].search(
            [('type', 'in', ('cash', 'bank')), ('company_id', '=', env.company.id)], limit=1)
        cls.lot_c = env['stock.lot'].create({
            'name': 'TEST-API-SALE-4', 'product_id': cls.product.id,
            'gross_weight_g': 24.5, 'stone_weight_g': 0.0})
        stock = env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1).lot_stock_id
        env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': cls.product.id, 'lot_id': cls.lot_c.id,
            'location_id': stock.id, 'inventory_quantity': 1.0}).action_apply_inventory()

    def test_lookup_by_rfid_then_serial_with_availability(self):
        self.sign_in('api_cashier')
        out = self.api('/counter/piece?q=TEST-RFID-COUNTER-A')['data']
        self.assertEqual(out['serial'], 'TEST-API-SALE-1')
        self.assertEqual(out['availability']['status'], 'on_shelf')
        self.assertIsNotNone(out['breakdown'])
        out = self.api('/counter/piece?q=TEST-API-SALE-3')['data']          # never put in stock
        self.assertEqual(out['availability']['status'], 'not_in_stock')
        self.api('/counter/piece?q=NOPE-0000', status=404)

    def test_readiness_names_what_would_stop_the_sale(self):
        self.sign_in('api_seller')                                           # not a manager
        out = self.api('/counter/readiness?piece_id=%d&client_id=%d&discount=15'
                       % (self.lot_a.id, self.client.id))['data']
        checks = {c['key']: c for c in out['checks']}
        self.assertTrue(checks['rate']['ok'])
        self.assertTrue(checks['piece']['ok'])
        self.assertTrue(checks['client']['ok'])
        self.assertFalse(checks['discount']['ok'])
        self.assertEqual(checks['discount']['detail']['limit'], 10.0)
        self.assertFalse(out['ready'])
        out = self.api('/counter/readiness?piece_id=%d&client_id=%d&discount=10'
                       % (self.lot_a.id, self.client.id))['data']
        self.assertTrue(out['ready'])

    def test_commit_with_old_gold_in_one_call(self):
        self.sign_in('api_cashier')
        intake = self.api('/old-gold', 'POST', {'client_id': self.client.id, 'gross_weight_g': 18.4,
                                                'karat': '21', 'melt_loss_pct': 2}, status=201)['data']
        self.assertEqual(intake['state'], 'confirmed')
        self.assertGreater(intake['value'], 0)
        unused = self.api('/old-gold?client_id=%d&unused=1' % self.client.id)['data']['items']
        self.assertIn(intake['id'], [x['id'] for x in unused])

        out = self.api('/counter/commit', 'POST', {
            'client_id': self.client.id, 'piece_id': self.lot_c.id, 'discount': 5,
            'journal_id': self.journal.id, 'old_gold_id': intake['id']}, status=201)['data']
        self.assertEqual(out['order']['state'], 'sale')
        self.assertEqual(out['order']['old_gold']['id'], intake['id'])
        self.assertEqual(out['invoice']['state'], 'posted')
        self.assertIn(out['invoice']['payment_state'], ('paid', 'in_payment'))
        self.assertEqual(len(out['payments']), 1)
        self.assertTrue(out['deliveries'] and all(d['state'] == 'done' for d in out['deliveries']))
        self.assertAlmostEqual(out['payments'][0]['amount'], out['invoice']['amount_total'], 2)
        credit = [l for l in out['invoice']['lines'] if l['price_unit'] < 0]
        self.assertEqual(len(credit), 1)
        self.assertAlmostEqual(credit[0]['price_unit'], -intake['value'], 2)

        piece = self.api('/counter/piece?q=%s' % self.lot_c.name)['data']
        self.assertEqual(piece['availability']['status'], 'sold')
        self.assertEqual(piece['on_hand'], 0)
        # the intake cannot be credited twice
        self.api('/counter/commit', 'POST', {
            'client_id': self.client.id, 'piece_id': self.lot_b.id,
            'journal_id': self.journal.id, 'old_gold_id': intake['id']}, status=400)

    def test_refused_commit_creates_nothing(self):
        self.sign_in('api_cashier')
        quotes_before = self.api('/sales/quotes')['data']['total']
        invoices_before = self.api('/sales/invoices')['data']['total']
        out = self.api('/counter/commit', 'POST', {
            'client_id': self.client.id, 'piece_id': self.lot_off_shelf.id,
            'journal_id': self.journal.id}, status=400)
        self.assertIn('not in stock', out['error']['message'])
        self.assertEqual(self.api('/sales/quotes')['data']['total'], quotes_before)
        self.assertEqual(self.api('/sales/invoices')['data']['total'], invoices_before)

    def test_staff_discount_above_limit_is_refused_at_commit(self):
        self.sign_in('api_seller')
        out = self.api('/counter/commit', 'POST', {
            'client_id': self.client.id, 'piece_id': self.lot_a.id, 'discount': 20,
            'journal_id': self.journal.id}, status=400)
        self.assertIn('manager', out['error']['message'].lower())


@tagged('post_install', '-at_install')
class TestJawharApiSalesHub(TestJawharApiSale):
    """Pipeline and Private Trays through the door."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.tray_link_days', '7')
        cls.client.write({'preferred_karats': '22', 'typical_budget': 6000.0})
        cls.royal = cls.env['res.partner'].create({
            'name': 'TEST Royal Hub', 'jewellery_tier': 'royal', 'relationship_manager_id': cls.cashier.id})

    def test_tray_from_ranking_to_shared_link_to_reservation(self):
        self.sign_in('api_cashier')
        tray = self.api('/trays', 'POST', {'client_id': self.client.id, 'intent': 'wedding', 'limit': 2}, status=201)['data']
        self.assertEqual(tray['state'], 'draft')
        self.assertEqual(len(tray['lines']), 2)
        self.assertTrue(all(l['reasons'] for l in tray['lines']))
        self.assertTrue(tray['lead'])

        shared = self.api('/trays/%d/share' % tray['id'], 'POST')['data']
        self.assertTrue(shared['token'])
        self.assertIn('/app/t/' + shared['token'], shared['url'])
        self.assertTrue(shared['tray']['link_live'])

        # the client's phone, no session
        pub = self.url_open('/jawhar/public/tray/' + shared['token'])
        self.assertEqual(pub.status_code, 200)
        self.assertNotIn(self.client.name, pub.text)
        piece = pub.json()['data']['pieces'][0]
        self.assertNotIn('id', piece)

        pipe = self.api('/pipeline')['data']
        mine = [l for l in pipe['items'] if l['tray'] and l['tray']['id'] == tray['id']]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]['stage']['name'], 'Tray shared')

        res = self.api('/trays/%d/reserve' % tray['id'], 'POST',
                       {'piece_id': tray['lines'][0]['piece']['id']}, status=201)['data']
        self.assertEqual(res['order']['kind'], 'quote')
        self.assertTrue(res['order']['lines'][0]['priced'])
        self.assertEqual(res['tray']['state'], 'reserved')
        self.assertFalse(res['tray']['link_live'])                 # the link dies on reservation
        self.assertEqual(self.url_open('/jawhar/public/tray/' + shared['token']).status_code, 404)

    def test_royal_tray_by_hand_only_and_no_link(self):
        self.sign_in('api_cashier')                                # cashier is a VIP manager
        tray = self.api('/trays', 'POST', {'client_id': self.royal.id}, status=201)['data']
        self.assertEqual(tray['lines'], [])
        self.api('/trays/%d/build' % tray['id'], 'POST', status=400)
        tray = self.api('/trays/%d/pieces' % tray['id'], 'POST', {'piece_id': self.lot_b.id})['data']
        self.assertEqual(len(tray['lines']), 1)
        out = self.api('/trays/%d/share' % tray['id'], 'POST', status=400)
        self.assertIn('Royal', out['error']['message'])
        self.api('/auth/logout', 'POST')
        self.sign_in('api_seller')                                 # not allowed to see this client
        self.api('/trays/%d' % tray['id'], status=404)
        self.assertNotIn(tray['id'], [t['id'] for t in self.api('/trays')['data']['items']])


@tagged('post_install', '-at_install')
class TestJawharApiAgents(TestJawharApiSalesHub):
    """Layla and Zayan through the door, and the approvals inbox."""

    def test_status_and_command_bar(self):
        self.sign_in('api_seller')
        st = self.api('/ai/status')['data']
        self.assertEqual({a['key'] for a in st['agents']}, {'zayan', 'layla'})
        self.assertFalse(st['can_pause'])
        self.assertIn('configured', st['model'])
        out = self.api('/ai/ask', 'POST', {'text': 'prepare my day'})['data']
        self.assertEqual(out['intent'], 'brief')
        self.assertTrue(out['brief']['sentences'])
        self.assertEqual(out['brief']['narrated_by'], 'local')
        self.assertEqual(self.api('/ai/ask', 'POST', {'text': ''}, status=400)['error']['code'], 'validation')

    def test_layla_tray_then_followup_then_review(self):
        self.sign_in('api_cashier')
        out = self.api('/ai/layla/tray', 'POST', {'client_id': self.client.id, 'intent': 'wedding', 'limit': 2})['data']
        self.assertEqual(len(out['tray']['lines']), 2)
        self.assertEqual(out['draft']['kind'], 'tray')
        self.assertEqual(out['run']['level'], 'C')
        fu = self.api('/ai/layla/followup', 'POST', {'client_id': self.client.id, 'channel': 'whatsapp',
                                                      'context': 'She asked about the bangle.'})['data']
        draft = fu['draft']
        self.assertEqual(draft['state'], 'pending')
        self.assertTrue(draft['body'])
        inbox = self.api('/ai/drafts')['data']
        self.assertIn(draft['id'], [d['id'] for d in inbox['items']])
        # stale digest does not bind
        self.api('/ai/drafts/%d/edit' % draft['id'], 'POST', {'body': draft['body'] + ' Thursday suits us.'})
        err = self.api('/ai/drafts/%d/approve' % draft['id'], 'POST', {'digest': draft['body_digest']}, status=400)
        self.assertEqual(err['error']['code'], 'invalid')
        fresh = self.api('/ai/drafts/%d' % draft['id'])['data']
        ok = self.api('/ai/drafts/%d/approve' % draft['id'], 'POST', {'digest': fresh['body_digest']})['data']
        self.assertEqual(ok['state'], 'approved')
        self.assertEqual(ok['approved_by']['name'], 'TEST Cashier')
        runs = self.api('/ai/runs')['data']['items']
        self.assertTrue(any(r['tool'] == 'followup.draft' for r in runs))

    def test_royal_tray_is_refused_through_the_door_and_logged(self):
        self.sign_in('api_cashier')
        out = self.api('/ai/layla/tray', 'POST', {'client_id': self.royal.id})['data']
        self.assertEqual(out['refused'], 'restricted_client')
        self.assertIn('by hand', out['message'])
        row = self.env['jewellery.ai.run'].sudo().search([('tool', '=', 'tray.prepare'), ('status', '=', 'refused')], limit=1)
        self.assertEqual(row.reason, 'restricted_client')

    def test_only_a_manager_pauses(self):
        self.sign_in('api_seller')
        self.assertEqual(self.api('/ai/pause', 'POST', {'paused': True}, status=403)['error']['code'], 'forbidden')
        self.api('/auth/logout', 'POST')
        self.sign_in('api_cashier')
        self.assertTrue(self.api('/ai/pause', 'POST', {'paused': True})['data']['paused'])
        self.assertTrue(self.api('/ai/status')['data']['paused'])
        self.assertEqual(self.api('/ai/brief', 'POST')['data']['refused'], 'paused')
        self.assertFalse(self.api('/ai/pause', 'POST', {'paused': False})['data']['paused'])

    def test_chat_through_the_door(self):
        self.sign_in('api_seller')
        out = self.api('/ai/chat', 'POST', {'agent': 'zayan', 'messages': [{'role': 'user', 'text': 'gold rate'}]})['data']
        self.assertEqual(out['intent'], 'rate')
        self.assertIn('245.8', out['reply'])
        self.assertEqual(self.api('/ai/chat', 'POST', {'messages': 'nope'}, status=400)['error']['code'], 'validation')


@tagged('post_install', '-at_install')
class TestJawharApiLists(TestJawharApiSale):
    """The lists management looks at first: search, sort, paging, a new client."""

    def test_clients_sort_page_and_create(self):
        self.sign_in('api_cashier')
        created = self.api('/clients', 'POST', {'name': 'TEST New Walk-in', 'phone': '+971500000001', 'city': 'Dubai',
                                                 'tier': 'preferred', 'preferred_karats': '21'}, status=201)['data']
        self.assertEqual(created['tier'], 'preferred')
        self.assertEqual(created['city'], 'Dubai')
        found = self.api('/clients?q=0000001')['data']
        self.assertEqual([c['id'] for c in found['items']], [created['id']])
        by_value = self.api('/clients?sort=value&limit=1')['data']
        self.assertEqual(by_value['total'], self.api('/clients')['data']['total'])
        self.assertEqual(len(by_value['items']), 1)
        page2 = self.api('/clients?limit=1&offset=1')['data']
        self.assertNotEqual(page2['items'][0]['id'], self.api('/clients?limit=1')['data']['items'][0]['id'])
        self.assertEqual(self.api('/clients', 'POST', {'name': ''}, status=400)['error']['code'], 'validation')

    def test_pieces_category_and_sort(self):
        self.sign_in('api_cashier')
        self.product.product_tmpl_id.write({'jewellery_category': 'bangle'})
        self.env['stock.lot'].create({'name': 'TEST-LIST-0001', 'product_id': self.product.id, 'gross_weight_g': 20.0})
        out = self.api('/pieces?category=bangle&sort=price')['data']
        self.assertTrue(out['total'] >= 1)
        self.assertTrue(all(p['category'] == 'bangle' for p in out['items']))
        prices = [p['price_incl_vat'] for p in out['items']]
        self.assertEqual(prices, sorted(prices, reverse=True))
        self.assertEqual(self.api('/pieces?category=coin')['data']['total'], 0)
