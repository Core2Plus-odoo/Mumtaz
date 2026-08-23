"""Agents 6 and 7 — the "no lead falls through" pair, plus scoring coverage.

These are the agents whose job is completeness, so the tests are mostly about
what happens to the *backlog*: does a run actually reduce it, and does the next
run pick up where the last one stopped.
"""

from odoo.tests import tagged

from ..models.crm_lead import COVERAGE_SUMMARY
from .common import C2pAgentsCommon


@tagged("post_install", "-at_install")
class TestLeadCoverage(C2pAgentsCommon):
    def setUp(self):
        """Take pre-existing leads out of scope.

        These agents deliberately select every lead in a bad state, so demo data
        would make the counts non-deterministic. Giving the existing ones an
        owner and a scored-on stamp leaves each test looking only at what it
        created.
        """
        super().setUp()
        leftovers = self.env["crm.lead"].search(
            ["|", ("user_id", "=", False), ("c2p_scored_on", "=", False)]
        )
        leftovers.write(
            {"user_id": self.salesperson.id, "c2p_scored_on": "2020-01-01 00:00:00"}
        )

    # ------------------------------------------------------------------
    # Agent 6 — owner assignment
    # ------------------------------------------------------------------
    def test_unowned_lead_gets_a_salesperson(self):
        lead = self.make_lead(name="Nobody's lead", user_id=False, probability=20)
        self.assertFalse(lead.user_id, "sanity: starts unassigned")

        result = self.env["crm.lead"]._cron_assign_owners()

        self.assertEqual(result["scanned"], 1)
        self.assertTrue(lead.user_id)

    def test_already_owned_leads_are_not_reassigned(self):
        lead = self.make_lead(name="Has an owner", probability=20)

        self.env["crm.lead"]._cron_assign_owners()

        self.assertEqual(lead.user_id, self.salesperson)

    def test_won_lead_is_out_of_scope(self):
        lead = self.make_lead(name="Closed won", user_id=False, probability=100)

        self.env["crm.lead"]._cron_assign_owners()

        self.assertFalse(lead.user_id)

    def test_every_lead_in_the_batch_gets_an_owner(self):
        leads = self.env["crm.lead"]
        for index in range(5):
            leads |= self.make_lead(
                name="Unowned %s" % index, user_id=False, probability=20
            )

        result = self.env["crm.lead"]._cron_assign_owners()

        self.assertEqual(result["acted"], 5)
        self.assertTrue(all(leads.mapped("user_id")))

    def test_dry_run_assigns_nobody(self):
        lead = self.make_lead(name="Dry", user_id=False, probability=20)

        result = self.env["crm.lead"]._cron_assign_owners(dry_run=True)

        self.assertEqual(result["acted"], 1)
        self.assertFalse(lead.user_id)

    # ------------------------------------------------------------------
    # Agent 7 — guaranteed next step
    # ------------------------------------------------------------------
    def _neglected(self, name="Neglected", days=5, **values):
        values.setdefault("probability", 20)
        lead = self.make_lead(name=name, **values)
        self.age(lead, "create_date", days)
        return lead

    def test_lead_with_no_next_step_gets_one(self):
        lead = self._neglected()

        self.env["crm.lead"]._cron_ensure_next_step()

        activity = self.agent_activities(lead, self.todo_type, COVERAGE_SUMMARY)
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity.user_id, self.salesperson)

    def test_lead_inside_the_grace_period_is_left_alone(self):
        """A lead that arrived this morning is not neglected yet."""
        lead = self._neglected(name="Brand new", days=1)

        self.env["crm.lead"]._cron_ensure_next_step()

        self.assertFalse(self.agent_activities(lead, self.todo_type, COVERAGE_SUMMARY))

    def test_lead_that_already_has_an_activity_is_left_alone(self):
        lead = self._neglected(name="Being worked")
        lead.activity_schedule(
            activity_type_id=self.call_type.id,
            summary="Rep's own call",
            user_id=self.salesperson.id,
        )

        self.env["crm.lead"]._cron_ensure_next_step()

        self.assertFalse(self.agent_activities(lead, self.todo_type, COVERAGE_SUMMARY))

    def test_unowned_lead_is_left_to_the_assignment_agent(self):
        """No point scheduling a task for nobody — agent 6 runs first."""
        lead = self._neglected(name="Unowned", user_id=False)

        self.env["crm.lead"]._cron_ensure_next_step()

        self.assertFalse(self.agent_activities(lead, self.todo_type, COVERAGE_SUMMARY))

    def test_rerun_does_not_duplicate(self):
        lead = self._neglected()

        self.env["crm.lead"]._cron_ensure_next_step()
        self.env["crm.lead"]._cron_ensure_next_step()

        self.assertEqual(
            len(self.agent_activities(lead, self.todo_type, COVERAGE_SUMMARY)), 1
        )

    def test_backlog_figure_shrinks_as_the_agent_works(self):
        for index in range(4):
            self._neglected(name="Neglected %s" % index)

        first = self.env["crm.lead"]._cron_ensure_next_step(limit=2)
        second = self.env["crm.lead"]._cron_ensure_next_step(limit=2)

        self.assertEqual(first["acted"], 2)
        self.assertEqual(second["acted"], 2)
        run = self.env["c2p.agent.run"].search(
            [("agent", "=", "coverage_followup")], order="id desc", limit=1
        )
        self.assertIn("0 lead(s) still with no next step", run.note)

    def test_dry_run_schedules_nothing(self):
        lead = self._neglected()

        result = self.env["crm.lead"]._cron_ensure_next_step(dry_run=True)

        self.assertEqual(result["acted"], 1)
        self.assertFalse(self.agent_activities(lead, self.todo_type, COVERAGE_SUMMARY))

    # ------------------------------------------------------------------
    # Scoring coverage — the reason c2p_scored_on exists
    # ------------------------------------------------------------------
    def test_never_scored_leads_are_taken_first(self):
        """The defect this field fixes: a limit must not strand old leads.

        Ordering by write_date meant the same recently-edited records were
        rescored nightly while everything older was never reached at all.
        """
        old = self.make_lead(name="Old and unscored")
        self.age(old, "write_date", 400)
        for index in range(3):
            self.make_lead(name="Recently touched %s" % index)

        batch = self.env["crm.lead"]._c2p_scoring_batch(limit=2)

        self.assertIn(old, batch, "the oldest unscored lead must not be stranded")

    def test_scoring_stamps_every_lead_it_looks_at(self):
        """Including ones whose priority did not change, or the backlog sticks."""
        lead = self.make_lead(name="Scores zero")
        self.assertEqual(lead._c2p_lead_priority(), "0")
        self.assertEqual(lead.priority, "0", "sanity: nothing will change")

        self.env["crm.lead"]._cron_score_leads()

        self.assertTrue(
            lead.c2p_scored_on, "an unchanged lead must still be marked as seen"
        )

    def test_the_backlog_drains_across_runs(self):
        leads = self.env["crm.lead"]
        for index in range(5):
            leads |= self.make_lead(name="Unscored %s" % index)

        self.env["crm.lead"]._cron_score_leads(limit=2)
        self.env["crm.lead"]._cron_score_leads(limit=2)
        self.env["crm.lead"]._cron_score_leads(limit=2)

        self.assertTrue(
            all(leads.mapped("c2p_scored_on")),
            "three runs of two should have covered all five",
        )
