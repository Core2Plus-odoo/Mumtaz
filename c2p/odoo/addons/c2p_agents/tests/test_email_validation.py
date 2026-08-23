"""Agent 5 — address validation, and the WhatsApp fallback it feeds.

The layers are tested as plain functions with the domain check switched off, so
the suite makes no network calls and does not depend on a resolver being
reachable from wherever it runs. The one test that exercises resolution feeds
the cache directly.
"""

from odoo.tests import tagged

from ..models.email_validation import (
    INVALID,
    RISKY,
    VALID,
    address_domain,
    validate_address,
)
from .common import C2pAgentsCommon


@tagged("post_install", "-at_install")
class TestEmailValidation(C2pAgentsCommon):
    # ------------------------------------------------------------------
    # Layer 1 — syntax
    # ------------------------------------------------------------------
    def test_empty_and_malformed_addresses_are_invalid(self):
        for bad in ("", "   ", "not-an-address", "@nodomain.com", "two@@at.com"):
            verdict, _ = validate_address(bad, check_domain=False)
            self.assertEqual(verdict, INVALID, "%r should be invalid" % bad)

    def test_display_name_form_is_accepted(self):
        verdict, _ = validate_address(
            "Aisha Rahman <aisha@realbusiness.ae>", check_domain=False
        )
        self.assertEqual(verdict, VALID)

    def test_address_domain_extraction(self):
        self.assertEqual(address_domain("a@b.co"), "b.co")
        self.assertEqual(address_domain("Name <a@B.CO>"), "b.co")
        self.assertEqual(address_domain(""), "")

    # ------------------------------------------------------------------
    # Layer 2 — domain class
    # ------------------------------------------------------------------
    def test_free_provider_is_risky_not_invalid(self):
        """A gmail address is deliverable. It just tells you something."""
        verdict, detail = validate_address("someone@gmail.com", check_domain=False)
        self.assertEqual(verdict, RISKY)
        self.assertIn("free mailbox", detail)

    def test_disposable_provider_is_invalid(self):
        verdict, detail = validate_address("x@mailinator.com", check_domain=False)
        self.assertEqual(verdict, INVALID)
        self.assertIn("disposable", detail)

    def test_business_domain_is_valid(self):
        verdict, _ = validate_address("ops@core2plus.com", check_domain=False)
        self.assertEqual(verdict, VALID)

    # ------------------------------------------------------------------
    # Layer 3 — resolution, via a pre-seeded cache (no network)
    # ------------------------------------------------------------------
    def test_unresolvable_domain_is_invalid(self):
        cache = {"deadd0main.invalid": (False, "domain does not exist")}
        verdict, detail = validate_address("a@deadd0main.invalid", cache)
        self.assertEqual(verdict, INVALID)
        self.assertEqual(detail, "domain does not exist")

    def test_resolvable_domain_passes_through(self):
        cache = {"realbusiness.ae": (True, "MX record found")}
        verdict, detail = validate_address("a@realbusiness.ae", cache)
        self.assertEqual(verdict, VALID)
        self.assertEqual(detail, "MX record found")

    def test_a_seeded_cache_is_used_instead_of_resolving(self):
        """The cache is what stops a 100-lead run making 100 identical lookups."""
        cache = {"shared-domain.example": (True, "seeded — not resolved")}
        for local in ("a", "b", "c"):
            _, detail = validate_address("%s@shared-domain.example" % local, cache)
            self.assertEqual(detail, "seeded — not resolved")
        self.assertEqual(len(cache), 1, "no second domain should have been added")

    # ------------------------------------------------------------------
    # The agent
    # ------------------------------------------------------------------
    def setUp(self):
        """Take any pre-existing leads out of scope.

        The agent selects every unchecked lead, and a database carrying demo
        data would drag those into the run — making the counts non-deterministic
        and, worse, firing real DNS lookups from the test suite. Marking them
        checked leaves each test looking only at the lead it created.
        """
        super().setUp()
        self.env["crm.lead"].search(
            [("c2p_email_validity", "=", "unknown")]
        ).write({"c2p_email_validity": VALID})

    def test_agent_records_verdicts_and_skips_rechecking(self):
        lead = self.make_lead(name="Disposable", email_from="x@mailinator.com")

        first = self.env["crm.lead"]._cron_validate_emails()

        self.assertEqual(first["scanned"], 1)
        self.assertEqual(lead.c2p_email_validity, INVALID)
        self.assertTrue(lead.c2p_email_checked_on)
        self.assertIn("disposable", lead.c2p_email_validity_detail)

        # Already checked, so a second run selects nothing at all.
        second = self.env["crm.lead"]._cron_validate_emails()
        self.assertEqual(second["scanned"], 0)

    def test_leads_without_an_address_are_not_selected(self):
        lead = self.make_lead(name="No address", email_from=False)

        self.env["crm.lead"]._cron_validate_emails()

        self.assertEqual(lead.c2p_email_validity, "unknown")

    def test_dry_run_writes_nothing(self):
        lead = self.make_lead(name="Dry", email_from="x@mailinator.com")

        result = self.env["crm.lead"]._cron_validate_emails(dry_run=True)

        self.assertEqual(result["scanned"], 1)
        self.assertEqual(lead.c2p_email_validity, "unknown")
        self.assertFalse(lead.c2p_email_checked_on)

    def test_run_note_breaks_down_the_verdicts(self):
        self.make_lead(name="Junk", email_from="x@mailinator.com")

        self.env["crm.lead"]._cron_validate_emails()

        run = self.env["c2p.agent.run"].search(
            [("agent", "=", "email_validation")], order="id desc", limit=1
        )
        self.assertIn("invalid=", run.note)

    # ------------------------------------------------------------------
    # WhatsApp fallback
    # ------------------------------------------------------------------
    def test_usable_email_routes_to_email(self):
        lead = self.make_lead(
            name="Reachable", email_from="ops@core2plus.com", phone="+971500000000"
        )
        lead.c2p_email_validity = VALID
        self.assertEqual(lead.c2p_outreach_channel, "email")

    def test_invalid_email_with_a_number_routes_to_whatsapp(self):
        lead = self.make_lead(
            name="Bad address", email_from="x@mailinator.com", phone="+971500000000"
        )
        lead.c2p_email_validity = INVALID
        self.assertEqual(lead.c2p_outreach_channel, "whatsapp")

    def test_risky_email_still_routes_to_email(self):
        """Risky is deliverable — only invalid triggers the fallback."""
        lead = self.make_lead(
            name="Gmail lead", email_from="someone@gmail.com", phone="+971500000000"
        )
        lead.c2p_email_validity = RISKY
        self.assertEqual(lead.c2p_outreach_channel, "email")

    def test_no_address_and_no_number_has_no_channel(self):
        lead = self.make_lead(name="Unreachable", email_from=False, phone=False)
        self.assertEqual(lead.c2p_outreach_channel, "none")

    def test_missing_email_falls_back_to_whatsapp(self):
        lead = self.make_lead(name="Phone only", email_from=False, phone="+971500000000")
        self.assertEqual(lead.c2p_outreach_channel, "whatsapp")
