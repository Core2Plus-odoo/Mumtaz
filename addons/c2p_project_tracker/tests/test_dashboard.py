from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import C2pTrackerCommon

MONEY_KEYS = {"portfolio_value", "collected", "outstanding",
              "payable_to_solutions", "consultants_margin"}


@tagged("post_install", "-at_install")
class TestDashboard(C2pTrackerCommon):
    """The dashboards' payloads, and that neither leaks a figure."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portfolio.write({"contract_value": 15000.0, "amount_received": 3000.0})
        cls.manager = cls.env["res.users"].create({
            "name": "T-Dash-Manager", "login": "t-dash-manager",
            "company_id": cls.company_consult.id,
            "company_ids": [(6, 0, [cls.company_consult.id,
                                    cls.company_solutions.id])],
            "group_ids": [(4, cls.env.ref(
                "c2p_project_tracker.group_c2p_portfolio_manager").id)],
        })

    def _portfolio(self, user):
        return self.env["c2p.dashboard"].with_user(user).portfolio_data()

    def test_manager_sees_money(self):
        data = self._portfolio(self.manager)
        self.assertTrue(data["show_money"])
        self.assertEqual(data["kpis"]["portfolio_value"], 15000.0)
        self.assertEqual(data["kpis"]["outstanding"], 12000.0)
        # 60% of 15,000 payable, none paid.
        self.assertEqual(data["kpis"]["payable_to_solutions"], 9000.0)

    def test_delivery_member_is_refused_the_portfolio(self):
        """Menu visibility is not access control — the method must refuse."""
        with self.assertRaises(AccessError):
            self._portfolio(self.worker)

    def test_delivery_payload_contains_no_money_key_at_all(self):
        """Not zeroed — absent, so nothing can be inferred from the shape."""
        data = self.env["c2p.dashboard"].with_user(self.worker).delivery_data()
        flat = str(data)
        for key in MONEY_KEYS | {"contract_value", "amount_received"}:
            self.assertNotIn(key, flat, f"{key} must not appear in delivery data")

    def test_rag_counts_sum_to_the_row_count(self):
        data = self._portfolio(self.manager)
        self.assertEqual(sum(data["rag_counts"].values()), len(data["rows"]))

    def test_row_carries_milestones_and_reasons(self):
        data = self._portfolio(self.manager)
        row = data["rows"][0]
        self.assertEqual(row["id"], self.portfolio.id)
        self.assertEqual(len(row["milestones"]), 1)
        self.assertEqual(row["milestones"][0]["code"], "M1")
        self.assertTrue(row["rag_reasons"], "the row should explain its status")

    def test_roadmap_reports_undated_rather_than_dropping_them(self):
        """Every production milestone currently lacks a deadline, so silently
        omitting them would make the roadmap look empty for no stated reason."""
        data = self._portfolio(self.manager)
        self.assertFalse(data["roadmap"]["has_dates"])
        self.assertEqual(data["roadmap"]["lanes"][0]["undated_count"], 1)

        self.pm1.write({"date_deadline": "2026-12-01"})
        data = self._portfolio(self.manager)
        self.assertTrue(data["roadmap"]["has_dates"])
        self.assertEqual(data["roadmap"]["lanes"][0]["undated_count"], 0)
        self.assertEqual(len(data["roadmap"]["lanes"][0]["milestones"]), 1)

    def test_attention_is_ranked_by_cost_of_delay(self):
        self.pm1.write({"date_deadline": "2020-01-01"})
        data = self._portfolio(self.manager)
        kinds = [item["kind"] for item in data["attention"]]
        self.assertIn("overdue_milestone", kinds)
        weights = [item["weight"] for item in data["attention"]]
        self.assertEqual(weights, sorted(weights, reverse=True),
                         "attention items must come back ranked")

    def test_no_money_trend_is_fabricated(self):
        """Nothing records historical balances, so the series must be absent
        rather than invented from today's figures."""
        data = self._portfolio(self.manager)
        self.assertIsNone(data["trends"]["money"])

    def test_filters_narrow_the_rows(self):
        data = self._portfolio(self.manager)
        self.assertEqual(len(data["rows"]), 1)
        filtered = self.env["c2p.dashboard"].with_user(self.manager).portfolio_data(
            rag_filter="green")
        self.assertEqual(
            len(filtered["rows"]),
            1 if data["rows"][0]["rag"] == "green" else 0)

    def test_delivery_team_load_counts_open_work(self):
        self._delivery_task(name="A", stage="In Progress")
        self._delivery_task(name="B", stage="To Do")
        data = self.env["c2p.dashboard"].with_user(self.worker).delivery_data()
        names = [row["name"] for row in data["team_load"]]
        self.assertIn(self.worker.name, names)
        row = next(r for r in data["team_load"] if r["name"] == self.worker.name)
        self.assertEqual(row["open"], 2)

    def test_delivery_hygiene_counts_the_four_checks(self):
        data = self.env["c2p.dashboard"].with_user(self.worker).delivery_data()
        labels = [entry["label"] for entry in data["hygiene"]]
        self.assertEqual(labels, ["No assignee", "No deadline", "No milestone",
                                  "Blocked without a reason"])
