import json

from psycopg2 import IntegrityError

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import tagged
from odoo.tests.common import HttpCase
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "faizy")
class TestCareRequestIntake(HttpCase):
    """Submitting the same request twice files one order."""

    def setUp(self):
        super().setUp()
        self.cust = mail_new_test_user(
            self.env, login="intake_cust", name="Intake Customer", groups="base.group_portal"
        )
        self.cust.partner_id.faizy_free_activities = 3  # the plan gate is not what is under test
        self.service = self.env["faizy.service"].search([("active", "=", True)], limit=1) or self.env[
            "faizy.service"
        ].create({"name": "Intake service"})
        self.authenticate("intake_cust", "intake_cust")

    def _post(self, **extra):
        body = {"service_id": self.service.id, "city": "Karachi", "description": "SYNTHETIC intake test"}
        body.update(extra)
        response = self.url_open(
            "/api/care/request", data=json.dumps(body), headers={"Content-Type": "application/json"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        return json.loads(response.text)

    def _orders(self):
        return self.env["faizy.order"].search([("partner_id", "=", self.cust.partner_id.id)])

    def test_same_request_id_returns_the_first_order(self):
        first = self._post(client_request_id="req-1")
        second = self._post(client_request_id="req-1")
        self.assertTrue(first["ok"] and second["ok"])
        self.assertEqual(first["order"]["id"], second["order"]["id"])
        self.assertEqual(len(self._orders()), 1)

    def test_different_request_ids_are_different_errands(self):
        first = self._post(client_request_id="req-a")
        second = self._post(client_request_id="req-b")
        self.assertNotEqual(first["order"]["id"], second["order"]["id"])
        self.assertEqual(len(self._orders()), 2)

    def test_double_tap_without_an_id_is_still_one_order(self):
        first = self._post()
        second = self._post()
        self.assertEqual(first["order"]["id"], second["order"]["id"])
        self.assertEqual(len(self._orders()), 1)

    def test_a_retry_is_not_refused_because_of_its_own_order(self):
        for index in range(15):  # MAX_OPEN_ORDERS
            self.env["faizy.order"].create({
                "title": "SYNTHETIC open %s" % index, "partner_id": self.cust.partner_id.id,
                "service_id": self.service.id, "city": "Karachi", "state": "pending",
            })
        order = self.env["faizy.order"].search([("partner_id", "=", self.cust.partner_id.id)], limit=1)
        order.client_request_id = "req-limit"
        again = self._post(client_request_id="req-limit")
        self.assertTrue(again["ok"], "the retry returns the existing order, not the open-tasks error")
        self.assertEqual(again["order"]["id"], order.id)

    def test_another_customers_request_id_does_not_collide(self):
        other = mail_new_test_user(self.env, login="intake_other", name="Other", groups="base.group_portal")
        other.partner_id.faizy_free_activities = 3
        mine = self._post(client_request_id="shared-id")
        self.authenticate("intake_other", "intake_other")
        theirs = self._post(client_request_id="shared-id")
        self.assertNotEqual(mine["order"]["id"], theirs["order"]["id"])

    def test_form_carries_a_request_token(self):
        page = self.url_open("/care/request")
        self.assertEqual(page.status_code, 200)
        self.assertIn('name="client_request_id"', page.text)

    @mute_logger("odoo.sql_db")
    def test_database_refuses_a_second_order_with_the_same_id(self):
        values = {"title": "SYNTHETIC db", "partner_id": self.cust.partner_id.id,
                  "service_id": self.service.id, "city": "Karachi", "client_request_id": "dup"}
        self.env["faizy.order"].create(values)
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.env["faizy.order"].create(values)
