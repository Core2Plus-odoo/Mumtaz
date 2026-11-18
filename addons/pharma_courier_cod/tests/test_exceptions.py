from odoo.exceptions import UserError

from odoo.tests import tagged

from .common import CourierCase


@tagged("post_install", "-at_install", "pharma")
class TestCourierExceptions(CourierCase):

    def test_customer_paid_less_raises_one_exception(self):
        s = self._ship("E1", declared=1000, collected=900)
        self.assertEqual(s.action_check(), 1)
        exc = self._exc("TCOD/E1/collection")
        self.assertEqual((exc.category, exc.amount, exc.state), ("collection", 100.0, "open"))
        self.assertEqual((exc.run_id.run_type, exc.is_demo, exc.source_model, exc.source_id),
                         ("cod", True, "pharma.courier.shipment", s.id))
        self.assertIn("E1", exc.description)

    def test_checking_again_raises_nothing_new(self):
        s = self._ship("E2", declared=1000, collected=900)
        s.action_check()
        self.assertEqual(s.action_check(), 0)
        self.assertEqual(len(self._exc("TCOD/E2/collection")), 1)

    def test_a_resolved_exception_stays_resolved(self):
        s = self._ship("E3", declared=1000, collected=900)
        s.action_check()
        self._exc("TCOD/E3/collection").write({"state": "closed"})
        self.assertEqual(s.action_check(), 0)
        self.assertEqual(len(self._exc("TCOD/E3/collection")), 1)

    def test_courier_accounting_for_less_is_a_different_exception_from_customer_paying_less(self):
        s = self._ship("E4", declared=1000, collected=1000)
        self._remit("RE4", [(s, 700, {"deduction_freight": 100})])
        self.assertEqual(s.action_check(), 1)
        exc = self._exc("TCOD/E4/remittance")
        self.assertEqual((exc.category, exc.amount), ("remittance", 300.0))
        self.assertFalse(self._exc("TCOD/E4/collection"))

    def test_overdue_cod_raises_an_exception(self):
        s = self._ship("E5", days_ago=20)
        self.assertEqual(s.action_check(), 1)
        exc = self._exc("TCOD/E5/overdue")
        self.assertEqual((exc.category, exc.amount), ("overdue", 1000.0))
        self.assertIn("20 days", exc.description)

    def test_cod_collected_on_a_returned_parcel(self):
        s = self._ship("E6", state="returned", collected=500, days_ago=None)
        self.assertEqual(s.action_check(), 1)
        exc = self._exc("TCOD/E6/returned_cod")
        self.assertEqual((exc.category, exc.amount), ("returned_cod", 500.0))

    def test_a_parcel_with_no_matching_order_is_a_finding(self):
        s = self._ship("E7", with_order=False)
        self.assertEqual(s.action_check(), 1)
        exc = self._exc("TCOD/E7/intake")
        self.assertEqual((exc.category, exc.amount), ("intake", 0.0))
        self._order("E8")
        self.assertEqual(self._ship("E8", with_order=False, order_ref="E8").action_check(), 0)

    def test_tolerance_hides_small_differences_only(self):
        self.courier.variance_tolerance = 50.0
        small = self._ship("E9", declared=1000, collected=960)
        big = self._ship("E10", declared=1000, collected=940)
        self.assertEqual(small.action_check(), 0)
        self.assertEqual(big.action_check(), 1)

    def test_findings_land_in_a_monthly_monitoring_run_in_the_hub_queue(self):
        s = self._ship("E11", declared=1000, collected=900)
        s.action_check()
        run = self._exc("TCOD/E11/collection").run_id
        self.assertEqual(run.name, f"COD monitoring TCOD {self.today.strftime('%Y-%m')}")
        self.assertEqual((run.run_type, run.is_demo), ("cod", True))
        self.assertEqual(run.open_exceptions, 1)
        s2 = self._ship("E12", declared=1000, collected=900)
        s2.action_check()
        self.assertEqual(self._exc("TCOD/E12/collection").run_id, run)         # one run per courier and month

    def test_refresh_all_is_for_finance_or_the_scheduler(self):
        s = self._ship("E13", days_ago=20)
        with self.assertRaises(UserError):
            self.Ship.with_user(self.ops).action_refresh_all()
        result = self.Ship.with_user(self.fin).action_refresh_all()
        self.assertEqual(result["tag"], "display_notification")
        self.assertTrue(self._exc("TCOD/E13/overdue"))
        self.assertTrue(s)

    def test_the_daily_job_runs_as_the_scheduler(self):
        self._ship("E14", days_ago=20)
        self.Ship._cron_daily()
        self.assertTrue(self._exc("TCOD/E14/overdue"))
