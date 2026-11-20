from odoo.tests import tagged

from .common import CourierCase


@tagged("post_install", "-at_install", "pharma")
class TestCourierFlow(CourierCase):
    """Every parcel and every remittance says where it is on the one path and what comes next, and who owns it."""

    def _at(self, s):
        return (s.flow_stage, s.flow_next, s.flow_owner)

    # ------------------------------------------------------------------ the parcel's path
    def test_before_delivery_the_parcel_is_just_awaited(self):
        booked = self._ship("F1", state="booked", days_ago=None, collected=0.0)
        transit = self._ship("F2", state="in_transit", days_ago=None, collected=0.0)
        self.assertEqual(self._at(booked), ("booked", "track", "ops"))
        self.assertEqual(self._at(transit), ("in_transit", "track", "ops"))

    def test_delivered_without_a_collected_figure_asks_finance_to_confirm_it(self):
        s = self._ship("F3", collected=0.0)
        self.assertEqual(self._at(s), ("delivered", "confirm_collection", "finance"))

    def test_collected_waits_for_the_courier_and_chases_once_overdue(self):
        fresh = self._ship("F4", days_ago=3)
        late = self._ship("F5", days_ago=20)                    # Test Courier remits within 14 days
        self.assertEqual(self._at(fresh), ("collected", "await_remittance", "finance"))
        self.assertEqual(self._at(late), ("collected", "chase_remittance", "finance"))

    def test_a_draft_slip_changes_nothing_a_posted_one_asks_for_reconciliation(self):
        s = self._ship("F6")
        rem = self._remit("S-F6", [(s, 1000, {})], bank=1000, post=False)
        self.assertEqual(s.flow_stage, "collected")
        rem.action_post()
        self.assertEqual(self._at(s), ("remitted", "reconcile", "finance"))

    def test_a_reconciled_slip_closes_the_parcel(self):
        s = self._ship("F7")
        rem = self._remit("S-F7", [(s, 1000, {})], bank=1000)
        rem.with_user(self.fin).action_reconcile()
        self.assertEqual(self._at(s), ("closed", "none", "none"))

    def test_a_part_remittance_keeps_the_rest_owed(self):
        s = self._ship("F8", days_ago=3)
        rem = self._remit("S-F8", [(s, 600, {})], bank=600)
        rem.with_user(self.fin).action_reconcile()
        self.assertEqual(self._at(s), ("remitted", "await_remittance", "finance"))

    def test_prepaid_parcels_are_closed_on_delivery(self):
        s = self._ship("F9", declared=0.0, mode="prepaid", collected=0.0)
        self.assertEqual(self._at(s), ("closed", "none", "none"))

    def test_returned_and_cancelled_leave_the_path(self):
        held = self._ship("F10", state="returned")              # COD was collected and is still with the courier
        clean = self._ship("F11", state="returned", collected=0.0)
        gone = self._ship("F12", state="cancelled", days_ago=None, collected=0.0)
        self.assertEqual(self._at(held), ("returned", "settle_returned", "finance"))
        self.assertEqual(self._at(clean), ("returned", "none", "none"))
        self.assertEqual(self._at(gone), ("cancelled", "none", "none"))

    def test_the_text_names_the_step_and_the_owner(self):
        s = self._ship("F13", state="in_transit", days_ago=None, collected=0.0)
        self.assertEqual(s.flow_next_text, "Awaiting delivery (Operations)")
        self.assertEqual(self._ship("F14", declared=0.0, mode="prepaid", collected=0.0).flow_next_text, "Nothing further")

    def test_the_stage_follows_the_records_it_is_not_typed(self):
        s = self._ship("F15", state="in_transit", days_ago=None, collected=0.0)
        self.assertEqual(s.flow_stage, "in_transit")
        s.write({"state": "delivered", "date_delivered": self.today, "cod_collected": 1000.0})
        self.assertEqual(self._at(s), ("collected", "await_remittance", "finance"))

    # ------------------------------------------------------------------ queues
    def test_the_queue_is_found_by_owner_and_by_step(self):
        a = self._ship("Q1", collected=0.0)
        b = self._ship("Q2", state="in_transit", days_ago=None, collected=0.0)
        done = self._ship("Q3", declared=0.0, mode="prepaid", collected=0.0)
        finance = self.Ship.search([("flow_owner", "=", "finance")])
        ops = self.Ship.search([("flow_owner", "=", "ops")])
        self.assertIn(a, finance)
        self.assertNotIn(b, finance)
        self.assertIn(b, ops)
        open_work = self.Ship.search([("flow_next", "not in", ("none",))])
        self.assertNotIn(done, open_work)
        self.assertIn(a, open_work)

    def test_open_findings_count_the_parcels_own_unclosed_exceptions(self):
        short = self._ship("Q4", declared=1000, collected=900)
        clean = self._ship("Q5", declared=1000, collected=1000)
        (short | clean).action_check()
        self.assertEqual((short.open_findings, clean.open_findings), (1, 0))   # the customer paid 100 less on Q4

    # ------------------------------------------------------------------ the remittance's path
    def test_a_remittance_walks_post_reconcile_resolve(self):
        s = self._ship("R1", declared=1000, collected=900)
        rem = self._remit("S-R1", [(s, 900, {})], bank=900, post=False)
        self.assertEqual((rem.flow_next, rem.flow_owner), ("post_slip", "finance"))
        rem.action_post()
        self.assertEqual(rem.flow_next, "reconcile")
        rem.with_user(self.fin).action_reconcile()
        self.assertTrue(rem.open_exceptions)                    # the customer paid 100 less than declared
        self.assertEqual((rem.flow_next, rem.flow_next_text), ("resolve", "Resolve the open findings (Finance Controller)"))

    def test_a_clean_reconciled_remittance_has_nothing_further(self):
        s = self._ship("R2")
        rem = self._remit("S-R2", [(s, 1000, {})], bank=1000)
        rem.with_user(self.fin).action_reconcile()
        self.assertEqual((rem.flow_next, rem.flow_owner), ("none", "none"))

    def test_a_cancelled_remittance_has_nothing_further(self):
        s = self._ship("R3")
        rem = self._remit("S-R3", [(s, 1000, {})], bank=1000, post=False)
        rem.action_cancel()
        self.assertEqual(rem.flow_next, "none")
