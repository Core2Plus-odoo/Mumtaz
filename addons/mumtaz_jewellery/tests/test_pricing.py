"""Unit tests for the pricing engine. Run with pytest or inside Odoo.

The engine is loaded by file path so these tests run without Odoo installed.
"""
import importlib.util
import os
import unittest
from decimal import Decimal

_PATH = os.path.join(
    os.path.dirname(__file__), "..", "services", "pricing.py")
_SPEC = importlib.util.spec_from_file_location("jewellery_pricing", _PATH)
pricing = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pricing)

D = Decimal


class TestUnits(unittest.TestCase):
    def test_tola_to_grams(self):
        self.assertEqual(pricing.to_grams(1, "tola"), D("11.6638038"))

    def test_rate_per_tola(self):
        self.assertEqual(pricing.rate_per_unit(100, "tola"), D("1166.38"))

    def test_unknown_unit(self):
        with self.assertRaises(ValueError):
            pricing.to_grams(1, "pound")


class TestPurity(unittest.TestCase):
    def test_karat(self):
        self.assertEqual(pricing.purity(karat=24), D(1))
        self.assertEqual(pricing.purity(karat=12), D("0.5"))

    def test_fineness_wins(self):
        self.assertEqual(pricing.purity(karat=22, fineness=916), D("0.916"))

    def test_invalid(self):
        for kwargs in ({"karat": 0}, {"karat": 25}, {"fineness": 1001}, {}):
            with self.assertRaises(ValueError):
                pricing.purity(**kwargs)


class TestPricePiece(unittest.TestCase):
    base = dict(net_weight_g=10, karat=22, rate_24k_per_g=100)

    def test_percent_making_vat(self):
        out = pricing.price_piece(
            **self.base, wastage_pct=2, making_type="percent",
            making_value=10, stones_value=50, vat_rate=5)
        # metal = 10 * 22/24 * 100 = 916.67
        self.assertEqual(out["metal_value"], D("916.67"))
        self.assertEqual(out["wastage_value"], D("18.33"))
        self.assertEqual(out["making_charge"], D("91.67"))
        self.assertEqual(out["subtotal"], D("1076.67"))
        self.assertEqual(out["vat"], D("53.83"))
        self.assertEqual(out["total"], D("1130.50"))

    def test_breakdown_adds_up(self):
        out = pricing.price_piece(
            net_weight_g="7.333", karat=18, rate_24k_per_g="287.45",
            wastage_pct="1.5", making_type="per_gram", making_value="12.5",
            stones_value="210.10", vat_rate=5)
        self.assertEqual(
            out["subtotal"],
            out["metal_value"] + out["wastage_value"]
            + out["making_charge"] + out["stones_value"])
        self.assertEqual(out["total"], out["subtotal"] + out["vat"])

    def test_fixed_making(self):
        out = pricing.price_piece(
            **self.base, making_type="fixed", making_value=75)
        self.assertEqual(out["making_charge"], D("75.00"))

    def test_trade_discount_hits_making_only(self):
        retail = pricing.price_piece(
            **self.base, making_type="percent", making_value=10)
        trade = pricing.price_piece(
            **self.base, making_type="percent", making_value=10,
            making_discount_pct=50)
        self.assertEqual(trade["metal_value"], retail["metal_value"])
        self.assertEqual(trade["making_charge"], D("45.83"))

    def test_fineness_override(self):
        out = pricing.price_piece(
            net_weight_g=10, fineness=916, rate_24k_per_g=100)
        self.assertEqual(out["metal_value"], D("916.00"))

    def test_zero_weight(self):
        out = pricing.price_piece(
            net_weight_g=0, karat=22, rate_24k_per_g=100)
        self.assertEqual(out["total"], D("0.00"))

    def test_rejects_bad_input(self):
        bad = (
            dict(net_weight_g=-1),
            dict(rate_24k_per_g=-1),
            dict(making_type="weird"),
            dict(making_discount_pct=101),
            dict(vat_rate=-5),
        )
        for override in bad:
            with self.assertRaises(ValueError):
                pricing.price_piece(**{**self.base, **override})


class TestOldGold(unittest.TestCase):
    def test_value(self):
        out = pricing.old_gold_value(
            gross_weight_g=10, karat=22, melt_loss_pct=2,
            rate_24k_per_g=100, buyback_discount_pct=3)
        # fine = 10 * 22/24 = 9.1667; after 2% loss = 8.9833
        self.assertEqual(out["fine_weight_g"], D("8.9833"))
        self.assertEqual(out["applied_rate_per_g"], D("97.0000"))
        self.assertEqual(out["value"], D("871.38"))

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            pricing.old_gold_value(
                gross_weight_g=10, karat=22, melt_loss_pct=100,
                rate_24k_per_g=100)
