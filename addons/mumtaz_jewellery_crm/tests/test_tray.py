"""The Private Tray: who may be ranked, what may go on a tray, how the link
behaves, and that a request is not a reservation."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import HttpCase, TransactionCase, tagged


class TrayCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env.company.quotation_validity_days = 7
        env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.vat_rate', '5')
        env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.tray_link_days', '7')
        Users = env['res.users'].with_context(no_reset_password=True)
        field = 'group_ids' if 'group_ids' in Users._fields else 'groups_id'
        g_user = env.ref('mumtaz_jewellery.group_jewellery_user')
        g_mgr = env.ref('mumtaz_jewellery.group_jewellery_manager')
        g_vip = env.ref('mumtaz_jewellery_vip.group_vip_manager')
        cls.staff = Users.create({'name': 'TEST Tray Staff', 'login': 'tray_staff', 'password': 'tray-pass',
                                  field: [(6, 0, [g_user.id])]})
        cls.maker = Users.create({'name': 'TEST Tray Maker', 'login': 'tray_maker', field: [(6, 0, [g_mgr.id])]})
        cls.checker = Users.create({'name': 'TEST Tray Checker', 'login': 'tray_checker',
                                    field: [(6, 0, [g_mgr.id, g_vip.id])]})
        rate = env['jewellery.gold.rate'].with_user(cls.maker).create({'rate_per_gram': 245.80})
        rate.with_user(cls.checker).action_approve()

        cls.product = env['product.product'].create({
            'name': 'TEST 22K bangle', 'type': 'consu', 'is_storable': True, 'tracking': 'serial',
            'is_jewellery': True, 'jewellery_karat': '22', 'jewellery_wastage_pct': 2.0,
            'jewellery_making_type': 'percent', 'jewellery_making_value': 10.0,
        })
        cls.stock = env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1).lot_stock_id
        cls.lots = [cls._piece(i, tags='wedding' if i % 2 else '') for i in range(1, 7)]
        cls.client = env['res.partner'].create({
            'name': 'TEST Tray Client', 'jewellery_tier': 'preferred', 'preferred_karats': '22',
            'typical_budget': 6000.0})
        cls.private = env['res.partner'].create({
            'name': 'TEST Private Client', 'jewellery_tier': 'private',
            'relationship_manager_id': cls.checker.id})
        cls.royal = env['res.partner'].create({
            'name': 'TEST Royal Client', 'jewellery_tier': 'royal',
            'relationship_manager_id': cls.checker.id})

    @classmethod
    def _piece(cls, seq, in_stock=True, tags=''):
        lot = cls.env['stock.lot'].create({
            'name': 'TEST-TRAY-%d' % seq, 'product_id': cls.product.id,
            'gross_weight_g': 20.0 + seq, 'stone_weight_g': 0.0, 'occasion_tags': tags})
        if in_stock:
            cls.env['stock.quant'].with_context(inventory_mode=True).create({
                'product_id': cls.product.id, 'lot_id': lot.id,
                'location_id': cls.stock.id, 'inventory_quantity': 1.0}).action_apply_inventory()
        return lot

    def _tray(self, partner=None, user=None):
        Tray = self.env['jewellery.tray'].with_user(user or self.staff)
        return Tray.create({'partner_id': (partner or self.client).id})


@tagged('post_install', '-at_install')
class TestTray(TrayCase):

    def test_build_ranks_eligible_pieces_with_reasons_and_opens_the_opportunity(self):
        tray = self._tray()
        ranked = tray.action_build(limit=3)
        self.assertEqual(len(ranked), 3)
        self.assertEqual(len(tray.line_ids), 3)
        for line in tray.line_ids:
            self.assertTrue(line.reasons)
            self.assertGreater(line.price, 0)
            self.assertIn('22K', line.reasons)            # the preference is a stored reason
        self.assertTrue(tray.lead_id)
        self.assertEqual(tray.lead_id.stage_id, self.env.ref('mumtaz_jewellery_crm.stage_enquiry'))
        self.assertEqual(tray.lead_id.partner_id, self.client)
        self.assertAlmostEqual(tray.lead_id.expected_revenue, sum(tray.line_ids.mapped('price')), 2)

    def test_sold_and_on_approval_pieces_never_reach_a_tray(self):
        sold_lot, memo_lot = self.lots[0], self.lots[1]
        order = self.env['sale.order'].create({
            'partner_id': self.client.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1,
                                   'jewellery_lot_id': sold_lot.id})]})
        order.order_line.action_price_from_rate()
        order.action_confirm()
        self.env['jewellery.approval.memo'].create({
            'partner_id': self.client.id, 'lot_ids': [(6, 0, [memo_lot.id])],
            'date_out': fields.Date.context_today(order),
            'return_by': fields.Date.context_today(order) + timedelta(days=3)})
        tray = self._tray()
        tray.action_build(limit=5)
        on_tray = tray.line_ids.mapped('lot_id')
        self.assertNotIn(sold_lot, on_tray)
        self.assertNotIn(memo_lot, on_tray)
        with self.assertRaises(UserError):
            tray.action_add_piece(sold_lot)

    def test_private_and_royal_are_never_ranked_but_may_be_chosen_by_hand(self):
        for partner in (self.private, self.royal):
            tray = self._tray(partner, user=self.checker)
            with self.assertRaises(UserError):
                tray.action_build()
            tray.action_add_piece(self.lots[2])
            self.assertEqual(len(tray.line_ids), 1)

    def test_a_royal_tray_never_leaves_the_building(self):
        tray = self._tray(self.royal, user=self.checker)
        tray.action_add_piece(self.lots[2])
        with self.assertRaises(UserError):
            tray.action_share()
        self.assertFalse(tray.token_digest)

    def test_staff_cannot_see_a_private_clients_tray(self):
        tray = self._tray(self.private, user=self.checker)
        tray.action_add_piece(self.lots[3])
        Tray = self.env['jewellery.tray']
        self.assertIn(tray, Tray.with_user(self.checker).search([]))
        self.assertNotIn(tray, Tray.with_user(self.staff).search([]))
        self.assertFalse(Tray.with_user(self.staff).search_count([('id', '=', tray.id)]))

    def test_share_stores_only_a_digest_and_the_link_expires_and_revokes(self):
        tray = self._tray()
        tray.action_build(limit=3)
        token = tray.action_share()
        self.assertTrue(token and len(token) > 20)
        self.assertNotIn(token, tray.token_digest)
        self.assertEqual(tray.state, 'shared')
        self.assertEqual(tray.lead_id.stage_id, self.env.ref('mumtaz_jewellery_crm.stage_tray'))
        Tray = self.env['jewellery.tray']
        self.assertEqual(Tray._find_by_token(token), tray)
        self.assertIsNone(Tray._find_by_token('not-a-token'))
        tray.sudo().token_expires = fields.Datetime.now() - timedelta(minutes=1)
        self.assertIsNone(Tray._find_by_token(token))
        tray.sudo().token_expires = fields.Datetime.now() + timedelta(days=1)
        tray.action_revoke()
        self.assertIsNone(Tray._find_by_token(token))

    def test_public_payload_carries_no_client_data_and_no_internal_ids(self):
        tray = self._tray()
        tray.action_build(limit=3)
        tray.action_share()
        payload = tray._public_payload()
        text = str(payload)
        self.assertNotIn(self.client.name, text)
        self.assertNotIn('TEST Tray Staff', text)
        self.assertNotIn(str(self.client.id), payload.get('tray', ''))
        for p in payload['pieces']:
            self.assertEqual(set(p), {'ref', 'product', 'karat', 'net_weight_g', 'price', 'why', 'feedback', 'question'})
            self.assertEqual(len(p['ref']), 10)
            self.assertNotIn('TEST-TRAY', p['ref'])

    def test_feedback_and_viewing_request_move_the_opportunity_but_reserve_nothing(self):
        tray = self._tray()
        tray.action_build(limit=3)
        tray.action_share()
        ref = tray.line_ids[0].public_ref
        tray._public_feedback(ref, 'like')
        tray._public_feedback(ref, 'question', 'Does it come in 21K?')
        self.assertEqual(tray.line_ids[0].feedback, 'like')
        self.assertIn('21K', tray.line_ids[0].question)
        tray._public_request_viewing('Thursday afternoon', 'with my mother')
        self.assertEqual(tray.state, 'viewing')
        self.assertEqual(tray.lead_id.stage_id, self.env.ref('mumtaz_jewellery_crm.stage_viewing'))
        self.assertTrue(tray.lead_id.activity_ids)
        self.assertIn('Viewing requested', tray.lead_id.activity_ids[0].summary)
        self.assertFalse(tray.reservation_order_id)                      # a request is not a reservation
        for lot in tray.line_ids.mapped('lot_id'):
            self.assertEqual(lot.product_qty, 1.0)

    def test_reserve_makes_a_priced_quote_and_the_sale_wins_the_opportunity(self):
        tray = self._tray()
        tray.action_build(limit=3)
        tray.action_share()
        lot = tray.line_ids[0].lot_id
        order = tray.with_user(self.staff).action_reserve(lot)
        self.assertEqual(order.state, 'draft')
        self.assertTrue(order.order_line.jewellery_is_priced)
        self.assertEqual(order.order_line.jewellery_lot_id, lot)
        self.assertEqual(tray.state, 'reserved')
        self.assertTrue(tray.token_revoked)
        self.assertEqual(tray.lead_id.stage_id, self.env.ref('mumtaz_jewellery_crm.stage_reserved'))
        order.action_confirm()
        self.assertEqual(tray.state, 'won')
        self.assertTrue(tray.lead_id.stage_id.is_won)
        self.assertEqual(tray.lead_id.probability, 100)

    def test_a_piece_that_went_elsewhere_is_dropped_on_open(self):
        tray = self._tray()
        tray.action_build(limit=3)
        token = tray.action_share()
        lot = tray.line_ids[0].lot_id
        other = self.env['sale.order'].create({
            'partner_id': self.env['res.partner'].create({'name': 'TEST Other'}).id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1,
                                   'jewellery_lot_id': lot.id})]})
        other.order_line.action_price_from_rate()
        other.action_confirm()
        payload = self.env['jewellery.tray']._find_by_token(token)._public_payload()
        self.assertEqual(len(payload['pieces']), 2)
        self.assertNotIn(lot, tray.line_ids.mapped('lot_id'))


@tagged('post_install', '-at_install')
class TestPublicTrayHttp(HttpCase, TrayCase):

    def test_the_link_works_without_a_login_and_dies_when_revoked(self):
        tray = self._tray()
        tray.action_build(limit=3)
        token = tray.action_share()
        resp = self.url_open('/jawhar/public/tray/' + token)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(len(data['pieces']), 3)
        self.assertNotIn(self.client.name, resp.text)

        import json
        ref = data['pieces'][0]['ref']
        resp = self.url_open('/jawhar/public/tray/%s/feedback' % token,
                             data=json.dumps({'ref': ref, 'kind': 'like'}),
                             headers={'Content-Type': 'application/json'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['pieces'][0]['feedback'], 'like')
        resp = self.url_open('/jawhar/public/tray/%s/viewing' % token,
                             data=json.dumps({'preferred': 'Saturday', 'note': ''}),
                             headers={'Content-Type': 'application/json'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['data']['viewing_requested'])
        self.assertEqual(tray.state, 'viewing')

        tray.action_revoke()
        self.assertEqual(self.url_open('/jawhar/public/tray/' + token).status_code, 404)
        self.assertEqual(self.url_open('/jawhar/public/tray/garbage-token').status_code, 404)
