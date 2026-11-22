"""Slice 1: what has to be true before a piece is agreed.

A quotation holds its rate until its validity date (the rate lock); after
that it must be renewed. A serial-tracked piece can be sold once: not while it
is on another live order, not when it is out of stock, not while it is out on
approval with a client. The check runs under a row lock on the piece.
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSaleCommitment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env.company
        cls.company.quotation_validity_days = 7
        env['ir.config_parameter'].sudo().set_param('mumtaz_jewellery.vat_rate', '5')

        group_mgr = env.ref('mumtaz_jewellery.group_jewellery_manager')
        group_user = env.ref('mumtaz_jewellery.group_jewellery_user')
        Users = env['res.users'].with_context(no_reset_password=True)
        field = 'group_ids' if 'group_ids' in Users._fields else 'groups_id'
        cls.maker = Users.create({'name': 'TEST Maker', 'login': 'test_commit_maker',
                                  field: [(6, 0, [group_mgr.id])]})
        cls.checker = Users.create({'name': 'TEST Checker', 'login': 'test_commit_checker',
                                    field: [(6, 0, [group_mgr.id])]})
        cls.staff = Users.create({'name': 'TEST Staff', 'login': 'test_commit_staff',
                                  field: [(6, 0, [group_user.id])]})

        cls.product = env['product.product'].create({
            'name': 'TEST 22K bangle', 'type': 'consu', 'is_storable': True,
            'tracking': 'serial', 'is_jewellery': True, 'jewellery_karat': '22',
            'jewellery_wastage_pct': 2.0, 'jewellery_making_type': 'percent',
            'jewellery_making_value': 10.0,
        })
        cls.client_a = env['res.partner'].create({'name': 'TEST Client A'})
        cls.client_b = env['res.partner'].create({'name': 'TEST Client B'})
        cls.stock = env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1).lot_stock_id

    # ---- helpers --------------------------------------------------------
    def _approve_rate(self, value):
        rate = self.env['jewellery.gold.rate'].with_user(self.maker).create({
            'rate_per_gram': value, 'effective_at': fields.Datetime.now()})
        rate.with_user(self.checker).action_approve()
        return rate

    def _piece(self, seq, in_stock=True, cost=None):
        lot = self.env['stock.lot'].create({
            'name': 'TEST-COMMIT-%d' % seq, 'product_id': self.product.id,
            'gross_weight_g': 24.5, 'stone_weight_g': 0.0, 'karat': '22',
            'wastage_pct': 2.0, 'making_type': 'percent', 'making_value': 10.0,
        })
        if cost is not None:
            lot.jewellery_cost_value = cost
        if in_stock:
            self.env['stock.quant'].with_context(inventory_mode=True).create({
                'product_id': self.product.id, 'lot_id': lot.id,
                'location_id': self.stock.id, 'inventory_quantity': 1.0,
            }).action_apply_inventory()
        return lot

    def _quote(self, partner, lot, priced=True):
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1,
                                   'jewellery_lot_id': lot.id})],
        })
        if priced:
            order.order_line.action_price_from_rate()
        return order

    # ---- validity: the rate lock -------------------------------------------
    def test_quote_gets_the_company_validity(self):
        self._approve_rate(245.80)
        order = self._quote(self.client_a, self._piece(1))
        self.assertEqual(order.validity_date,
                         fields.Date.context_today(order) + timedelta(days=7))
        self.assertFalse(order.jewellery_quote_expired)

    def test_rate_change_within_validity_does_not_touch_the_quote(self):
        """The lock: a quote keeps the rate it was priced at until it expires."""
        self._approve_rate(245.80)
        order = self._quote(self.client_a, self._piece(2))
        price_before = order.order_line.price_unit
        self._approve_rate(300.00)
        order.action_confirm()                       # still valid: confirms at 245.80
        self.assertEqual(order.state, 'sale')
        self.assertEqual(order.order_line.price_unit, price_before)
        self.assertEqual(order.order_line.jewellery_rate_per_gram, 245.80)

    def test_expired_quote_cannot_confirm_until_renewed(self):
        self._approve_rate(245.80)
        order = self._quote(self.client_a, self._piece(3))
        order.validity_date = fields.Date.context_today(order) - timedelta(days=1)
        self.assertTrue(order.jewellery_quote_expired)
        with self.assertRaises(ValidationError) as caught:
            order.action_confirm()
        self.assertIn('expired', str(caught.exception).lower())
        self.assertEqual(order.state, 'draft')

        self._approve_rate(300.00)
        order.action_renew_quote()
        self.assertEqual(order.order_line.jewellery_rate_per_gram, 300.00)
        self.assertEqual(order.validity_date,
                         fields.Date.context_today(order) + timedelta(days=7))
        self.assertFalse(order.jewellery_quote_expired)
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_confirmed_order_cannot_be_renewed(self):
        self._approve_rate(245.80)
        order = self._quote(self.client_a, self._piece(4))
        order.action_confirm()
        with self.assertRaises(UserError):
            order.action_renew_quote()

    # ---- the unique piece -------------------------------------------------
    def test_second_order_for_the_same_piece_is_refused(self):
        self._approve_rate(245.80)
        lot = self._piece(5)
        first = self._quote(self.client_a, lot)
        second = self._quote(self.client_b, lot)      # two clients, one bangle
        first.action_confirm()
        with self.assertRaises(ValidationError) as caught:
            second.action_confirm()
        self.assertIn(first.name, str(caught.exception))
        self.assertEqual(second.state, 'draft')

    def test_piece_not_in_stock_is_refused(self):
        self._approve_rate(245.80)
        order = self._quote(self.client_a, self._piece(6, in_stock=False))
        with self.assertRaises(ValidationError) as caught:
            order.action_confirm()
        self.assertIn('not in stock', str(caught.exception))

    def test_piece_out_on_approval_is_refused(self):
        self._approve_rate(245.80)
        lot = self._piece(7)
        memo = self.env['jewellery.approval.memo'].create({
            'partner_id': self.client_b.id, 'lot_ids': [(6, 0, [lot.id])],
            'date_out': fields.Date.context_today(lot),
            'return_by': fields.Date.context_today(lot) + timedelta(days=3),
        })
        order = self._quote(self.client_a, lot)
        with self.assertRaises(ValidationError) as caught:
            order.action_confirm()
        self.assertIn(memo.name, str(caught.exception))
        self.assertIn(self.client_b.name, str(caught.exception))

    def test_quantity_must_be_one(self):
        self._approve_rate(245.80)
        order = self._quote(self.client_a, self._piece(8))
        order.order_line.product_uom_qty = 2
        with self.assertRaises(ValidationError):
            order.action_confirm()

    # ---- cost basis and margin --------------------------------------------
    def test_margin_is_price_minus_recorded_cost_and_managers_only(self):
        self._approve_rate(245.80)
        lot = self._piece(9, cost=5000.0)
        order = self._quote(self.client_a, lot)
        line = order.order_line.with_user(self.maker)
        self.assertTrue(line.jewellery_has_cost)
        self.assertAlmostEqual(line.jewellery_margin, line.price_subtotal - 5000.0, 2)

        # No recorded cost is "unknown", not zero.
        lot_no_cost = self._piece(10)
        order2 = self._quote(self.client_a, lot_no_cost)
        self.assertFalse(order2.order_line.with_user(self.maker).jewellery_has_cost)

        # Counter staff cannot read cost or margin at all.
        from odoo.exceptions import AccessError
        with self.assertRaises(AccessError):
            lot.with_user(self.staff).read(['jewellery_cost_value'])
