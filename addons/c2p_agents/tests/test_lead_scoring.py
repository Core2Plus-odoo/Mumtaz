"""Agent 1 — the production scoring arithmetic and its priority bands.

Every number asserted here comes from cron 44's `code` field as read on
2026-08-10. If a weight changes, this file is where it shows up as a failure
with the old number in it.
"""

from odoo.tests import tagged

from .common import C2pAgentsCommon


@tagged("post_install", "-at_install")
class TestLeadScoring(C2pAgentsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.source_referral = cls.env["utm.source"].create({"name": "Referral"})
        cls.source_meta_referral = cls.env["utm.source"].create(
            {"name": "Meta referral campaign"}
        )
        cls.source_unknown = cls.env["utm.source"].create({"name": "Trade Show Q3"})
        cls.uae = cls.env.ref("base.ae")
        cls.pakistan = cls.env.ref("base.pk")

    def test_every_rule_contributes(self):
        """referral 25 + GCC 20 + business email 20 + revenue 25 + phone 10
        + contact 5 = 105."""
        lead = self.make_lead(
            source_id=self.source_referral.id,
            country_id=self.uae.id,
            email_from="ops@clientcompany.ae",
            expected_revenue=120000,
            phone="+971 50 000 0000",
            contact_name="Aisha Rahman",
        )
        self.assertEqual(lead._c2p_lead_score(), 105)
        self.assertEqual(lead._c2p_lead_priority(), "3")

    def test_source_signals_are_additive(self):
        """A source matching both rules scores both — 20 + 25, not 25.

        This is the production behaviour and the easiest thing to get wrong when
        reading the original as an if/elif ladder.
        """
        lead = self.make_lead(source_id=self.source_meta_referral.id)
        self.assertEqual(lead._c2p_lead_score(), 45)
        self.assertEqual(lead._c2p_lead_priority(), "2")

    def test_bare_lead_scores_nothing(self):
        lead = self.make_lead(name="Walk-in enquiry")
        self.assertEqual(lead._c2p_lead_score(), 0)
        self.assertEqual(lead._c2p_lead_priority(), "0")

    def test_free_provider_earns_no_email_points(self):
        personal = self.make_lead(email_from="someone@gmail.com")
        business = self.make_lead(email_from="someone@realbusiness.ae")
        self.assertEqual(personal._c2p_lead_score(), 0)
        self.assertEqual(business._c2p_lead_score(), 20)

    def test_free_marker_matches_any_country_variant(self):
        """The markers carry a trailing dot, so gmail.co.uk is caught too."""
        for address in ("a@gmail.com", "a@gmail.co.uk", "a@yahoo.co.uk"):
            lead = self.make_lead(email_from=address)
            self.assertEqual(lead._c2p_lead_score(), 0, address)

    def test_non_gcc_country_scores_nothing(self):
        """Production scores the six GCC states only — Pakistan is not one."""
        gcc = self.make_lead(country_id=self.uae.id)
        other = self.make_lead(country_id=self.pakistan.id)
        self.assertEqual(gcc._c2p_lead_score(), 20)
        self.assertEqual(other._c2p_lead_score(), 0)

    def test_unmapped_source_scores_zero_rather_than_failing(self):
        lead = self.make_lead(source_id=self.source_unknown.id)
        self.assertEqual(lead._c2p_lead_score(), 0)

    def test_revenue_bands_do_not_stack(self):
        self.assertEqual(self.make_lead(expected_revenue=250000)._c2p_lead_score(), 25)
        self.assertEqual(self.make_lead(expected_revenue=30000)._c2p_lead_score(), 25)
        self.assertEqual(self.make_lead(expected_revenue=29999)._c2p_lead_score(), 10)
        self.assertEqual(self.make_lead(expected_revenue=7000)._c2p_lead_score(), 10)
        self.assertEqual(self.make_lead(expected_revenue=6999)._c2p_lead_score(), 0)

    def test_an_existing_activity_is_worth_points(self):
        """Production reads a scheduled activity as somebody working the lead."""
        lead = self.make_lead(name="Being worked")
        self.assertEqual(lead._c2p_lead_score(), 0)
        lead.activity_schedule(
            activity_type_id=self.todo_type.id,
            summary="Rep's own note",
            user_id=self.salesperson.id,
        )
        lead.invalidate_recordset(["activity_ids"])
        self.assertEqual(lead._c2p_lead_score(), 5)

    def test_priority_band_boundaries(self):
        """65 is Very High, 45 is High, 25 is Medium — each inclusive."""
        # GCC 20 + email 20 + phone 10 = 50
        high = self.make_lead(
            country_id=self.uae.id,
            email_from="a@business.ae",
            phone="+971 50 000 0000",
        )
        self.assertEqual(high._c2p_lead_score(), 50)
        self.assertEqual(high._c2p_lead_priority(), "2")

        # GCC 20 + phone 10 = 30
        medium = self.make_lead(country_id=self.uae.id, phone="+971 50 000 0000")
        self.assertEqual(medium._c2p_lead_score(), 30)
        self.assertEqual(medium._c2p_lead_priority(), "1")

        # phone alone = 10
        low = self.make_lead(phone="+971 50 000 0000")
        self.assertEqual(low._c2p_lead_score(), 10)
        self.assertEqual(low._c2p_lead_priority(), "0")

    def test_cron_writes_the_computed_priority(self):
        lead = self.make_lead(
            source_id=self.source_referral.id,
            country_id=self.uae.id,
            email_from="ops@clientcompany.ae",
            expected_revenue=120000,
            phone="+971 50 000 0000",
            contact_name="Aisha Rahman",
        )
        self.assertEqual(lead.priority, "0", "sanity: starts at the default")

        self.env["crm.lead"]._cron_score_leads()

        self.assertEqual(lead.priority, "3")

    def test_scoring_does_not_disturb_write_date(self):
        """Load-bearing: the stale agent selects on write_date.

        If the scorer bumped write_date on every lead it looked at, no lead
        would ever look quiet for 21 days and agent 2 would select nothing for
        the rest of time.
        """
        lead = self.make_lead(name="Unchanged by scoring")
        self.age(lead, "write_date", 400)
        before = lead.write_date

        self.env["crm.lead"]._cron_score_leads()
        lead.invalidate_recordset(["write_date", "c2p_scored_on"])

        self.assertEqual(lead.write_date, before, "write_date must be untouched")
        self.assertTrue(lead.c2p_scored_on, "but the pass must still be recorded")

    def test_run_is_recorded(self):
        before = self.env["c2p.agent.run"].search_count([("agent", "=", "lead_scoring")])
        self.env["crm.lead"]._cron_score_leads()
        after = self.env["c2p.agent.run"].search_count([("agent", "=", "lead_scoring")])
        self.assertEqual(after, before + 1)
