from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import C2pTrackerCommon

COMMERCIAL_FIELDS = [
    "contract_value", "amount_received", "amount_received_effective",
    "amount_outstanding", "subcontract_pct", "subcontract_value",
    "subcontract_paid", "subcontract_outstanding", "consultants_margin",
    "commercials_missing", "c2p_currency_id", "c2p_sale_order_id",
]


@tagged("post_install", "-at_install")
class TestSecurity(C2pTrackerCommon):
    """A Delivery Member must not reach an AED figure by any route."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portfolio.write({"contract_value": 15000.0, "amount_received": 3000.0})
        cls.manager = cls.env["res.users"].create({
            "name": "T-Manager", "login": "t-manager",
            "company_id": cls.company_consult.id,
            "company_ids": [(6, 0, [cls.company_consult.id,
                                    cls.company_solutions.id])],
            "group_ids": [(4, cls.env.ref(
                "c2p_project_tracker.group_c2p_portfolio_manager").id)],
        })

    def test_commercial_fields_are_hidden_from_delivery_member(self):
        """The acceptance criterion: no AED value anywhere for Shafat's team.
        read() with explicit fields is the RPC path a client would use."""
        project = self.portfolio.with_user(self.worker)
        for name in COMMERCIAL_FIELDS:
            with self.subTest(field=name):
                with self.assertRaises(AccessError,
                                       msg=f"{name} should be unreadable"):
                    project.read([name])

    def test_commercial_fields_are_absent_from_fields_get(self):
        """Not merely unreadable — a restricted field should not even be
        advertised, or a UI will try to render it and fail."""
        described = self.portfolio.with_user(self.worker).fields_get()
        for name in COMMERCIAL_FIELDS:
            self.assertNotIn(name, described,
                             f"{name} should not be exposed to a Delivery Member")

    def test_delivery_member_cannot_write_commercials(self):
        with self.assertRaises(AccessError):
            self.portfolio.with_user(self.worker).write({"contract_value": 1.0})

    def test_portfolio_manager_can_read_commercials(self):
        values = self.portfolio.with_user(self.manager).read(
            ["contract_value", "amount_outstanding"])[0]
        self.assertEqual(values["contract_value"], 15000.0)
        self.assertEqual(values["amount_outstanding"], 12000.0)

    def test_health_is_visible_without_the_figures(self):
        """A Delivery Lead should see why a project is amber without seeing the
        amounts, so the reason text must not contain a number with a currency."""
        lead = self.env["res.users"].create({
            "name": "T-Lead", "login": "t-lead",
            "company_id": self.company_solutions.id,
            "company_ids": [(6, 0, [self.company_solutions.id,
                                    self.company_consult.id])],
            "group_ids": [(4, self.env.ref(
                "c2p_project_tracker.group_c2p_delivery_lead").id)],
        })
        self.portfolio.write({"contract_value": 0.0})
        self.portfolio.invalidate_recordset()
        reasons = self.portfolio.with_user(lead).read(["rag_reasons"])[0]
        self.assertIn("Commercials", reasons["rag_reasons"])
        self.assertNotIn("15000", reasons["rag_reasons"])
        self.assertNotIn("AED", reasons["rag_reasons"])

    def test_multi_company_isolation_on_history(self):
        """History rows belong to the milestone's company and must not leak to
        a user without that company allowed."""
        self._delivery_task(stage="In Progress")
        rows = self.env["c2p.milestone.history"].search([])
        self.assertTrue(rows)
        self.assertEqual(rows[0].company_id, self.company_consult)
        visible = self.env["c2p.milestone.history"].with_user(
            self.worker).search([])
        self.assertNotIn(
            rows[0], visible,
            "a Solutions-only user should not see Consultants history rows")
