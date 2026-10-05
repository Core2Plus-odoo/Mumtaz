from odoo.tests import tagged

from .common import C2pTrackerCommon


@tagged("post_install", "-at_install")
class TestSync(C2pTrackerCommon):
    """The five ordered stage rules, deadline propagation and the baseline."""

    def test_no_tasks_leaves_stage_alone(self):
        """Rule 5: nothing to go on, so the stage is not touched."""
        self.portfolio._c2p_sync_portfolio_milestones()
        self.assertEqual(self._pm1_stage(), "Not Started")

    def test_in_progress_when_any_task_in_flight(self):
        """Rule 4."""
        self._delivery_task(stage="In Progress")
        self.assertEqual(self._pm1_stage(), "In Progress")

    def test_client_review_when_all_tasks_done(self):
        """Rule 3 beats rule 4: every task done means the client's turn."""
        self._delivery_task(name="A", stage="Done")
        self._delivery_task(name="B", stage="Done")
        self.assertEqual(self._pm1_stage(), "Client Review")

    def test_blocked_beats_client_review(self):
        """Rule 2 outranks rule 3: one waiting task blocks the milestone even
        when the rest are finished."""
        self._delivery_task(name="A", stage="Done")
        self._delivery_task(name="B", stage="Waiting on Client",
                            blocked_reason="Awaiting data")
        self.assertEqual(self._pm1_stage(), "Blocked")

    def test_reached_beats_everything(self):
        """Rule 1 outranks rule 2: a reached milestone is Done regardless."""
        self._delivery_task(name="B", stage="Waiting on Client",
                            blocked_reason="Awaiting data")
        self.dm1.is_reached = True
        self.portfolio._c2p_sync_portfolio_milestones()
        self.assertEqual(self._pm1_stage(), "Done")

    def test_waiting_loop_resolves_back_to_in_progress(self):
        """Waiting on Client → Blocked, then resolved → In Progress."""
        task = self._delivery_task(stage="Waiting on Client",
                                   blocked_reason="Awaiting sign-off")
        self.assertEqual(self._pm1_stage(), "Blocked")
        self.assertTrue(task.waiting_since, "waiting_since should be set")

        task.write({"stage_id": self.d_stage["In Progress"].id})
        self.assertEqual(self._pm1_stage(), "In Progress")
        self.assertFalse(task.waiting_since,
                         "waiting_since should clear on leaving the stage")

    def test_deadline_propagates_and_sets_baseline_once(self):
        self.dm1.deadline = "2026-11-01"
        self.portfolio._c2p_sync_portfolio_milestones()
        self.pm1.invalidate_recordset()
        self.assertEqual(str(self.pm1.date_deadline), "2026-11-01")
        self.assertEqual(str(self.pm1.baseline_deadline), "2026-11-01")

        # A later change moves the deadline but must leave the baseline, which
        # is what slippage is measured against.
        self.dm1.deadline = "2026-11-21"
        self.portfolio._c2p_sync_portfolio_milestones()
        self.pm1.invalidate_recordset()
        self.assertEqual(str(self.pm1.date_deadline), "2026-11-21")
        self.assertEqual(str(self.pm1.baseline_deadline), "2026-11-01")
        self.assertEqual(self.pm1.slippage_days, 20)

    def test_empty_delivery_deadline_does_not_clear_portfolio(self):
        """Production has 24 milestones with no deadline; copying False across
        would wipe the portfolio date and the baseline comparison with it."""
        self.pm1.write({"date_deadline": "2026-11-01"})
        self.assertFalse(self.dm1.deadline)
        self.portfolio._c2p_sync_portfolio_milestones()
        self.pm1.invalidate_recordset()
        self.assertEqual(str(self.pm1.date_deadline), "2026-11-01")

    def test_sync_locked_is_respected(self):
        self.pm1.sync_locked = True
        self._delivery_task(stage="In Progress")
        self.assertEqual(self._pm1_stage(), "Not Started")

    def test_history_row_written_and_note_is_internal(self):
        self._delivery_task(stage="In Progress")
        rows = self.env["c2p.milestone.history"].search(
            [("milestone_id", "=", self.pm1.id)])
        self.assertTrue(rows, "a history row should be written")
        self.assertEqual(rows[0].new_stage_id.name, "In Progress")
        self.assertEqual(rows[0].source, "sync")

        notes = self.pm1.message_ids.filtered(
            lambda m: m.subtype_id == self.env.ref("mail.mt_note"))
        self.assertTrue(notes, "an internal note should be posted")
        # The acceptance criterion is that no one is emailed.
        self.assertFalse(notes.mapped("partner_ids"),
                         "the auto-sync note must not notify any partner")

    def test_only_m_coded_tasks_are_milestones(self):
        """Portfolio projects hold ordinary tasks too — project 14 has 16 tasks
        for 8 milestones — so the M-code is what makes a milestone."""
        plain = self.env["project.task"].create({
            "name": "Weekly client call", "project_id": self.portfolio.id,
            "stage_id": self.p_stage["Not Started"].id,
        })
        self.assertFalse(plain.c2p_is_milestone)
        self.assertFalse(plain.c2p_code)
        self.assertTrue(self.pm1.c2p_is_milestone)
        self.assertEqual(self.pm1.c2p_code, "M1")
        self.assertEqual(self.portfolio._c2p_milestones(), self.pm1)

    def test_lowercase_code_normalises(self):
        task = self.env["project.task"].create({
            "name": "m7 lower case", "project_id": self.portfolio.id,
            "stage_id": self.p_stage["Not Started"].id,
        })
        self.assertEqual(task.c2p_code, "M7")
