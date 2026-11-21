"""Agent 2 — which opportunities count as stale, and which do not."""

from odoo.tests import tagged

from ..models.crm_lead import STALE_SUMMARY
from .common import C2pAgentsCommon


@tagged("post_install", "-at_install")
class TestStaleLeads(C2pAgentsCommon):
    def _stale_candidate(self, **values):
        """A high-priority opportunity that has been quiet for 25 days."""
        values.setdefault("priority", "3")
        values.setdefault("probability", 30)
        lead = self.make_lead(**values)
        self.age(lead, "write_date", 25)
        return lead

    def test_quiet_high_priority_opportunity_is_flagged(self):
        lead = self._stale_candidate(name="Quiet big deal")

        self.env["crm.lead"]._cron_flag_stale_opportunities()

        activity = self.agent_activities(lead, self.todo_type, STALE_SUMMARY)
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity.user_id, self.salesperson)

    def test_recently_touched_opportunity_is_left_alone(self):
        lead = self.make_lead(name="Active deal", priority="3", probability=30)
        self.age(lead, "write_date", 10)

        self.env["crm.lead"]._cron_flag_stale_opportunities()

        self.assertFalse(self.agent_activities(lead, self.todo_type, STALE_SUMMARY))

    def test_boundary_is_inclusive_at_the_threshold(self):
        """21 days qualifies, 20 does not."""
        at_threshold = self.make_lead(name="Exactly 21", priority="3", probability=30)
        self.age(at_threshold, "write_date", 21)
        just_under = self.make_lead(name="Only 20", priority="3", probability=30)
        self.age(just_under, "write_date", 20)

        self.env["crm.lead"]._cron_flag_stale_opportunities()

        self.assertTrue(
            self.agent_activities(at_threshold, self.todo_type, STALE_SUMMARY)
        )
        self.assertFalse(
            self.agent_activities(just_under, self.todo_type, STALE_SUMMARY)
        )

    def test_low_priority_is_out_of_scope(self):
        lead = self._stale_candidate(name="Quiet small deal", priority="1")

        self.env["crm.lead"]._cron_flag_stale_opportunities()

        self.assertFalse(self.agent_activities(lead, self.todo_type, STALE_SUMMARY))

    def test_opportunity_with_an_open_activity_is_not_stale(self):
        """A pending activity is exactly what "no activity" is meant to exclude."""
        lead = self.make_lead(name="Already being worked", priority="3", probability=30)
        lead.activity_schedule(
            activity_type_id=self.call_type.id,
            summary="Rep's own call",
            user_id=self.salesperson.id,
        )
        self.age(lead, "write_date", 25)

        self.env["crm.lead"]._cron_flag_stale_opportunities()

        self.assertFalse(self.agent_activities(lead, self.todo_type, STALE_SUMMARY))

    def test_won_opportunity_is_out_of_scope(self):
        lead = self.make_lead(name="Closed won", priority="3", probability=100)
        self.age(lead, "write_date", 25)

        self.env["crm.lead"]._cron_flag_stale_opportunities()

        self.assertFalse(self.agent_activities(lead, self.todo_type, STALE_SUMMARY))

    def test_archived_opportunity_is_out_of_scope(self):
        lead = self._stale_candidate(name="Lost deal")
        lead.active = False
        self.age(lead, "write_date", 25)

        self.env["crm.lead"]._cron_flag_stale_opportunities()

        self.assertFalse(self.agent_activities(lead, self.todo_type, STALE_SUMMARY))

    def test_plain_lead_is_out_of_scope(self):
        """The agent chases opportunities, not unconverted leads."""
        lead = self._stale_candidate(name="Unconverted", type="lead")

        self.env["crm.lead"]._cron_flag_stale_opportunities()

        self.assertFalse(self.agent_activities(lead, self.todo_type, STALE_SUMMARY))

    def test_limit_is_respected(self):
        for index in range(5):
            self._stale_candidate(name="Quiet deal %s" % index)

        result = self.env["crm.lead"]._cron_flag_stale_opportunities(limit=2)

        self.assertEqual(result["scanned"], 2)
        self.assertLessEqual(result["acted"], 2)
