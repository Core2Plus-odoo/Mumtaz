from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import C2pTrackerCommon


@tagged("post_install", "-at_install")
class TestHealth(C2pTrackerCommon):
    """Each RAG trigger, and the override."""

    def setUp(self):
        super().setUp()
        self.today = fields.Date.context_today(self.portfolio)
        # Give the project commercials so the "missing" amber rule does not
        # mask the trigger under test.
        self.portfolio.write({"contract_value": 10000.0,
                              "amount_received": 9000.0})

    def _reasons(self):
        self.portfolio.invalidate_recordset()
        return self.portfolio.rag_reasons or ""

    def test_green_when_nothing_is_wrong(self):
        self.pm1.write({"date_deadline": self.today + timedelta(days=30)})
        self.assertEqual(self.portfolio.rag_status, "green")
        self.assertEqual(self.portfolio.health_score, 100)

    def test_amber_on_milestone_one_to_seven_days_overdue(self):
        self.pm1.write({"date_deadline": self.today - timedelta(days=3)})
        self.assertEqual(self.portfolio.rag_status, "amber")
        self.assertIn("3 days overdue", self._reasons())

    def test_red_on_milestone_more_than_seven_days_overdue(self):
        self.pm1.write({"date_deadline": self.today - timedelta(days=9)})
        self.assertEqual(self.portfolio.rag_status, "red")
        self.assertIn("9 days overdue", self._reasons())

    def test_red_on_golive_slippage_over_threshold(self):
        self.pm1.write({"date_deadline": self.today + timedelta(days=30)})
        self.portfolio.write({
            "baseline_golive_date": self.today,
            "forecast_golive_date": self.today + timedelta(days=30),
        })
        self.assertEqual(self.portfolio.golive_slippage_days, 30)
        self.assertEqual(self.portfolio.rag_status, "red")
        self.assertIn("slipped 30 days", self._reasons())

    def test_amber_when_an_open_milestone_has_no_deadline(self):
        """Every milestone in production currently lacks a deadline, so this
        is the state the dashboard will actually open in."""
        self.assertFalse(self.pm1.date_deadline)
        self.assertEqual(self.portfolio.rag_status, "amber")
        self.assertIn("no deadline", self._reasons())

    def test_amber_when_commercials_are_missing(self):
        self.pm1.write({"date_deadline": self.today + timedelta(days=30)})
        self.portfolio.write({"contract_value": 0.0})
        self.assertEqual(self.portfolio.rag_status, "amber")
        self.assertIn("Commercials", self._reasons())

    def test_amber_when_outstanding_high_and_progress_past_half(self):
        self.pm1.write({"date_deadline": self.today + timedelta(days=30),
                        "stage_id": self.p_stage["Done"].id})
        # One milestone, done, so progress is 100%.
        self.portfolio.write({"contract_value": 10000.0, "amount_received": 1000.0})
        self.portfolio.invalidate_recordset()
        self.assertEqual(self.portfolio.progress_pct, 100.0)
        self.assertEqual(self.portfolio.rag_status, "amber")
        self.assertIn("outstanding", self._reasons().lower())

    def test_override_wins_and_states_its_reason(self):
        self.pm1.write({"date_deadline": self.today - timedelta(days=30)})
        self.assertEqual(self.portfolio.rag_status, "red")
        self.portfolio.write({
            "rag_override": "green",
            "rag_override_reason": "Client agreed a revised plan",
        })
        self.portfolio.invalidate_recordset()
        self.assertEqual(self.portfolio.rag_status, "green")
        self.assertIn("Client agreed a revised plan", self._reasons())

    def test_weighted_progress_uses_weights(self):
        heavy = self.env["project.task"].create({
            "name": "M2 Heavy", "project_id": self.portfolio.id,
            "stage_id": self.p_stage["Done"].id, "weight": 3.0,
        })
        self.pm1.weight = 1.0
        self.portfolio.invalidate_recordset()
        # 3 of 4 weight units done.
        self.assertEqual(self.portfolio.progress_pct, 75.0)
        self.assertTrue(heavy.c2p_is_milestone)

    def test_non_portfolio_projects_are_grey(self):
        self.assertEqual(self.delivery.rag_status, "grey")
        template = self.env["project.project"].create({
            "name": "Playbook", "c2p_layer": "template",
        })
        self.assertEqual(template.rag_status, "grey")

    def test_blocker_age_drives_status(self):
        self.pm1.write({"date_deadline": self.today + timedelta(days=30)})
        task = self._delivery_task(stage="Waiting on Client",
                                   blocked_reason="Awaiting data")
        # waiting_since is today, so the blocker is 0 days old: not yet amber
        # on that count.
        task.write({"waiting_since": self.today - timedelta(days=10)})
        self.portfolio.invalidate_recordset()
        self.assertEqual(self.portfolio.rag_status, "amber")
        task.write({"waiting_since": self.today - timedelta(days=20)})
        self.portfolio.invalidate_recordset()
        self.assertEqual(self.portfolio.rag_status, "red")
