"""Pieces (serial-tracked stock lots): weights, tag uniqueness, and the rule
that a displayed price always comes from the approved rate.
"""
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import JewelCommon


@tagged('post_install', '-at_install', 'mumtaz_jewel')
class TestPiece(JewelCommon):

    def test_net_weight_is_gross_minus_stones(self):
        piece = self._piece()
        self.assertEqual(round(piece.net_weight_g, 3), 10.0)

    def test_stone_weight_cannot_exceed_gross(self):
        piece = self._piece()
        with self.assertRaises(ValidationError):
            piece.write({'stone_weight_g': 99.0})

    def test_rfid_tag_is_unique_per_company(self):
        product = self._jewellery_product()
        first = self._piece(product)
        first.write({'rfid_tag': 'DEMO-TAG-1'})
        second = self.env['stock.lot'].create({
            'name': 'DEMO-PIECE-0002',
            'product_id': product.product_variant_id.id,
            'company_id': self.company.id,
            'gross_weight_g': 5.0,
            'karat': '22',
        })
        with self.assertRaises(ValidationError):
            second.write({'rfid_tag': 'DEMO-TAG-1'})

    def test_breakdown_matches_the_engine_and_adds_up(self):
        self._approved_rate(rate=100.0)
        breakdown = self._piece().get_price_breakdown()
        self.assertEqual(round(breakdown['metal_value'], 2), 916.67)
        self.assertEqual(round(breakdown['wastage_value'], 2), 18.33)
        self.assertEqual(round(breakdown['making_charge'], 2), 91.67)
        self.assertEqual(round(breakdown['stones_value'], 2), 50.0)
        self.assertEqual(round(breakdown['vat'], 2), 53.83)
        self.assertEqual(round(breakdown['total'], 2), 1130.50)
        self.assertEqual(
            round(breakdown['subtotal'], 2),
            round(breakdown['metal_value'] + breakdown['wastage_value']
                  + breakdown['making_charge'] + breakdown['stones_value'], 2))

    def test_a_dealer_discount_never_touches_the_metal(self):
        self._approved_rate(rate=100.0)
        piece = self._piece()
        retail = piece.get_price_breakdown()
        trade = piece.get_price_breakdown(making_discount_pct=50.0)
        self.assertEqual(trade['metal_value'], retail['metal_value'])
        self.assertEqual(trade['wastage_value'], retail['wastage_value'])
        self.assertLess(trade['making_charge'], retail['making_charge'])
        self.assertEqual(round(trade['making_charge'], 2), 45.83)

    def test_pricing_without_a_karat_is_refused(self):
        self._approved_rate(rate=100.0)
        piece = self._piece()
        piece.write({'karat': False})
        with self.assertRaises(ValidationError):
            piece.get_price_breakdown()

    def test_the_displayed_price_is_zero_until_a_rate_is_approved(self):
        """The computed field must not invent a number (it swallows the error)."""
        piece = self._piece()
        self._draft_rate(self.user_manager_a)
        piece.invalidate_recordset()
        self.assertEqual(piece.jewellery_price, 0.0)
        self._approved_rate(rate=100.0)
        piece.invalidate_recordset()
        self.assertEqual(round(piece.jewellery_price, 2), 1130.50)
