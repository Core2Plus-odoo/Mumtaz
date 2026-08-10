"""Agent 3 — time parked in a stage flagged as a proposal stage."""

from odoo.tests import tagged

from ..models.crm_lead import PROPOSAL_SUMMARY
from .common import C2pAgentsCommon


@tagged("post_install", "-at_install")
class TestProposalFollowup(C2pAgentsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.proposal_stage = cls.env["crm.stage"].create(
            {"name": "Proposal Sent", "is_proposal_stage": True}
        )
        cls.other_stage = cls.env["crm.stage"].create(
            {"name": "Qualification", "is_proposal_stage": False}
        )

    def _parked(self, stage, days, **values):
        values.setdefault("probability", 40)
        lead = self.make_lead(stage_id=stage.id, **values)
        self.age(lead, "date_last_stage_update", days)
        return lead

    def test_proposal_sitting_too_long_is_chased(self):
        lead = self._parked(self.proposal_stage, 10, name="Proposal out with client")

        self.env["crm.lead"]._cron_followup_proposals()

        activity = self.agent_activities(lead, self.call_type, PROPOSAL_SUMMARY)
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity.user_id, self.salesperson)

    def test_fresh_proposal_is_left_alone(self):
        lead = self._parked(self.proposal_stage, 3, name="Just sent")

        self.env["crm.lead"]._cron_followup_proposals()

        self.assertFalse(self.agent_activities(lead, self.call_type, PROPOSAL_SUMMARY))

    def test_boundary_is_inclusive_at_the_threshold(self):
        at_threshold = self._parked(self.proposal_stage, 7, name="Exactly 7")
        just_under = self._parked(self.proposal_stage, 6, name="Only 6")

        self.env["crm.lead"]._cron_followup_proposals()

        self.assertTrue(
            self.agent_activities(at_threshold, self.call_type, PROPOSAL_SUMMARY)
        )
        self.assertFalse(
            self.agent_activities(just_under, self.call_type, PROPOSAL_SUMMARY)
        )

    def test_unflagged_stage_is_out_of_scope(self):
        """This is the whole reason the flag exists rather than a name match."""
        lead = self._parked(self.other_stage, 30, name="Sitting in qualification")

        self.env["crm.lead"]._cron_followup_proposals()

        self.assertFalse(self.agent_activities(lead, self.call_type, PROPOSAL_SUMMARY))

    def test_unflagging_a_stage_takes_it_out_of_scope(self):
        """Selection follows the checkbox, so unticking it stops the chasing."""
        lead = self._parked(self.proposal_stage, 30, name="No longer chased")
        self.proposal_stage.is_proposal_stage = False

        self.env["crm.lead"]._cron_followup_proposals()

        self.assertFalse(self.agent_activities(lead, self.call_type, PROPOSAL_SUMMARY))

    def test_lead_with_an_open_activity_is_left_alone(self):
        lead = self.make_lead(
            name="Being chased already", stage_id=self.proposal_stage.id, probability=40
        )
        lead.activity_schedule(
            activity_type_id=self.todo_type.id,
            summary="Rep's own note",
            user_id=self.salesperson.id,
        )
        self.age(lead, "date_last_stage_update", 30)

        self.env["crm.lead"]._cron_followup_proposals()

        self.assertFalse(self.agent_activities(lead, self.call_type, PROPOSAL_SUMMARY))

    def test_won_lead_is_out_of_scope(self):
        lead = self.make_lead(
            name="Signed", stage_id=self.proposal_stage.id, probability=100
        )
        self.age(lead, "date_last_stage_update", 30)

        self.env["crm.lead"]._cron_followup_proposals()

        self.assertFalse(self.agent_activities(lead, self.call_type, PROPOSAL_SUMMARY))

    def test_install_hook_seeds_the_flag_from_stage_names(self):
        """The seeding rule that makes the flag useful on day one."""
        from ..models.crm_stage import seed_proposal_stages

        looks_like_one = self.env["crm.stage"].create({"name": "Quotation Review"})
        does_not = self.env["crm.stage"].create({"name": "Negotiation"})

        seed_proposal_stages(self.env)

        self.assertTrue(looks_like_one.is_proposal_stage)
        self.assertFalse(does_not.is_proposal_stage)
