"""Agent 3 — two proposal stages, two different messages.

Production matches stage names exactly: "Proposal Sent" means chase the client,
"Proposal to be Send" means chase ourselves. Getting those the same way round is
the whole point of the agent.
"""

from odoo.tests import tagged

from ..models.crm_lead import (
    PROPOSAL_PENDING_SUMMARY,
    PROPOSAL_SENT_SUMMARY,
    PROPOSAL_STAGE_PENDING,
    PROPOSAL_STAGE_SENT,
)
from .common import C2pAgentsCommon


@tagged("post_install", "-at_install")
class TestProposalFollowup(C2pAgentsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stage_sent = cls.env["crm.stage"].create({"name": PROPOSAL_STAGE_SENT})
        cls.stage_pending = cls.env["crm.stage"].create(
            {"name": PROPOSAL_STAGE_PENDING}
        )
        cls.stage_other = cls.env["crm.stage"].create({"name": "Negotiation"})

    def _parked(self, stage, days, **values):
        lead = self.make_lead(stage_id=stage.id, **values)
        self.age(lead, "date_last_stage_update", days)
        return lead

    def test_sent_proposal_gets_a_follow_up_call(self):
        lead = self._parked(self.stage_sent, 10, name="Out with the client")

        self.env["crm.lead"]._cron_followup_proposals()

        activity = self.agent_activities(lead, self.call_type, PROPOSAL_SENT_SUMMARY)
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity.user_id, self.salesperson)
        self.assertIn("Call rather than email", activity.note)

    def test_unsent_proposal_chases_us_not_the_client(self):
        """The other stage means we have not issued it yet — different message."""
        lead = self._parked(self.stage_pending, 10, name="Still not issued")

        self.env["crm.lead"]._cron_followup_proposals()

        self.assertFalse(
            self.agent_activities(lead, self.call_type, PROPOSAL_SENT_SUMMARY)
        )
        activity = self.agent_activities(
            lead, self.call_type, PROPOSAL_PENDING_SUMMARY
        )
        self.assertEqual(len(activity), 1)
        self.assertIn("issue the proposal today", activity.note)

    def test_fresh_proposal_is_left_alone(self):
        lead = self._parked(self.stage_sent, 3, name="Just sent")

        self.env["crm.lead"]._cron_followup_proposals()

        self.assertFalse(
            self.agent_activities(lead, self.call_type, PROPOSAL_SENT_SUMMARY)
        )

    def test_boundary_is_inclusive_at_the_threshold(self):
        at_threshold = self._parked(self.stage_sent, 8, name="Past 7 days")
        just_under = self._parked(self.stage_sent, 6, name="Only 6")

        self.env["crm.lead"]._cron_followup_proposals()

        self.assertTrue(
            self.agent_activities(at_threshold, self.call_type, PROPOSAL_SENT_SUMMARY)
        )
        self.assertFalse(
            self.agent_activities(just_under, self.call_type, PROPOSAL_SENT_SUMMARY)
        )

    def test_other_stages_are_out_of_scope(self):
        lead = self._parked(self.stage_other, 30, name="Sitting in negotiation")

        self.env["crm.lead"]._cron_followup_proposals()

        self.assertFalse(
            self.agent_activities(lead, self.call_type, PROPOSAL_SENT_SUMMARY)
        )

    def test_stage_names_are_matched_exactly(self):
        """A near-miss name is not a proposal stage. This is the fragility the
        run note exists to make visible."""
        near_miss = self.env["crm.stage"].create({"name": "Proposal Sent to Client"})
        lead = self._parked(near_miss, 30, name="Near-miss stage")

        self.env["crm.lead"]._cron_followup_proposals()

        self.assertFalse(
            self.agent_activities(lead, self.call_type, PROPOSAL_SENT_SUMMARY)
        )

    def test_no_matching_stage_is_reported_not_silent(self):
        self.env["crm.stage"].search(
            [("name", "in", [PROPOSAL_STAGE_SENT, PROPOSAL_STAGE_PENDING])]
        ).write({"name": "Renamed away"})

        result = self.env["crm.lead"]._cron_followup_proposals()

        self.assertEqual(result["scanned"], 0)
        run = self.env["c2p.agent.run"].search(
            [("agent", "=", "proposal_followup")], order="id desc", limit=1
        )
        self.assertIn("no crm.stage is named", run.note)

    def test_lead_with_an_open_activity_is_left_alone(self):
        lead = self.make_lead(
            name="Being chased already", stage_id=self.stage_sent.id
        )
        lead.activity_schedule(
            activity_type_id=self.todo_type.id,
            summary="Rep's own note",
            user_id=self.salesperson.id,
        )
        self.age(lead, "date_last_stage_update", 30)

        self.env["crm.lead"]._cron_followup_proposals()

        self.assertFalse(
            self.agent_activities(lead, self.call_type, PROPOSAL_SENT_SUMMARY)
        )

    def test_ownerless_lead_is_skipped_and_counted(self):
        """Production refuses to schedule a task for nobody."""
        lead = self._parked(
            self.stage_sent, 10, name="Nobody's proposal", user_id=False
        )
        lead.team_id = False

        result = self.env["crm.lead"]._cron_followup_proposals()

        self.assertFalse(
            self.agent_activities(lead, self.call_type, PROPOSAL_SENT_SUMMARY)
        )
        run = self.env["c2p.agent.run"].search(
            [("agent", "=", "proposal_followup")], order="id desc", limit=1
        )
        self.assertIn("no owner", run.note)
        self.assertGreaterEqual(result["scanned"], 1)

    def test_rerun_does_not_duplicate(self):
        lead = self._parked(self.stage_sent, 10, name="Chase once")

        self.env["crm.lead"]._cron_followup_proposals()
        self.env["crm.lead"]._cron_followup_proposals()

        self.assertEqual(
            len(self.agent_activities(lead, self.call_type, PROPOSAL_SENT_SUMMARY)), 1
        )
