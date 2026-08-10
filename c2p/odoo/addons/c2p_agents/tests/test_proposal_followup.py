"""Agent 3 — time parked in a stage whose name reads as a proposal stage."""

from odoo.tests import tagged

from ..models.crm_lead import PROPOSAL_SUMMARY
from .common import C2pAgentsCommon


@tagged("post_install", "-at_install")
class TestProposalFollowup(C2pAgentsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.proposal_stage = cls.env["crm.stage"].create({"name": "Proposal Sent"})
        cls.other_stage = cls.env["crm.stage"].create({"name": "Negotiation"})

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

    def test_stage_whose_name_does_not_match_is_out_of_scope(self):
        lead = self._parked(self.other_stage, 30, name="Sitting in negotiation")

        self.env["crm.lead"]._cron_followup_proposals()

        self.assertFalse(self.agent_activities(lead, self.call_type, PROPOSAL_SUMMARY))

    def test_stage_hints_match_quotation_and_offer_too(self):
        for stage_name in ("Quotation Review", "Offer Issued", "PROPOSAL follow"):
            stage = self.env["crm.stage"].create({"name": stage_name})
            self.assertIn(
                stage.id,
                self.env["crm.lead"]._c2p_proposal_stage_ids(),
                "%s should read as a proposal stage" % stage_name,
            )

    def test_renaming_a_stage_out_of_the_hints_is_reported_not_silent(self):
        """The cost of matching names, made visible rather than quiet.

        With no stage matching, the run records why it selected nothing. A bare
        zero would read as a quiet week — which is the failure this module
        exists to stop.
        """
        self.env["crm.stage"].search([]).write({"name": "Unrecognisable"})

        result = self.env["crm.lead"]._cron_followup_proposals()

        self.assertEqual(result["scanned"], 0)
        run = self.env["c2p.agent.run"].search(
            [("agent", "=", "proposal_followup")], order="id desc", limit=1
        )
        self.assertIn("no CRM stage name contains", run.note)

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
