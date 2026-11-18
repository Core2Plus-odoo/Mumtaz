from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import AccountingCase


@tagged("post_install", "-at_install", "pharma")
class TestEntryReversal(AccountingCase):
    """DEMO / fictional data only. A Finance Controller asks for a posted COD entry to be withdrawn; Odoo's own reversal
    is created as a DRAFT; an accountant posts it; only then can a corrected entry be created."""

    # ---------------------------------------------------------------- helpers
    def _settlement(self, slip="V1", bank=870.0):
        s = self._ship(f"{slip}-1", declared=1000)
        rem = self._remit(slip, [(s, 1000, {"deduction_freight": 100, "deduction_cod_fee": 20,
                                            "deduction_wht_sales_tax": 10})], bank=bank)
        rem.with_user(self.fin).action_reconcile()
        rem.with_user(self.fin).action_create_entry()
        rem.move_id.sudo().action_post()
        return rem

    def _collection(self, trk="C1"):
        s = self._ship(trk, declared=1000)
        s.with_user(self.fin).action_create_collection_entry()
        s.collection_move_id.sudo().action_post()
        return s

    def _reverse(self, rec, reason="posted to the wrong courier"):
        return rec.with_user(self.fin)._reverse_entry(reason, False)

    # ---------------------------------------------------------------- the reversal
    def test_a_posted_settlement_is_reversed_into_a_draft_that_mirrors_it(self):
        rem = self._settlement()
        original = self._by_account(rem.move_id)
        reversal = self._reverse(rem)
        self.assertEqual((reversal.state, reversal.reversed_entry_id), ("draft", rem.move_id))
        self.assertEqual(self._by_account(reversal), {k: (c, d) for k, (d, c) in original.items()})
        self.assertIn("posted to the wrong courier", reversal.ref)
        self.assertEqual(rem.move_reversal_state, "draft")
        self.assertTrue(rem.message_ids.filtered(lambda m: "posted to the wrong courier" in (m.body or "")))

    def test_the_original_still_stands_until_the_reversal_is_posted(self):
        rem = self._settlement("V2")
        self._reverse(rem)
        self.assertTrue(rem.move_open)
        with self.assertRaises(UserError) as cm:
            rem.with_user(self.fin).action_create_entry()
        self.assertIn("already has journal entry", str(cm.exception))

    def test_once_the_reversal_is_posted_a_corrected_entry_can_be_created(self):
        rem = self._settlement("V3")
        old = rem.move_id
        self._reverse(rem).sudo().action_post()
        self.assertEqual((rem.move_reversal_state, rem.move_open), ("posted", False))
        rem.with_user(self.fin).action_create_entry()
        self.assertNotEqual(rem.move_id, old)
        self.assertEqual(rem.move_id.state, "draft")
        self.assertEqual(rem.sudo().previous_move_ids, old)

    def test_the_module_never_posts_the_reversal(self):
        rem = self._settlement("V4")
        self.assertEqual(self._reverse(rem).state, "draft")

    # ---------------------------------------------------------------- guards
    def test_a_reason_is_required(self):
        rem = self._settlement("V5")
        for blank in ("", "   ", None):
            with self.assertRaises(UserError):
                rem.with_user(self.fin)._reverse_entry(blank, False)
        self.assertFalse(rem.move_id.reversal_move_ids)

    def test_only_a_finance_controller_can_reverse(self):
        rem = self._settlement("V6")
        for user in (self.ops, self.adm):
            with self.assertRaises(UserError) as cm:
                rem.with_user(user)._reverse_entry("why", False)
            self.assertIn("Only a Finance Controller", str(cm.exception))
        self.assertFalse(rem.move_id.reversal_move_ids)

    def test_a_draft_entry_is_cancelled_not_reversed(self):
        s = self._ship("V7-1", declared=1000)
        rem = self._remit("V7", [(s, 1000, {"deduction_freight": 100})], bank=900)
        rem.with_user(self.fin).action_reconcile()
        rem.with_user(self.fin).action_create_entry()
        with self.assertRaises(UserError) as cm:
            self._reverse(rem)
        self.assertIn("cancel it in Accounting", str(cm.exception))

    def test_nothing_to_reverse_when_there_is_no_entry(self):
        s = self._ship("V8")
        with self.assertRaises(UserError) as cm:
            self._reverse(s)
        self.assertIn("no entry to reverse", str(cm.exception))

    def test_a_second_reversal_is_refused_while_one_stands(self):
        rem = self._settlement("V9")
        self._reverse(rem)
        with self.assertRaises(UserError) as cm:
            self._reverse(rem, "again")
        self.assertIn("already has a reversal", str(cm.exception))
        self.assertEqual(len(rem.move_id.reversal_move_ids), 1)

    def test_a_cancelled_reversal_can_be_asked_for_again(self):
        rem = self._settlement("V10")
        self._reverse(rem).sudo().button_cancel()
        self.assertFalse(rem.move_reversal_state)
        self.assertTrue(rem.move_open)
        self.assertEqual(self._reverse(rem, "second try").state, "draft")

    # ---------------------------------------------------------------- the collection entry follows the same path
    def test_a_posted_collection_entry_is_reversed_and_then_corrected(self):
        s = self._collection("C2")
        old = s.collection_move_id
        reversal = self._reverse(s, "wrong customer")
        self.assertEqual(self._by_account(reversal), {"CODT01": (0.0, 1000.0), self.receivable.code: (1000.0, 0.0)})
        self.assertEqual(s.collection_reversal_state, "draft")
        with self.assertRaises(UserError):
            s.with_user(self.fin).action_create_collection_entry()
        reversal.sudo().action_post()
        s.with_user(self.fin).action_create_collection_entry()
        self.assertEqual((s.collection_move_id.state, s.sudo().previous_move_ids), ("draft", old))

    def test_reversing_does_not_undo_a_reconciliation(self):
        """The reversal is a draft and must leave the customer's reconciliation alone: that is the accountant's call."""
        s = self._collection("C3")
        credit = s.collection_move_id.line_ids.filtered(lambda l: l.account_id == self.receivable)
        invoice_like = self.env["account.move"].create({
            "move_type": "entry", "journal_id": self.journal.id, "date": s.collection_move_id.date,
            "line_ids": [(0, 0, {"account_id": self.receivable.id, "partner_id": self.partner.id, "debit": 1000.0,
                                 "credit": 0.0, "name": "TEST sale"}),
                         (0, 0, {"account_id": self.acc["acc_other_account_id"].id, "debit": 0.0, "credit": 1000.0,
                                 "name": "TEST income"})]})
        invoice_like.action_post()
        (credit | invoice_like.line_ids.filtered(lambda l: l.account_id == self.receivable)).reconcile()
        self.assertTrue(credit.reconciled)
        reversal = self._reverse(s, "check")
        self.assertEqual(reversal.state, "draft")
        self.assertTrue(credit.reconciled)

    # ---------------------------------------------------------------- the wizard
    def test_the_wizard_creates_the_draft_reversal(self):
        rem = self._settlement("V11")
        action = rem.with_user(self.fin).action_open_reverse_wizard()
        self.assertEqual((action["res_model"], action["target"]), ("pharma.courier.entry.reverse", "new"))
        wiz = self.env["pharma.courier.entry.reverse"].with_user(self.fin).with_context(**action["context"]).create(
            {"reason": "wizard test", "res_model": rem._name, "res_id": rem.id})
        wiz.action_confirm()
        self.assertEqual(rem.move_reversal_state, "draft")

    def test_the_wizard_only_works_on_cod_records(self):
        wiz = self.env["pharma.courier.entry.reverse"].with_user(self.fin).create(
            {"reason": "x", "res_model": "res.partner", "res_id": self.partner.id})
        with self.assertRaises(UserError):
            wiz.action_confirm()
