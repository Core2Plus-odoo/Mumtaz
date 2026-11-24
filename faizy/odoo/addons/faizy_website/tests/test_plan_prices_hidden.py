import importlib.util
import os

from odoo.tests import tagged
from odoo.tests.common import HttpCase

PARAM = "faizy.show_plan_prices"
MIGRATION = os.path.join(
    os.path.dirname(__file__), "..", "..", "faizy_core", "migrations", "19.0.1.26.0", "post-service-description.py"
)


@tagged("post_install", "-at_install", "faizy_website")
class TestPlanPricesHidden(HttpCase):
    """No plan price or plan number reaches the public until Umer approves them in writing."""

    def _body(self, url):
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200, url)
        return response.text

    def _set(self, value):
        self.env["ir.config_parameter"].sudo().set_param(PARAM, value)
        self.env.cr.flush()

    def test_prices_are_hidden_by_default(self):
        self.assertFalse(self.env["faizy.plan"].prices_public())
        for url in ("/", "/pricing", "/start?plan=standard"):
            body = self._body(url)
            for forbidden in ("1,999", "per month", "Extra activities", "activities a month", "Show prices in"):
                self.assertNotIn(forbidden, body, f"{forbidden!r} on {url}")
        self.assertIn("Price confirmed with you on WhatsApp", self._body("/pricing"))

    def test_plan_lines_with_numbers_are_hidden_but_the_rest_stay(self):
        plan = self.env.ref("faizy_core.plan_lite")
        names = plan.public_features().mapped("name")
        self.assertNotIn("10 activities a month", names)
        self.assertNotIn("Up to 2 family members", names)
        self.assertIn("WhatsApp booking and updates", names)

    def test_anything_but_on_means_hidden(self):
        for value in ("off", "true", "1", ""):
            self._set(value)
            self.assertFalse(self.env["faizy.plan"].prices_public(), value)

    def test_prices_return_when_a_manager_turns_them_on(self):
        self._set("on")
        self.assertTrue(self.env["faizy.plan"].prices_public())
        body = self._body("/pricing")
        self.assertIn("per month", body)
        self.assertIn("activities a month", self.env.ref("faizy_core.plan_lite").public_features().mapped("name")[0])

    def test_migration_removes_the_platform_fee_text_only_when_unedited(self):
        spec = importlib.util.spec_from_file_location("faizy_service_migration", os.path.abspath(MIGRATION))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        service = self.env.ref("faizy_core.service_product_request")
        service.description = module.OLD
        module.migrate(self.env.cr, "19.0.1.24.0")
        self.assertEqual(service.description, module.NEW)
        service.description = "Edited by marketing, 5% is mentioned here."
        module.migrate(self.env.cr, "19.0.1.24.0")
        self.assertEqual(service.description, "Edited by marketing, 5% is mentioned here.")
