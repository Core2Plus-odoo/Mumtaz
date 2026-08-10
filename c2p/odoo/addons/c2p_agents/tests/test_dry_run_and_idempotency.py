"""The two cross-cutting guarantees: dry runs write nothing, re-runs duplicate nothing.

Both are asserted per agent in the agents' own test files where it is cheap to
do so. This file covers the guarantees themselves — the settings plumbing, the
default, and the marker that makes deduplication work.
"""

from odoo import fields
from odoo.tests import tagged

from ..models.crm_lead import STALE_SUMMARY
from .common import C2pAgentsCommon


@tagged("post_install", "-at_install")
class TestDryRunAndIdempotency(C2pAgentsCommon):
    def _stale_lead(self, name="Quiet deal"):
        lead = self.make_lead(name=name, priority="3", probability=30)
        self.age(lead, "write_date", 25)
        return lead

    # ------------------------------------------------------------------
    # Dry run
    # ------------------------------------------------------------------
    def test_dry_run_reports_without_writing(self):
        lead = self._stale_lead()

        result = self.env["crm.lead"]._cron_flag_stale_opportunities(dry_run=True)

        self.assertGreaterEqual(result["acted"], 1, "intent is still reported")
        self.assertTrue(result["dry_run"])
        self.assertFalse(self.agent_activities(lead, self.todo_type, STALE_SUMMARY))

    def test_dry_run_scoring_does_not_write_priority(self):
        lead = self.make_lead(
            name="Would score high",
            country_id=self.env.ref("base.ae").id,
            email_from="ops@clientcompany.ae",
            expected_revenue=120000,
            phone="+971 50 000 0000",
            contact_name="Aisha Rahman",
        )

        self.env["crm.lead"]._cron_score_leads(dry_run=True)

        self.assertEqual(lead.priority, "0")
        self.assertEqual(
            lead._c2p_lead_priority(), "3", "it would have been raised on a live run"
        )

    def test_dry_run_is_still_recorded(self):
        """A dry run is a run. It has to be as visible as a live one."""
        self._stale_lead()

        self.env["crm.lead"]._cron_flag_stale_opportunities(dry_run=True)

        run = self.env["c2p.agent.run"].search(
            [("agent", "=", "stale_opportunity")], order="id desc", limit=1
        )
        self.assertTrue(run.dry_run)
        self.assertEqual(run.state, "ok")

    def test_parameter_supplies_the_default(self):
        self.env["ir.config_parameter"].sudo().set_param("c2p_agents.dry_run", "True")
        lead = self._stale_lead()

        self.env["crm.lead"]._cron_flag_stale_opportunities()

        self.assertFalse(
            self.agent_activities(lead, self.todo_type, STALE_SUMMARY),
            "with no explicit argument the parameter decides",
        )

    def test_an_explicit_argument_overrides_the_parameter(self):
        self.env["ir.config_parameter"].sudo().set_param("c2p_agents.dry_run", "True")
        lead = self._stale_lead()

        self.env["crm.lead"]._cron_flag_stale_opportunities(dry_run=False)

        self.assertTrue(self.agent_activities(lead, self.todo_type, STALE_SUMMARY))

    def test_an_unreadable_parameter_falls_back_to_dry(self):
        """Anything unrecognised must leave the agents safe, not arm them."""
        self.env["ir.config_parameter"].sudo().set_param(
            "c2p_agents.dry_run", "perhaps"
        )
        lead = self._stale_lead()

        self.env["crm.lead"]._cron_flag_stale_opportunities()

        self.assertFalse(self.agent_activities(lead, self.todo_type, STALE_SUMMARY))

    def test_a_broken_numeric_parameter_falls_back_to_its_default(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "c2p_agents.stale_days", "three weeks"
        )
        lead = self._stale_lead()

        self.env["crm.lead"]._cron_flag_stale_opportunities()

        self.assertTrue(
            self.agent_activities(lead, self.todo_type, STALE_SUMMARY),
            "it should fall back to 21 days rather than crash",
        )

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------
    def test_rerunning_creates_no_duplicate(self):
        lead = self._stale_lead()

        self.env["crm.lead"]._cron_flag_stale_opportunities()
        self.age(lead, "write_date", 25)  # the activity refreshed write_date
        self.env["crm.lead"]._cron_flag_stale_opportunities()

        self.assertEqual(
            len(self.agent_activities(lead, self.todo_type, STALE_SUMMARY)), 1
        )

    def test_a_flagged_record_drops_out_of_the_domain(self):
        """The first guard: the activity the agent created excludes the record.

        The CRM agents select on `activity_ids = False`, so a record they have
        flagged is no longer stale by their own definition. The summary marker
        checked in `_c2p_already_flagged` is the second line of defence, and the
        invoice chaser — which has no such filter — is where it does the work.
        """
        lead = self._stale_lead()

        self.env["crm.lead"]._cron_flag_stale_opportunities()
        self.age(lead, "write_date", 25)

        still_stale = self.env["crm.lead"].search(
            self.env["crm.lead"]._c2p_stale_domain(fields.Datetime.now())
        )
        self.assertNotIn(lead, still_stale)
        self.assertEqual(
            len(self.agent_activities(lead, self.todo_type, STALE_SUMMARY)), 1
        )

    def test_completing_the_activity_lets_a_still_stale_record_be_flagged_again(self):
        """Documented trade-off: the marker keys on OPEN activities.

        Once a rep marks the To-Do done and the record is still stale, the next
        run raises a fresh one. For a chaser that is the wanted behaviour, and
        this test exists so that changing it is a deliberate decision.
        """
        lead = self._stale_lead()
        self.env["crm.lead"]._cron_flag_stale_opportunities()
        activity = self.agent_activities(lead, self.todo_type, STALE_SUMMARY)
        self.assertEqual(len(activity), 1)

        activity.action_done()
        self.age(lead, "write_date", 25)
        self.env["crm.lead"]._cron_flag_stale_opportunities()

        self.assertEqual(
            len(self.agent_activities(lead, self.todo_type, STALE_SUMMARY)), 1
        )
