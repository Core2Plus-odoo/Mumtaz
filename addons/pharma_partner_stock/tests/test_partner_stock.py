from datetime import datetime, date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "pharma")
class TestPartnerStockFromMoves(TransactionCase):
    """DEMO/fictional data only. One month of real stock moves in and out of a partner location."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("pharma.mode", "demo")
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        base = cls.env.ref("base.group_user").id
        cls.finance = Users.create({"name": "PS Finance", "login": "ps_finance", "group_ids": [
            (6, 0, [base, cls.env.ref("pharma_core.group_pharma_finance").id])]})
        cls.plain = Users.create({"name": "PS Plain", "login": "ps_plain", "group_ids": [
            (6, 0, [base, cls.env.ref("pharma_core.group_pharma_user").id])]})
        Loc = cls.env["stock.location"]
        cls.wh = cls.env.ref("stock.stock_location_stock")
        cls.customers = cls.env.ref("stock.stock_location_customers")
        cls.partner_loc = Loc.create({"name": "DEMO-PARTNER-WH1", "usage": "internal"})
        cls.shelf = Loc.create({"name": "Shelf", "usage": "internal", "location_id": cls.partner_loc.id})
        cls.loss = Loc.create({"name": "DEMO Inventory Loss", "usage": "inventory"})
        cls.scrap_loc = Loc.create({"name": "DEMO Scrap", "usage": "inventory"})
        cls.product = cls.env["product.product"].create({
            "name": "DEMO Lot SKU", "default_code": "DEMO-SKU-X", "is_storable": True, "tracking": "lot"})
        Lot = cls.env["stock.lot"]
        cls.l1 = Lot.create({"name": "DEMO-LOT-L1", "product_id": cls.product.id})
        cls.l2 = Lot.create({"name": "DEMO-LOT-L2", "product_id": cls.product.id})
        # opening position (October): 50 of L1 and 8 of L2 reach the partner
        cls._move(cls.wh, cls.partner_loc, 50, cls.l1, datetime(2026, 10, 15, 9))
        cls._move(cls.wh, cls.partner_loc, 8, cls.l2, datetime(2026, 10, 16, 9))
        # the period: November
        cls._move(cls.wh, cls.partner_loc, 20, cls.l1, datetime(2026, 11, 2, 9))              # inward
        cls._move(cls.partner_loc, cls.customers, 15, cls.l1, datetime(2026, 11, 10, 9))      # sold / issued
        cls._move(cls.partner_loc, cls.wh, 5, cls.l1, datetime(2026, 11, 12, 9))              # returned to Pharma
        cls._move(cls.partner_loc, cls.shelf, 10, cls.l1, datetime(2026, 11, 5, 9))           # inside the location: ignored
        cls._scrap(3, cls.l1, datetime(2026, 11, 15, 9))                                      # documented scrap
        cls._move(cls.loss, cls.partner_loc, 4, cls.l1, datetime(2026, 11, 20, 9))            # inventory adjustment: not derived
        cls._move(cls.partner_loc, cls.customers, 2, cls.l1, datetime(2026, 12, 5, 9))        # after the period: ignored
        cls.recon = cls.env["pharma.recon.run"].with_user(cls.finance).create({
            "name": "DEMO R07 from stock moves", "run_type": "partner_stock", "period": "2026-11",
            "partner_location_id": cls.partner_loc.id, "date_from": date(2026, 11, 1), "date_to": date(2026, 11, 30)})

    @classmethod
    def _move(cls, src, dest, qty, lot, when):
        if src.usage == "internal":
            cls.env["stock.quant"]._update_available_quantity(cls.product, src, qty, lot_id=lot)
        move = cls.env["stock.move"].create({
            "product_id": cls.product.id, "product_uom_qty": qty, "product_uom": cls.product.uom_id.id,
            "location_id": src.id, "location_dest_id": dest.id})
        move._action_confirm()
        move._action_assign()
        if not move.move_line_ids:
            move.move_line_ids = [(0, 0, {"product_id": cls.product.id, "location_id": src.id,
                                          "location_dest_id": dest.id, "quantity": qty})]
        move.move_line_ids.write({"lot_id": lot.id, "quantity": qty})
        move.picked = True
        move._action_done()
        move.move_line_ids.write({"date": when})
        return move

    @classmethod
    def _scrap(cls, qty, lot, when):
        cls.env["stock.quant"]._update_available_quantity(cls.product, cls.partner_loc, qty, lot_id=lot)
        scrap = cls.env["stock.scrap"].create({
            "product_id": cls.product.id, "scrap_qty": qty, "lot_id": lot.id,
            "location_id": cls.partner_loc.id, "scrap_location_id": cls.scrap_loc.id})
        scrap.action_validate()
        scrap.move_ids.move_line_ids.write({"date": when})

    def _lines(self):
        return {l.lot: l for l in self.recon.stock_line_ids}

    # ---- derivation
    def test_roll_forward_is_derived_from_stock_moves(self):
        self.recon.with_user(self.finance).action_compute_stock_from_moves()
        lines = self._lines()
        self.assertEqual(set(lines), {"DEMO-LOT-L1", "DEMO-LOT-L2"})
        l1 = lines["DEMO-LOT-L1"]
        self.assertEqual((l1.opening, l1.inward_accepted, l1.sold_or_issued, l1.returned_to_pharma,
                          l1.expired_damaged_documented), (50, 20, 15, 5, 3))
        self.assertEqual(l1.sku, "DEMO-SKU-X")
        self.assertEqual(l1.expected_closing, 47)
        self.assertTrue(l1.from_stock_moves)
        l2 = lines["DEMO-LOT-L2"]
        self.assertEqual((l2.opening, l2.inward_accepted, l2.expected_closing), (8, 0, 8))

    def test_moves_inside_the_partner_location_and_outside_the_period_are_ignored(self):
        self.recon.with_user(self.finance).action_compute_stock_from_moves()
        l1 = self._lines()["DEMO-LOT-L1"]
        self.assertEqual(l1.opening, 50)               # not 60: the shelf move is internal
        self.assertEqual(l1.sold_or_issued, 15)        # not 17: the December sale is outside the period

    def test_inventory_adjustment_is_not_added_silently_it_becomes_variance(self):
        self.recon.with_user(self.finance).action_compute_stock_from_moves()
        l1 = self._lines()["DEMO-LOT-L1"]
        l1.write({"reported": 51})                     # the partner physically holds 4 more than the moves explain
        self.assertEqual(l1.variance, 4)
        l1.with_user(self.finance).action_raise_exceptions()
        exc = self.recon.exception_ids
        self.assertEqual(len(exc), 1)
        self.assertEqual(exc.amount, 4)
        self.assertEqual(exc.state, "open")            # nothing written off

    def test_recompute_is_idempotent_and_keeps_reported_and_approved_adjustments(self):
        self.recon.with_user(self.finance).action_compute_stock_from_moves()
        l1 = self._lines()["DEMO-LOT-L1"]
        l1.write({"reported": 51, "adj_positive_approved": 4})
        self.recon.with_user(self.finance).action_compute_stock_from_moves()
        self.assertEqual(len(self.recon.stock_line_ids), 2)
        l1 = self._lines()["DEMO-LOT-L1"]
        self.assertEqual((l1.reported, l1.adj_positive_approved, l1.expected_closing, l1.variance), (51, 4, 51, 0))

    # ---- guards
    def test_only_finance_can_compute(self):
        with self.assertRaises(UserError):
            self.recon.with_user(self.plain).action_compute_stock_from_moves()

    def test_needs_location_and_period_and_the_right_run_type(self):
        Run = self.env["pharma.recon.run"].with_user(self.finance)
        with self.assertRaises(UserError):
            Run.create({"name": "no location", "run_type": "partner_stock"}).action_compute_stock_from_moves()
        with self.assertRaises(UserError):
            Run.create({"name": "wrong type", "run_type": "cod", "partner_location_id": self.partner_loc.id,
                        "date_from": date(2026, 11, 1), "date_to": date(2026, 11, 30)}).action_compute_stock_from_moves()
        with self.assertRaises(UserError):
            Run.create({"name": "reversed", "run_type": "partner_stock", "partner_location_id": self.partner_loc.id,
                        "date_from": date(2026, 11, 30), "date_to": date(2026, 11, 1)}).action_compute_stock_from_moves()

    def test_fractional_quantity_is_refused_not_rounded(self):
        self._move(self.wh, self.partner_loc, 2.5, self.l2, datetime(2026, 11, 8, 9))
        with self.assertRaises(UserError) as cm:
            self.recon.with_user(self.finance).action_compute_stock_from_moves()
        self.assertIn("Fractional quantity", str(cm.exception))
