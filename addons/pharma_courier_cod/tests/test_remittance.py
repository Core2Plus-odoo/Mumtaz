from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import CourierCase


@tagged("post_install", "-at_install", "pharma")
class TestCourierRemittance(CourierCase):

    # ------------------------------------------------------------------ arithmetic and constraints
    def test_totals_and_the_itemised_deductions(self):
        a, b = self._ship("T1", declared=1000), self._ship("T2", declared=2000)
        rem = self._remit("S1", [(a, 1000, {"deduction_freight": 100, "deduction_wht_income_tax": 20}),
                                 (b, 2000, {"deduction_cod_fee": 50, "deduction_wht_sales_tax": 30})], bank=2800, post=False)
        self.assertEqual((rem.line_count, rem.amount_gross, rem.amount_deductions, rem.amount_net),
                         (2, 3000.0, 200.0, 2800.0))
        self.assertEqual(rem.amount_bank_variance, 0.0)
        l1 = rem.line_ids[0]
        self.assertEqual((l1.amount_deductions, l1.amount_net), (120.0, 880.0))

    def test_bank_variance_is_signed(self):
        a = self._ship("T3")
        rem = self._remit("S2", [(a, 1000, {"deduction_freight": 100})], bank=850, post=False)
        self.assertEqual(rem.amount_bank_variance, -50.0)

    def test_deductions_cannot_exceed_the_gross(self):
        a = self._ship("T4")
        with self.assertRaises(ValidationError):
            self._remit("S3", [(a, 100, {"deduction_freight": 150})], post=False)

    def test_negative_amounts_are_refused(self):
        a = self._ship("T5")
        with self.assertRaises(ValidationError):
            self._remit("S4", [(a, 100, {"deduction_other": -5})], post=False)
        with self.assertRaises(ValidationError):
            self._remit("S5", [(a, -1, {})], post=False)

    def test_a_slip_reference_is_unique_per_courier(self):
        a, b = self._ship("T6"), self._ship("T7")
        self._remit("DUP", [(a, 1000, {})], post=False)
        with self.assertRaises(Exception), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self._remit("DUP", [(b, 1000, {})], post=False)
        self._remit("DUP", [(self._ship("T8", courier=self.courier2), 1000, {})], post=False, courier=self.courier2)

    def test_a_shipment_appears_once_per_remittance(self):
        a = self._ship("T9")
        with self.assertRaises(Exception), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self._remit("S6", [(a, 500, {}), (a, 500, {})], post=False)

    def test_a_remittance_takes_only_its_own_couriers_shipments(self):
        other = self._ship("T10", courier=self.courier2)
        with self.assertRaises(ValidationError):
            self._remit("S7", [(other, 1000, {})], post=False)

    # ------------------------------------------------------------------ workflow
    def test_posting_needs_lines_and_locks_them(self):
        a = self._ship("W1")
        empty = self.Rem.create({"courier_id": self.courier.id, "slip_ref": "EMPTY", "date": self.today})
        with self.assertRaises(UserError):
            empty.action_post()
        rem = self._remit("W-S1", [(a, 1000, {})])
        self.assertEqual((rem.state, rem.line_ids.state), ("posted", "posted"))
        with self.assertRaises(UserError):
            rem.action_post()
        with self.assertRaises(UserError):
            rem.line_ids.write({"amount_gross": 1})
        with self.assertRaises(UserError):
            rem.line_ids.unlink()
        with self.assertRaises(UserError):
            self.env["pharma.courier.remittance.line"].create(
                {"remittance_id": rem.id, "shipment_id": self._ship("W2").id, "amount_gross": 10})
        with self.assertRaises(UserError):
            rem.write({"slip_ref": "CHANGED"})
        with self.assertRaises(UserError):
            rem.unlink()

    def test_a_draft_can_be_deleted_and_a_cancelled_one_reopened(self):
        a = self._ship("W3")
        draft = self._remit("W-S2", [(a, 1000, {})], post=False)
        draft.unlink()
        self.assertFalse(self.Rem.search([("slip_ref", "=", "W-S2")]))
        rem = self._remit("W-S3", [(a, 1000, {})])
        rem.action_cancel()
        self.assertEqual(rem.state, "cancel")
        with self.assertRaises(UserError):
            rem.action_post()
        rem.action_draft()
        rem.action_post()
        self.assertEqual(a.cod_remitted, 1000.0)

    def test_names_come_from_a_sequence(self):
        a, b = self._ship("W4"), self._ship("W5")
        r1 = self._remit("W-S4", [(a, 1000, {})], post=False)
        r2 = self._remit("W-S5", [(b, 1000, {})], post=False)
        self.assertTrue(r1.name.startswith("PCR/") and r2.name.startswith("PCR/"))
        self.assertNotEqual(r1.name, r2.name)

    # ------------------------------------------------------------------ reconcile through the hub
    def _batch(self, bank, deductions=(100, 200), slip="K-S1", **kw):
        a, b = self._ship(f"{slip}-1", declared=1000), self._ship(f"{slip}-2", declared=2000)
        return self._remit(slip, [(a, 1000, {"deduction_freight": deductions[0]}),
                                  (b, 2000, {"deduction_freight": deductions[1]})], bank=bank, **kw)

    def test_a_clean_batch_matches_the_bank_through_the_hub(self):
        rem = self._batch(bank=2700)
        rem.with_user(self.fin).action_reconcile()
        run = rem.run_id
        self.assertEqual((run.run_type, run.state, run.authorized_deductions), ("cod", "matched", 300.0))
        self.assertEqual((rem.run_state, rem.open_exceptions), ("matched", 0))
        methods = run.item_ids.filtered(lambda i: i.side == "source").mapped("method")
        self.assertEqual(methods, ["one_to_many_batch"] * 2)
        self.assertEqual(run.name, "COD TCOD K-S1")

    def test_a_difference_at_the_bank_is_an_exception_never_forced_to_zero(self):
        rem = self._batch(bank=2600, slip="K-S2")
        rem.with_user(self.fin).action_reconcile()
        run = rem.run_id
        self.assertEqual((run.state, rem.open_exceptions), ("partial", 1))
        exc = run.exception_ids
        self.assertEqual(exc.amount, -100.0)
        self.assertIn("variance", exc.description)
        self.assertEqual(rem.amount_bank_variance, -100.0)

    def test_reconcile_preconditions(self):
        rem = self._batch(bank=2700, slip="K-S3")
        with self.assertRaises(UserError):
            rem.with_user(self.ops).action_reconcile()                     # not a Finance Controller
        draft = self._batch(bank=2700, slip="K-S4", post=False)
        with self.assertRaises(UserError):
            draft.with_user(self.fin).action_reconcile()                   # not posted
        no_bank = self._batch(bank=None, slip="K-S5")
        with self.assertRaises(UserError):
            no_bank.with_user(self.fin).action_reconcile()                 # no bank amount
        rem.with_user(self.fin).action_reconcile()
        with self.assertRaises(UserError):
            rem.with_user(self.fin).action_reconcile()                     # once only

    def test_a_reconciled_remittance_is_locked(self):
        rem = self._batch(bank=2700, slip="K-S6")
        rem.with_user(self.fin).action_reconcile()
        with self.assertRaises(UserError):
            rem.write({"bank_amount": 1})
        with self.assertRaises(UserError):
            rem.action_cancel()
        with self.assertRaises(UserError):
            rem.with_user(self.fin).action_reconcile()

    def test_shipment_level_findings_join_the_batch_run(self):
        short = self._ship("K-X1", declared=1000, collected=900)
        rem = self._remit("K-S7", [(short, 900, {})], bank=900)
        rem.with_user(self.fin).action_reconcile()
        exc = self._exc("TCOD/K-X1/collection")
        self.assertEqual(exc.run_id, rem.run_id)
        self.assertEqual(rem.run_id.state, "partial")                      # open exception, so not 'matched'

    def test_unauthorized_deductions_are_a_finding(self):
        rem = self._batch(bank=2700, slip="K-S8", check_deductions=True, deductions_authorized=250.0)
        self.assertEqual(rem.deductions_excess, 50.0)
        rem.with_user(self.fin).action_reconcile()
        exc = self._exc("TCOD/K-S8/deduction")
        self.assertEqual((exc.category, exc.amount), ("deduction", 50.0))
        self.assertEqual(exc.run_id, rem.run_id)

    def test_deductions_are_not_checked_unless_asked(self):
        rem = self._batch(bank=2700, slip="K-S9", deductions_authorized=1.0)
        rem.with_user(self.fin).action_reconcile()
        self.assertFalse(self._exc("TCOD/K-S9/deduction"))
        self.assertEqual(rem.deductions_excess, 0.0)

    def test_a_tolerance_covers_a_small_excess_in_deductions(self):
        self.courier.variance_tolerance = 100.0
        rem = self._batch(bank=2700, slip="K-S10", check_deductions=True, deductions_authorized=250.0)
        rem.with_user(self.fin).action_reconcile()
        self.assertFalse(self._exc("TCOD/K-S10/deduction"))

    def test_the_run_is_visible_from_the_remittance(self):
        rem = self._batch(bank=2700, slip="K-S11")
        with self.assertRaises(UserError):
            rem.action_view_run()
        rem.with_user(self.fin).action_reconcile()
        self.assertEqual(rem.action_view_run()["res_id"], rem.run_id.id)
