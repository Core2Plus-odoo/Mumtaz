from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import C2pTrackerCommon


@tagged("post_install", "-at_install")
class TestHygiene(C2pTrackerCommon):
    """Assignee + deadline + milestone on leaving Backlog, and blocked reasons."""

    def test_backlog_needs_nothing(self):
        task = self.env["project.task"].create({
            "name": "Rough idea", "project_id": self.delivery.id,
            "stage_id": self.d_stage["Backlog"].id,
        })
        self.assertTrue(task.id)

    def test_leaving_backlog_requires_all_three(self):
        task = self.env["project.task"].create({
            "name": "Rough idea", "project_id": self.delivery.id,
            "stage_id": self.d_stage["Backlog"].id,
        })
        with self.assertRaises(ValidationError) as caught:
            task.write({"stage_id": self.d_stage["To Do"].id})
        message = str(caught.exception)
        for expected in ("assignee", "deadline", "milestone"):
            self.assertIn(expected, message,
                          f"the error should name the missing {expected}")

    def test_leaving_backlog_with_all_three_succeeds(self):
        task = self._delivery_task(stage="To Do")
        self.assertEqual(task.stage_id.name, "To Do")

    def test_partial_hygiene_still_blocked(self):
        task = self.env["project.task"].create({
            "name": "Half ready", "project_id": self.delivery.id,
            "stage_id": self.d_stage["Backlog"].id,
            "user_ids": [(6, 0, [self.worker.id])],
        })
        with self.assertRaises(ValidationError):
            task.write({"stage_id": self.d_stage["To Do"].id})

    def test_portfolio_tasks_are_exempt(self):
        """The hygiene rule is a delivery discipline; portfolio milestones are
        driven by the sync engine and must not be held to it."""
        task = self.env["project.task"].create({
            "name": "M9 later milestone", "project_id": self.portfolio.id,
            "stage_id": self.p_stage["Not Started"].id,
        })
        task.write({"stage_id": self.p_stage["In Progress"].id})
        self.assertEqual(task.stage_id.name, "In Progress")

    def test_waiting_on_client_requires_a_reason(self):
        task = self._delivery_task(stage="To Do")
        with self.assertRaises(ValidationError):
            task.write({"stage_id": self.d_stage["Waiting on Client"].id})

    def test_baseline_reset_denied_to_delivery_member(self):
        self.pm1.write({"date_deadline": "2026-11-01"})
        self.assertTrue(self.pm1.baseline_deadline)
        with self.assertRaises(UserError):
            self.pm1.with_user(self.worker).action_reset_baseline()

    def test_counterpart_pair_must_be_one_of_each(self):
        other = self.env["project.project"].create({
            "name": "Another delivery", "c2p_layer": "delivery",
            "company_id": self.company_solutions.id,
        })
        with self.assertRaises(ValidationError):
            other.c2p_counterpart_id = self.delivery

    def test_counterpart_cannot_be_self(self):
        with self.assertRaises(ValidationError):
            self.portfolio.c2p_counterpart_id = self.portfolio

    def test_counterpart_link_is_reciprocal(self):
        self.assertEqual(self.delivery.c2p_counterpart_id, self.portfolio)
