from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import AccountingCase


@tagged("post_install", "-at_install", "pharma")
class TestCollectionEntry(AccountingCase):

    def _collect(self, trk, declared=1000.0, **kw):
        return self._ship(trk, declared=declared, **kw)

    def _create(self, shipments):
        return shipments.with_user(self.fin).action_create_collection_entry()

    # ---------------------------------------------------------------- the entry
    def test_a_collected_parcel_makes_a_balanced_draft_entry(self):
        s = self._collect("K1", days_ago=3)
        result = self._create(s)
        move = s.collection_move_id
        self.assertEqual((move.move_type, move.state, move.journal_id, move.date), ("entry", "draft", self.journal, s.date_delivered))
        self.assertEqual(move.ref, "COD collected TCOD K1")
        self.assertEqual(self._by_account(move), {"CODT01": (1000.0, 0.0), self.receivable.code: (0.0, 1000.0)})
        self.assertEqual(sum(move.line_ids.mapped("debit")), sum(move.line_ids.mapped("credit")))
        self.assertEqual((s.collection_move_state, s.collection_move_ref), ("draft", move.name))
        self.assertEqual(result["tag"], "display_notification")
        self.assertTrue(s.message_ids.filtered(lambda m: "collection entry" in (m.body or "")))

    def test_the_customer_is_on_the_receivable_line_so_it_can_be_reconciled(self):
        s = self._collect("K2")
        self._create(s)
        line = s.collection_move_id.line_ids.filtered(lambda l: l.account_id == self.receivable)
        self.assertEqual((line.partner_id, line.credit), (self.partner, 1000.0))

    def test_the_amount_is_what_the_courier_collected_not_what_was_declared(self):
        s = self._collect("K3", declared=1000.0, collected=900.0)
        self._create(s)
        self.assertEqual(self._by_account(s.collection_move_id)["CODT01"], (900.0, 0.0))

    def test_nothing_is_posted_by_the_module(self):
        s = self._collect("K4")
        self._create(s)
        self.assertEqual(s.collection_move_id.state, "draft")

    def test_collection_and_settlement_net_the_clearing_account_to_zero(self):
        """The point of the pair: what the courier collected is debited, what it remits is credited."""
        s = self._collect("K5")
        rem = self._remit("K5S", [(s, 1000, {"deduction_freight": 100})], bank=900)
        rem.with_user(self.fin).action_reconcile()
        self._create(s)
        rem.with_user(self.fin).action_create_entry()
        clearing = (s.collection_move_id | rem.move_id).line_ids.filtered(lambda l: l.account_id.code == "CODT01")
        self.assertEqual(sum(clearing.mapped("debit")) - sum(clearing.mapped("credit")), 0.0)

    # ---------------------------------------------------------------- guards
    def test_only_a_finance_controller_can_create_it(self):
        s = self._collect("G1")
        with self.assertRaises(UserError):
            s.with_user(self.ops).action_create_collection_entry()
        self.assertFalse(s.collection_move_id)

    def test_a_finance_controller_does_not_need_accounting_rights(self):
        self.assertFalse(self.fin.has_group("account.group_account_invoice"))
        s = self._collect("G2")
        self._create(s)
        self.assertEqual(s.collection_move_id.create_uid, self.fin)
        self.assertEqual(s.with_user(self.fin).collection_move_state, "draft")

    def test_each_reason_for_refusal_is_named(self):
        cases = {
            "prepaid": (self._collect("R1", declared=0.0, mode="prepaid"), "not a COD shipment"),
            "transit": (self._collect("R2", state="in_transit", days_ago=None), "not delivered"),
            "none": (self._collect("R3", collected=0.0), "no COD collected"),
            "returned": (self._collect("R4", state="returned"), "not delivered"),
            "noorder": (self._collect("R5", with_order=False), "no matching sale order"),
        }
        for key, (s, why) in cases.items():
            with self.assertRaises(UserError, msg=key) as cm:
                self._create(s)
            self.assertIn(why, str(cm.exception), key)
            self.assertFalse(s.collection_move_id, key)

    def test_a_second_entry_is_refused_until_the_first_is_cancelled_or_deleted(self):
        s = self._collect("G3")
        self._create(s)
        with self.assertRaises(UserError) as cm:
            self._create(s)
        self.assertIn("already has collection entry", str(cm.exception))
        first = s.collection_move_id
        first.button_cancel()
        self._create(s)
        self.assertNotEqual(s.collection_move_id, first)
        s.collection_move_id.unlink()
        self.assertFalse(s.collection_move_id)
        self._create(s)
        self.assertTrue(s.collection_move_id)

    def test_a_batch_is_all_or_nothing(self):
        good1, good2 = self._collect("B1"), self._collect("B2")
        bad = self._collect("B3", state="in_transit", days_ago=None)
        before = self.env["account.move"].search_count([])
        with self.assertRaises(UserError) as cm:
            self._create(good1 | good2 | bad)
        self.assertIn("B3 is not delivered", str(cm.exception))
        self.assertEqual(self.env["account.move"].search_count([]), before)
        self.assertFalse((good1 | good2).collection_move_id)
        result = self._create(good1 | good2)
        self.assertEqual(self.env["account.move"].search_count([]), before + 2)
        self.assertIn("2 draft", result["params"]["message"])

    def test_missing_configuration_is_named_and_nothing_is_written(self):
        s = self._collect("C1", courier=self.courier2)
        before = self.env["account.move"].search_count([])
        with self.assertRaises(UserError) as cm:
            self._create(s)
        self.assertIn("COD clearing account", str(cm.exception))
        self.assertEqual(self.env["account.move"].search_count([]), before)

    def test_a_copy_does_not_carry_the_entry(self):
        self.assertFalse(self.env["pharma.courier.shipment"]._fields["collection_move_id"].copy)
