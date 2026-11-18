from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import AccountingCase


@tagged("post_install", "-at_install", "pharma")
class TestCourierEntry(AccountingCase):

    # ---------------------------------------------------------------- helpers
    def _reconciled(self, slip, rows, bank):
        rem = self._remit(slip, rows, bank=bank)
        rem.with_user(self.fin).action_reconcile()
        return rem

    def _standard(self, slip="E1", bank=870.0):
        s = self._ship(f"{slip}-1", declared=1000)
        return self._reconciled(slip, [(s, 1000, {"deduction_freight": 100, "deduction_cod_fee": 20,
                                                  "deduction_wht_sales_tax": 10})], bank)

    # ---------------------------------------------------------------- the entry
    def test_a_reconciled_remittance_makes_a_balanced_draft_entry(self):
        rem = self._standard()
        rem.with_user(self.fin).action_create_entry()
        move = rem.move_id
        self.assertEqual((move.move_type, move.state, move.journal_id, move.date), ("entry", "draft", self.journal, rem.date))
        self.assertEqual(move.ref, "COD TCOD E1")
        self.assertEqual(self._by_account(move), {
            "CODT01": (0.0, 1000.0),      # clearing cleared by the gross the courier remitted
            "CODT02": (870.0, 0.0),       # what reached the bank
            "CODT03": (100.0, 0.0), "CODT04": (20.0, 0.0), "CODT06": (10.0, 0.0)})
        self.assertEqual(sum(move.line_ids.mapped("debit")), sum(move.line_ids.mapped("credit")))
        self.assertEqual((rem.move_state, rem.move_ref), ("draft", move.name))
        self.assertTrue(rem.message_ids.filtered(lambda m: "Draft journal entry" in (m.body or "")))

    def test_nothing_is_posted_by_the_module(self):
        rem = self._standard("E2")
        rem.with_user(self.fin).action_create_entry()
        self.assertEqual(rem.move_id.state, "draft")

    def test_every_deduction_goes_to_its_own_account(self):
        s = self._ship("E3-1", declared=5000)
        rem = self._reconciled("E3", [(s, 5000, {
            "deduction_freight": 100, "deduction_cod_fee": 50, "deduction_wht_income_tax": 40,
            "deduction_wht_sales_tax": 30, "deduction_other": 25})], 4755)
        rem.with_user(self.fin).action_create_entry()
        self.assertEqual(self._by_account(rem.move_id), {
            "CODT01": (0.0, 5000.0), "CODT02": (4755.0, 0.0), "CODT03": (100.0, 0.0), "CODT04": (50.0, 0.0),
            "CODT05": (40.0, 0.0), "CODT06": (30.0, 0.0), "CODT07": (25.0, 0.0)})

    def test_a_bank_shortfall_is_booked_to_the_difference_account(self):
        rem = self._standard("E4", bank=800.0)                      # slip net is 870, only 800 arrived
        rem.with_user(self.fin).action_create_entry()
        got = self._by_account(rem.move_id)
        self.assertEqual((got["CODT02"], got["CODT08"]), ((800.0, 0.0), (70.0, 0.0)))
        self.assertEqual(sum(rem.move_id.line_ids.mapped("debit")), sum(rem.move_id.line_ids.mapped("credit")))

    def test_a_bank_surplus_is_a_credit_on_the_difference_account(self):
        rem = self._standard("E5", bank=900.0)
        rem.with_user(self.fin).action_create_entry()
        self.assertEqual(self._by_account(rem.move_id)["CODT08"], (0.0, 30.0))

    def test_zero_amounts_make_no_lines(self):
        s = self._ship("E6-1", declared=1000)
        rem = self._reconciled("E6", [(s, 1000, {})], 1000)
        rem.with_user(self.fin).action_create_entry()
        self.assertEqual(sorted(self._by_account(rem.move_id)), ["CODT01", "CODT02"])

    def test_the_courier_partner_is_on_the_lines(self):
        self.courier.partner_id = self.partner
        rem = self._standard("E7")
        rem.with_user(self.fin).action_create_entry()
        self.assertEqual(rem.move_id.line_ids.mapped("partner_id"), self.partner)

    # ---------------------------------------------------------------- guards
    def test_only_a_finance_controller_can_create_it(self):
        rem = self._standard("G1")
        with self.assertRaises(UserError):
            rem.with_user(self.ops).action_create_entry()
        self.assertFalse(rem.move_id)

    def test_a_finance_controller_does_not_need_accounting_rights(self):
        self.assertFalse(self.fin.has_group("account.group_account_invoice"))
        rem = self._standard("G2")
        rem.with_user(self.fin).action_create_entry()
        self.assertTrue(rem.move_id)
        self.assertEqual(rem.move_id.create_uid, self.fin)            # the entry records who made it
        self.assertEqual(rem.with_user(self.fin).move_state, "draft")  # and Finance can see its status

    def test_it_needs_a_posted_and_reconciled_remittance(self):
        s = self._ship("G3-1", declared=1000)
        draft = self._remit("G3", [(s, 1000, {})], bank=1000, post=False)
        with self.assertRaises(UserError):
            draft.with_user(self.fin).action_create_entry()
        posted = self._remit("G3B", [(self._ship("G3B-1", declared=1000), 1000, {})], bank=1000)
        with self.assertRaises(UserError):
            posted.with_user(self.fin).action_create_entry()           # not reconciled yet

    def test_it_needs_a_bank_amount(self):
        s = self._ship("G4-1", declared=1000)
        rem = self._remit("G4", [(s, 1000, {})], bank=0.0)
        with self.assertRaises(UserError):
            rem.with_user(self.fin).action_reconcile()                 # reconcile itself needs a bank amount
        self.assertFalse(rem.run_id)

    def test_a_second_entry_is_refused_until_the_first_is_cancelled(self):
        rem = self._standard("G5")
        rem.with_user(self.fin).action_create_entry()
        first = rem.move_id
        with self.assertRaises(UserError):
            rem.with_user(self.fin).action_create_entry()
        first.button_cancel()
        rem.with_user(self.fin).action_create_entry()
        self.assertNotEqual(rem.move_id, first)

    def test_deleting_the_draft_entry_frees_the_remittance(self):
        rem = self._standard("G6")
        rem.with_user(self.fin).action_create_entry()
        rem.move_id.unlink()
        self.assertFalse(rem.move_id)
        rem.with_user(self.fin).action_create_entry()
        self.assertTrue(rem.move_id)

    def test_a_copy_does_not_carry_the_entry(self):
        self.assertFalse(self.env["pharma.courier.remittance"]._fields["move_id"].copy)

    # ---------------------------------------------------------------- configuration
    def test_missing_configuration_is_named_and_nothing_is_written(self):
        self.courier2.write({"acc_journal_id": self.journal.id})
        s = self._ship("C1-1", declared=1000, courier=self.courier2)
        rem = self._reconciled_other("C1", s)
        before = self.env["account.move"].search_count([])
        with self.assertRaises(UserError) as cm:
            rem.with_user(self.fin).action_create_entry()
        msg = str(cm.exception)
        for label in ("COD clearing account", "Bank / receipts account", "Freight account", "Difference account"):
            self.assertIn(label, msg)
        self.assertNotIn("Journal", msg.replace("Journal Entry", ""))   # the journal IS set
        self.assertEqual(self.env["account.move"].search_count([]), before)
        self.assertFalse(rem.move_id)

    def _reconciled_other(self, slip, shipment):
        rem = self._remit(slip, [(shipment, 1000, {"deduction_freight": 100})], bank=850, courier=self.courier2)
        rem.with_user(self.fin).action_reconcile()
        return rem

    def test_only_accounts_a_slip_uses_are_required(self):
        """A slip with no withholding does not need the withholding accounts, nor a difference account when the bank agrees."""
        self.courier2.write({"acc_journal_id": self.journal.id, "acc_clearing_account_id": self.acc["acc_clearing_account_id"].id,
                             "acc_bank_account_id": self.acc["acc_bank_account_id"].id,
                             "acc_freight_account_id": self.acc["acc_freight_account_id"].id})
        s = self._ship("C2-1", declared=1000, courier=self.courier2)
        rem = self._remit("C2", [(s, 1000, {"deduction_freight": 100})], bank=900, courier=self.courier2)
        rem.with_user(self.fin).action_reconcile()
        rem.with_user(self.fin).action_create_entry()
        self.assertEqual(self._by_account(rem.move_id), {"CODT01": (0.0, 1000.0), "CODT02": (900.0, 0.0), "CODT03": (100.0, 0.0)})

    def test_every_account_the_entry_can_use_is_configurable_on_the_courier(self):
        from odoo.addons.pharma_courier_cod_accounting.models.courier import ACCOUNT_FIELDS
        fields = self.env["pharma.courier"].fields_get()
        for fname in ACCOUNT_FIELDS:
            self.assertIn(fname, fields)
        self.assertEqual(len(ACCOUNT_FIELDS), 9)
