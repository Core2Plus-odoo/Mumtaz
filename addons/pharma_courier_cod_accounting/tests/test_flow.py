import ast

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import AccountingCase


@tagged("post_install", "-at_install", "pharma")
class TestAccountingFlow(AccountingCase):
    """The accounting steps on the COD path, the strict order, and the accountant's queue."""

    def _at(self, rec):
        return (rec.flow_stage, rec.flow_next, rec.flow_owner) if rec._name.endswith("shipment") else \
            (rec.flow_next, rec.flow_owner)

    def _set_mode(self, mode):
        self.env["ir.config_parameter"].sudo().set_param("pharma.cod_flow_mode", mode)

    def _post(self, move):
        move.sudo().action_post()

    def _collected(self, trk, **kw):
        """A parcel with a POSTED collection entry."""
        s = self._ship(trk, **kw)
        s.with_user(self.fin).action_create_collection_entry()
        self._post(s.collection_move_id)
        return s

    # ------------------------------------------------------------------ the path
    def test_the_collection_entry_is_a_step_with_an_owner_at_each_stage(self):
        s = self._ship("A1", days_ago=3)
        self.assertEqual(self._at(s), ("collected", "collect_entry", "finance"))
        s.with_user(self.fin).action_create_collection_entry()
        self.assertEqual(self._at(s), ("collected", "post_collection", "accountant"))
        self._post(s.collection_move_id)
        self.assertEqual(self._at(s), ("collected", "await_remittance", "finance"))

    def test_the_whole_path_from_collection_to_closed(self):
        s = self._collected("A2")
        rem = self._remit("S-A2", [(s, 1000, {"deduction_freight": 100})], bank=900)
        self.assertEqual(self._at(s), ("remitted", "reconcile", "finance"))
        rem.with_user(self.fin).action_reconcile()
        self.assertEqual(self._at(s), ("reconciled", "settle_entry", "finance"))
        self.assertEqual(self._at(rem), ("settle_entry", "finance"))
        rem.with_user(self.fin).action_create_entry()
        self.assertEqual(self._at(s), ("reconciled", "post_settlement", "accountant"))
        self.assertEqual(self._at(rem), ("post_settlement", "accountant"))
        self._post(rem.move_id)
        self.assertEqual(self._at(s), ("closed", "none", "none"))
        self.assertEqual(self._at(rem), ("none", "none"))

    def test_a_withdrawn_entry_sends_the_parcel_back_through_the_steps(self):
        s = self._collected("A3")
        s.with_user(self.fin)._reverse_entry("booked twice", self.today)
        self.assertEqual(self._at(s), ("collected", "post_reversal", "accountant"))
        self._post(s.collection_move_id.reversal_move_ids)
        self.assertEqual(self._at(s), ("collected", "collect_entry", "finance"))

    def test_a_withdrawn_settlement_sends_the_slip_back(self):
        s = self._collected("A4")
        rem = self._remit("S-A4", [(s, 1000, {})], bank=1000)
        rem.with_user(self.fin).action_reconcile()
        rem.with_user(self.fin).action_create_entry()
        self._post(rem.move_id)
        rem.with_user(self.fin)._reverse_entry("wrong account", self.today)
        self.assertEqual(self._at(rem), ("post_reversal", "accountant"))
        self._post(rem.move_id.reversal_move_ids)
        self.assertEqual(self._at(rem), ("settle_entry", "finance"))

    def test_the_queues_find_the_accountants_work(self):
        s = self._ship("A5")
        s.with_user(self.fin).action_create_collection_entry()
        self.assertIn(s, self.Ship.search([("flow_owner", "=", "accountant")]))
        self.assertNotIn(s, self.Ship.search([("flow_owner", "=", "finance")]))

    # ------------------------------------------------------------------ the strict order
    def test_strict_by_default_a_slip_cannot_be_settled_before_its_parcels_are_booked(self):
        self.env["ir.config_parameter"].sudo().set_param("pharma.cod_flow_mode", False)     # parameter absent
        s = self._ship("B1")
        rem = self._remit("S-B1", [(s, 1000, {})], bank=1000)
        rem.with_user(self.fin).action_reconcile()
        self.assertEqual(rem._flow_mode(), "strict")
        with self.assertRaises(UserError) as cm:
            rem.with_user(self.fin).action_create_entry()
        self.assertIn("B1", str(cm.exception))
        self.assertIn("POSTED collection entry", str(cm.exception))
        self.assertFalse(rem.move_id)

    def test_a_draft_collection_entry_is_not_enough(self):
        self._set_mode("strict")
        s = self._ship("B2")
        s.with_user(self.fin).action_create_collection_entry()
        rem = self._remit("S-B2", [(s, 1000, {})], bank=1000)
        rem.with_user(self.fin).action_reconcile()
        with self.assertRaises(UserError):
            rem.with_user(self.fin).action_create_entry()

    def test_a_posted_collection_entry_lets_the_slip_through(self):
        self._set_mode("strict")
        s = self._collected("B3")
        rem = self._remit("S-B3", [(s, 1000, {})], bank=1000)
        rem.with_user(self.fin).action_reconcile()
        rem.with_user(self.fin).action_create_entry()
        self.assertTrue(rem.move_id)

    def test_a_written_reason_overrides_and_is_logged(self):
        self._set_mode("strict")
        s = self._ship("B4")
        rem = self._remit("S-B4", [(s, 1000, {})], bank=1000)
        rem.with_user(self.fin).action_reconcile()
        rem.flow_override_reason = "   "
        with self.assertRaises(UserError):
            rem.with_user(self.fin).action_create_entry()                # blank is not a reason
        rem.flow_override_reason = "Courier sent the slip before the delivery report was loaded"
        rem.with_user(self.fin).action_create_entry()
        self.assertTrue(rem.move_id)
        note = rem.message_ids.filtered(lambda m: "Order check overridden" in (m.body or ""))
        self.assertTrue(note)
        self.assertIn("Courier sent the slip", note[0].body)
        self.assertIn("B4", note[0].body)

    def test_advisory_mode_allows_it_and_notes_the_gap(self):
        self._set_mode("advisory")
        s = self._ship("B5")
        rem = self._remit("S-B5", [(s, 1000, {})], bank=1000)
        rem.with_user(self.fin).action_reconcile()
        rem.with_user(self.fin).action_create_entry()
        self.assertTrue(rem.move_id)
        self.assertTrue(rem.message_ids.filtered(lambda m: "Advisory" in (m.body or "")))

    def test_a_reversed_collection_entry_no_longer_counts_as_booked(self):
        self._set_mode("strict")
        s = self._collected("B6")
        s.with_user(self.fin)._reverse_entry("withdrawn", self.today)
        self._post(s.collection_move_id.reversal_move_ids)
        rem = self._remit("S-B6", [(s, 1000, {})], bank=1000)
        rem.with_user(self.fin).action_reconcile()
        with self.assertRaises(UserError):
            rem.with_user(self.fin).action_create_entry()

    # ------------------------------------------------------------------ the accountant's queue
    def test_every_cod_entry_is_tagged_with_its_kind(self):
        s = self._collected("K1")
        rem = self._remit("S-K1", [(s, 1000, {})], bank=1000)
        rem.with_user(self.fin).action_reconcile()
        rem.with_user(self.fin).action_create_entry()
        s.with_user(self.fin)._reverse_entry("test", self.today)
        self.assertEqual(s.collection_move_id.pharma_cod_kind, "collection")
        self.assertEqual(rem.move_id.pharma_cod_kind, "settlement")
        self.assertEqual(s.collection_move_id.reversal_move_ids.pharma_cod_kind, "reversal")

    def test_entries_to_post_lists_exactly_the_draft_cod_entries(self):
        action = self.env.ref("pharma_courier_cod_accounting.action_pharma_cod_entries_to_post")
        domain = ast.literal_eval(action.domain)
        s = self._ship("K2")
        s.with_user(self.fin).action_create_collection_entry()
        move = s.collection_move_id
        self.assertIn(move, self.env["account.move"].search(domain))
        self._post(move)
        self.assertNotIn(move, self.env["account.move"].search(domain))
        plain = self.env["account.move"].create({"move_type": "entry", "journal_id": self.journal.id,
                                                 "date": fields.Date.today()})
        self.assertNotIn(plain, self.env["account.move"].search(domain))     # other drafts are not the COD queue
