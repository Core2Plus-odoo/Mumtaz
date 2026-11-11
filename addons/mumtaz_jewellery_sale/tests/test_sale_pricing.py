"""Slice 1: the price on a sale line comes from the approved rate, and stops
moving the moment the client agrees to it.

The acceptance test the roadmap names is test_confirmed_order_survives_a_rate
_change: gold moves daily, and a confirmed order must not.
"""
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.mumtaz_jewellery.services import pricing


@tagged('post_install', '-at_install')
class TestSalePricing(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env['ir.config_parameter'].sudo().set_param(
            'mumtaz_jewellery.vat_rate', '5')

        group_mgr = cls.env.ref('mumtaz_jewellery.group_jewellery_manager')
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        field = 'group_ids' if 'group_ids' in Users._fields else 'groups_id'
        cls.maker = Users.create({
            'name': 'TEST Rate Maker', 'login': 'test_sale_maker',
            field: [(6, 0, [group_mgr.id])]})
        cls.checker = Users.create({
            'name': 'TEST Rate Checker', 'login': 'test_sale_checker',
            field: [(6, 0, [group_mgr.id])]})

        cls.product = cls.env['product.product'].create({
            'name': 'TEST 22K bangle',
            'type': 'consu',
            'is_storable': True,
            'tracking': 'serial',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'TEST Client'})

    # ---- helpers --------------------------------------------------------
    def _approve_rate(self, value):
        """Create and approve a rate through the real maker-checker path."""
        rate = self.env['jewellery.gold.rate'].with_user(self.maker).create({
            'rate_per_gram': value,
            'effective_at': fields.Datetime.now(),
        })
        rate.with_user(self.checker).action_approve()
        return rate

    def _piece(self, **overrides):
        values = {
            'name': 'TEST-PIECE-%s' % (overrides.pop('seq', 1)),
            'product_id': self.product.id,
            'gross_weight_g': 24.5,
            'stone_weight_g': 0.0,
            'karat': '22',
            'wastage_pct': 2.0,
            'making_type': 'percent',
            'making_value': 10.0,
            'stones_value': 0.0,
        }
        values.update(overrides)
        return self.env['stock.lot'].create(values)

    def _order(self, lot, discount=0.0):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'jewellery_lot_id': lot.id,
                'jewellery_making_discount_pct': discount,
            })],
        })
        return order, order.order_line[0]

    # ---- the engine is the only source of a number ----------------------
    def test_price_matches_the_engine_to_the_cent(self):
        self._approve_rate(245.80)
        lot = self._piece(seq=1)
        order, line = self._order(lot)
        line.action_price_from_rate()

        expected = pricing.price_piece(
            net_weight_g=24.5, karat=22, rate_24k_per_g=245.80,
            wastage_pct=2.0, making_type='percent', making_value=10.0,
            stones_value=0.0, vat_rate=0,
        )
        self.assertAlmostEqual(line.price_unit, float(expected['subtotal']), 2)
        self.assertAlmostEqual(
            line.jewellery_metal_value, float(expected['metal_value']), 2)
        self.assertAlmostEqual(
            line.jewellery_making_charge, float(expected['making_charge']), 2)
        self.assertAlmostEqual(
            line.jewellery_fine_weight_g, float(expected['fine_weight_g']), 4)
        self.assertEqual(line.jewellery_rate_per_gram, 245.80)
        self.assertTrue(line.jewellery_is_priced)

    def test_price_unit_excludes_vat(self):
        """Odoo's tax engine owns tax. Taking VAT from both charges it twice."""
        self._approve_rate(245.80)
        lot = self._piece(seq=2)
        order, line = self._order(lot)
        line.action_price_from_rate()
        with_vat = pricing.price_piece(
            net_weight_g=24.5, karat=22, rate_24k_per_g=245.80,
            wastage_pct=2.0, making_type='percent', making_value=10.0,
            stones_value=0.0, vat_rate=5,
        )
        self.assertNotAlmostEqual(
            line.price_unit, float(with_vat['total']), 2,
            msg='price_unit must be the pre-tax subtotal, not the VAT total')
        self.assertAlmostEqual(
            line.price_unit, float(with_vat['subtotal']), 2)

    # ---- THE acceptance test --------------------------------------------
    def test_confirmed_order_survives_a_rate_change(self):
        """Gold moves daily. A confirmed order must not."""
        self._approve_rate(245.80)
        lot = self._piece(seq=3)
        order, line = self._order(lot)
        line.action_price_from_rate()
        agreed_price = line.price_unit
        agreed_metal = line.jewellery_metal_value
        agreed_rate = line.jewellery_rate_per_gram
        order.action_confirm()

        # the market moves 20% overnight
        self._approve_rate(295.00)
        line.invalidate_recordset()

        self.assertEqual(line.price_unit, agreed_price)
        self.assertEqual(line.jewellery_metal_value, agreed_metal)
        self.assertEqual(line.jewellery_rate_per_gram, agreed_rate)
        self.assertNotEqual(
            line.jewellery_rate_per_gram, 295.00,
            'the confirmed line must still carry the rate it was sold at')

    def test_confirmed_line_refuses_a_direct_write(self):
        self._approve_rate(245.80)
        lot = self._piece(seq=4)
        order, line = self._order(lot)
        line.action_price_from_rate()
        order.action_confirm()
        with self.assertRaises(UserError):
            line.write({'price_unit': 1.0})

    def test_the_freeze_holds_for_sudo(self):
        """A rate feed or server action must not reprice history either."""
        self._approve_rate(245.80)
        lot = self._piece(seq=5)
        order, line = self._order(lot)
        line.action_price_from_rate()
        order.action_confirm()
        with self.assertRaises(UserError):
            line.sudo().write({'jewellery_metal_value': 0.0})

    def test_confirmed_order_refuses_repricing(self):
        self._approve_rate(245.80)
        lot = self._piece(seq=6)
        order, line = self._order(lot)
        line.action_price_from_rate()
        order.action_confirm()
        self._approve_rate(295.00)
        with self.assertRaises(UserError):
            line.action_price_from_rate()

    # ---- a draft is still a draft ---------------------------------------
    def test_draft_line_reprices_to_the_new_rate(self):
        self._approve_rate(245.80)
        lot = self._piece(seq=7)
        order, line = self._order(lot)
        line.action_price_from_rate()
        first = line.price_unit

        self._approve_rate(295.00)
        line.action_price_from_rate()

        self.assertGreater(line.price_unit, first)
        self.assertEqual(line.jewellery_rate_per_gram, 295.00)

    # ---- the discount never touches metal -------------------------------
    def test_dealer_discount_applies_to_making_only(self):
        self._approve_rate(245.80)
        lot_full = self._piece(seq=8)
        lot_disc = self._piece(seq=9)
        _o1, full = self._order(lot_full)
        _o2, discounted = self._order(lot_disc, discount=50.0)
        full.action_price_from_rate()
        discounted.action_price_from_rate()

        self.assertAlmostEqual(
            discounted.jewellery_metal_value, full.jewellery_metal_value, 2,
            msg='the metal is never discounted')
        self.assertAlmostEqual(
            discounted.jewellery_wastage_value, full.jewellery_wastage_value, 2)
        self.assertAlmostEqual(
            discounted.jewellery_making_charge,
            full.jewellery_making_charge / 2, 2)
        self.assertLess(discounted.price_unit, full.price_unit)

    # ---- refusals --------------------------------------------------------
    def test_pricing_without_an_approved_rate_is_refused(self):
        draft = self.env['jewellery.gold.rate'].with_user(self.maker).create({
            'rate_per_gram': 245.80,
            'effective_at': fields.Datetime.now(),
        })
        self.assertEqual(draft.state, 'draft')
        lot = self._piece(seq=10)
        order, line = self._order(lot)
        with self.assertRaises(Exception):
            line.action_price_from_rate()
        self.assertFalse(line.jewellery_is_priced)

    def test_confirm_refuses_an_unpriced_jewellery_line(self):
        self._approve_rate(245.80)
        lot = self._piece(seq=11)
        order, line = self._order(lot)
        self.assertFalse(line.jewellery_is_priced)
        with self.assertRaises(ValidationError):
            order.action_confirm()

    def test_a_line_without_a_piece_cannot_be_priced(self):
        self._approve_rate(245.80)
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id, 'product_uom_qty': 1})],
        })
        with self.assertRaises(UserError):
            order.order_line[0].action_price_from_rate()

    def test_an_ordinary_line_confirms_untouched(self):
        """Nothing here may break selling something that is not jewellery."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0})],
        })
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertEqual(order.order_line[0].price_unit, 100.0)

    # ---- the snapshot is not inherited by a copy -------------------------
    def test_duplicating_an_order_drops_the_snapshot(self):
        """A copy is a new negotiation and must be priced afresh."""
        self._approve_rate(245.80)
        lot = self._piece(seq=12)
        order, line = self._order(lot)
        line.action_price_from_rate()
        self.assertTrue(line.jewellery_is_priced)

        copy = order.copy()
        copied = copy.order_line[0]
        self.assertFalse(copied.jewellery_rate_id)
        self.assertFalse(copied.jewellery_priced_on)
        self.assertFalse(copied.jewellery_is_priced)
