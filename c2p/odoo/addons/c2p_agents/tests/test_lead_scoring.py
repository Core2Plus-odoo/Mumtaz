"""Agent 1 — scoring arithmetic and the priority bands it maps onto."""

from odoo.tests import tagged

from .common import C2pAgentsCommon


@tagged("post_install", "-at_install")
class TestLeadScoring(C2pAgentsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.source_referral = cls.env["utm.source"].create({"name": "Referral"})
        cls.source_unknown = cls.env["utm.source"].create({"name": "Trade Show Q3"})
        cls.uae = cls.env.ref("base.ae")
        cls.pakistan = cls.env.ref("base.pk")

    def test_every_rule_contributes(self):
        """A lead ticking all six rules scores the sum of all six."""
        lead = self.make_lead(
            source_id=self.source_referral.id,     # 25
            country_id=self.uae.id,                # 25
            email_from="ops@clientcompany.ae",     # 15
            expected_revenue=120000,               # 25
            phone="+971 50 000 0000",              # 10
            contact_name="Aisha Rahman",           # 10
        )
        self.assertEqual(lead._c2p_lead_score(), 110)
        self.assertEqual(lead._c2p_lead_priority(), "3")

    def test_bare_lead_scores_nothing(self):
        lead = self.make_lead(name="Walk-in enquiry")
        self.assertEqual(lead._c2p_lead_score(), 0)
        self.assertEqual(lead._c2p_lead_priority(), "0")

    def test_free_email_is_not_a_business_email(self):
        """A gmail address earns no business-email points; a domain one does."""
        personal = self.make_lead(email_from="someone@gmail.com")
        business = self.make_lead(email_from="someone@realbusiness.ae")
        self.assertEqual(personal._c2p_lead_score(), 0)
        self.assertEqual(business._c2p_lead_score(), 15)

    def test_email_domain_survives_a_display_name(self):
        """`email_from` is routinely "Name <addr>" and must still parse."""
        lead = self.make_lead(email_from="Aisha Rahman <aisha@realbusiness.ae>")
        self.assertEqual(lead._c2p_email_domain(), "realbusiness.ae")
        self.assertEqual(lead._c2p_lead_score(), 15)

    def test_unmapped_source_scores_zero_rather_than_failing(self):
        """An unrecognised source is worth nothing, not an error."""
        lead = self.make_lead(source_id=self.source_unknown.id)
        self.assertEqual(lead._c2p_lead_score(), 0)

    def test_revenue_bands_do_not_stack(self):
        """Only the highest band a lead qualifies for is awarded."""
        top = self.make_lead(expected_revenue=250000)
        middle = self.make_lead(expected_revenue=50000)
        bottom = self.make_lead(expected_revenue=5000)
        below = self.make_lead(expected_revenue=4999)
        self.assertEqual(top._c2p_lead_score(), 25)
        self.assertEqual(middle._c2p_lead_score(), 20)
        self.assertEqual(bottom._c2p_lead_score(), 6)
        self.assertEqual(below._c2p_lead_score(), 0)

    def test_priority_band_boundaries(self):
        """40 points is High; 39 is Medium. The boundary is inclusive."""
        # country PK (8) + business email (15) + phone (10) + contact (10) = 43
        high = self.make_lead(
            country_id=self.pakistan.id,
            email_from="a@business.pk",
            phone="+92 300 0000000",
            contact_name="Named Person",
        )
        self.assertEqual(high._c2p_lead_score(), 43)
        self.assertEqual(high._c2p_lead_priority(), "2")

        # country PK (8) + business email (15) = 23
        medium = self.make_lead(
            country_id=self.pakistan.id, email_from="a@business.pk"
        )
        self.assertEqual(medium._c2p_lead_score(), 23)
        self.assertEqual(medium._c2p_lead_priority(), "1")

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

    def test_run_is_recorded(self):
        """Every run leaves an audit row, which is the point of the model."""
        before = self.env["c2p.agent.run"].search_count([("agent", "=", "lead_scoring")])
        self.env["crm.lead"]._cron_score_leads()
        after = self.env["c2p.agent.run"].search_count([("agent", "=", "lead_scoring")])
        self.assertEqual(after, before + 1)
