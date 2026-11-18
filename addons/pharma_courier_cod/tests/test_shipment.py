from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tools import mute_logger

from odoo.addons.pharma_courier_cod.models.shipment import map_status

from odoo.tests import tagged

from .common import CourierCase


@tagged("post_install", "-at_install", "pharma")
class TestCourierShipment(CourierCase):

    def test_status_mapping_is_not_fooled_by_words_that_contain_deliver(self):
        cases = {"Delivered": "delivered", "DELIVERED": "delivered", "Undelivered": "in_transit",
                 "Not Delivered": "in_transit", "Out for Delivery": "in_transit", "Delivery Attempted": "in_transit",
                 "Delivery Failed": "in_transit", "Returned to Shipper": "returned", "RTO": "returned",
                 "Cancelled": "cancelled", "In Transit": "in_transit", "Arrived at Hub": "in_transit",
                 "Booked": "booked", "Order Placed": "booked", "": "booked", None: "booked"}
        for raw, expected in cases.items():
            self.assertEqual(map_status(raw), expected, raw)

    def test_tracking_number_is_unique_per_courier(self):
        self._ship("U1")
        with self.assertRaises(Exception), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self._ship("U1", with_order=False)
        self._ship("U1", courier=self.courier2, with_order=False)       # another courier may reuse a number

    # ------------------------------------------------------------------ COD arithmetic
    def test_clean_cod_from_collected_to_remitted(self):
        s = self._ship("A1", declared=1000)
        self.assertEqual((s.cod_state, s.cod_outstanding, s.cod_collection_variance), ("outstanding", 1000.0, 0.0))
        self._remit("R1", [(s, 1000, {"deduction_freight": 100})])
        self.assertEqual((s.cod_remitted, s.cod_deductions, s.cod_net_received), (1000.0, 100.0, 900.0))
        self.assertEqual((s.cod_state, s.cod_outstanding), ("remitted", 0.0))

    def test_customer_paid_less_is_a_collection_variance(self):
        s = self._ship("A2", declared=1000, collected=900)
        self.assertEqual(s.cod_collection_variance, -100.0)
        self.assertEqual(s.cod_outstanding, 900.0)

    def test_partial_remittance(self):
        s = self._ship("A3", declared=1000)
        self._remit("R3", [(s, 600, {})])
        self.assertEqual((s.cod_state, s.cod_outstanding, s.cod_remittance_variance), ("partial", 400.0, -400.0))

    def test_delivered_with_nothing_collected(self):
        s = self._ship("A4", declared=1000, collected=0)
        self.assertEqual((s.cod_state, s.cod_outstanding), ("uncollected", 0.0))
        self.assertEqual(s.cod_collection_variance, -1000.0)

    def test_states_where_no_cod_is_expected(self):
        self.assertEqual(self._ship("B1", mode="prepaid").cod_state, "none")
        self.assertEqual(self._ship("B2", state="returned").cod_state, "none")
        self.assertEqual(self._ship("B3", state="cancelled").cod_state, "none")
        pending = self._ship("B4", state="in_transit", days_ago=None)
        self.assertEqual((pending.cod_state, pending.cod_outstanding), ("pending", 0.0))

    def test_only_posted_remittances_count(self):
        s = self._ship("C1")
        rem = self._remit("RC1", [(s, 1000, {})], post=False)
        self.assertEqual(s.cod_remitted, 0.0)
        rem.action_post()
        self.assertEqual(s.cod_remitted, 1000.0)
        rem.action_cancel()
        self.assertEqual((s.cod_remitted, s.cod_state), (0.0, "outstanding"))

    # ------------------------------------------------------------------ ageing
    def test_ageing_buckets_and_the_overdue_boundary(self):
        table = {0: "b_0_7", 7: "b_0_7", 8: "b_8_15", 15: "b_8_15", 16: "b_16_30", 30: "b_16_30",
                 31: "b_31_plus", 90: "b_31_plus"}
        for days, bucket in table.items():
            s = self._ship(f"G{days}", days_ago=days)
            self.assertEqual((s.cod_days_outstanding, s.cod_ageing_bucket), (days, bucket), days)
        self.assertFalse(self._ship("G14", days_ago=14, courier=self.courier2).cod_is_overdue)      # cycle is 14: day 14 is on time
        self.assertTrue(self._ship("G15x", days_ago=15).cod_is_overdue)                              # day 15 is overdue

    def test_ageing_applies_only_to_outstanding_cod(self):
        remitted = self._ship("H1", days_ago=40)
        self._remit("RH1", [(remitted, 1000, {})])
        for s in (remitted, self._ship("H2", days_ago=40, mode="prepaid"), self._ship("H3", days_ago=40, state="returned")):
            self.assertEqual((s.cod_days_outstanding, s.cod_ageing_bucket, s.cod_is_overdue), (0, False, False), s.tracking_number)

    def test_ageing_runs_from_delivery_not_from_booking(self):
        s = self._ship("H4", days_ago=3, date_booked=self.today - timedelta(days=60))
        self.assertEqual((s.cod_days_outstanding, s.cod_ageing_bucket), (3, "b_0_7"))

    def test_refresh_moves_a_shipment_to_the_bucket_for_today(self):
        s = self._ship("I1", days_ago=2)
        self.assertEqual(s.cod_ageing_bucket, "b_0_7")
        # time passing changes no field, which is exactly why ageing needs the refresh
        self.env.cr.execute("UPDATE pharma_courier_shipment SET date_delivered = %s WHERE id = %s",
                            (self.today - timedelta(days=20), s.id))
        s.invalidate_recordset()
        s.action_refresh_ageing()
        self.assertEqual((s.cod_days_outstanding, s.cod_ageing_bucket), (20, "b_16_30"))

    def test_a_longer_agreed_cycle_delays_overdue(self):
        self.courier2.remittance_cycle_days = 30
        self.assertFalse(self._ship("I2", days_ago=20, courier=self.courier2).cod_is_overdue)
        self.assertTrue(self._ship("I3", days_ago=31, courier=self.courier2).cod_is_overdue)

    # ------------------------------------------------------------------ values and the order link
    def test_bad_values_are_refused(self):
        with self.assertRaises(ValidationError):
            self._ship("V1", declared=-1)
        with self.assertRaises(ValidationError):
            self._ship("V2", date_booked=self.today, days_ago=5)             # delivered before it was booked
        with self.assertRaises(ValidationError):
            self.courier.remittance_cycle_days = 0

    def test_order_is_linked_by_customer_reference_or_by_number(self):
        so = self._order("ORD-77")
        s = self.Ship.create({"courier_id": self.courier.id, "tracking_number": "L1", "order_ref": "ORD-77"})
        self.assertEqual((s.sale_order_id, s.order_matched), (so, True))
        s2 = self.Ship.create({"courier_id": self.courier.id, "tracking_number": "L2", "order_ref": so.name})
        self.assertEqual(s2.sale_order_id, so)

    def test_order_link_is_made_later_when_the_reference_is_set_later(self):
        s = self.Ship.create({"courier_id": self.courier.id, "tracking_number": "L3"})
        self.assertFalse(s.order_matched)
        so = self._order("ORD-78")
        s.order_ref = "ORD-78"
        self.assertEqual((s.sale_order_id, s.order_matched), (so, True))

    def test_a_courier_reporting_an_unknown_order_still_creates_a_shipment(self):
        s = self.Ship.create({"courier_id": self.courier.id, "tracking_number": "L4", "order_ref": "NO-SUCH"})
        self.assertFalse(s.order_matched)

    # ------------------------------------------------------------------ security
    def test_who_may_create_what(self):
        vals = {"courier_id": self.courier.id, "tracking_number": "S1"}
        with self.assertRaises(AccessError):
            self.Ship.with_user(self.ops).create(vals)
        self.assertTrue(self.Ship.with_user(self.fin).create(vals))
        with self.assertRaises(AccessError):
            self.env["pharma.courier"].with_user(self.fin).create({"name": "X", "code": "XX"})
        self.assertTrue(self.env["pharma.courier"].with_user(self.adm).create({"name": "Y", "code": "YY"}))
        self.assertEqual(len(self.Ship.with_user(self.ops).search([("tracking_number", "=", "S1")])), 1)   # read is allowed
