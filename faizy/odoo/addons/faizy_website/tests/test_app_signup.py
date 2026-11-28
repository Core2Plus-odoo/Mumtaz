import json

from odoo.tests import tagged
from odoo.tests.common import HttpCase

PARAM = "faizy.app_signup"


@tagged("post_install", "-at_install", "faizy")
class TestAppSignup(HttpCase):
    """POST /api/care/signup: off by default, never attaches to an existing customer."""

    BODY = {
        "name": "SYNTHETIC App Customer",
        "phone": "+971500000001",
        "email": "synthetic.app@example.com",
        "password": "synthetic-pass-1",
        "country_code": "AE",
    }

    def _post(self, **override):
        body = dict(self.BODY, **override)
        response = self.url_open(
            "/api/care/signup", data=json.dumps(body), headers={"Content-Type": "application/json"}
        )
        return response.status_code, json.loads(response.text)

    def _on(self):
        self.env["ir.config_parameter"].sudo().set_param(PARAM, "on")

    def _users(self):
        return self.env["res.users"].with_context(active_test=False).search([("login", "=", self.BODY["email"])])

    def test_closed_unless_switched_on(self):
        status, data = self._post()
        self.assertEqual(status, 403)
        self.assertEqual(data["error"], "signup_closed")
        self.assertFalse(self._users())

    def test_creates_a_portal_customer_who_can_log_in(self):
        self._on()
        status, data = self._post()
        self.assertEqual(status, 200, data)
        user = self._users()
        self.assertEqual(len(user), 1)
        self.assertTrue(user.has_group("base.group_portal"))
        self.assertFalse(user.has_group("base.group_user"))
        self.assertTrue(user.partner_id.is_faizy_customer)
        self.assertEqual(user.partner_id.phone, self.BODY["phone"])
        self.assertEqual(user.partner_id.country_id.code, "AE")
        self.assertEqual(data["partner"]["id"], user.partner_id.id)
        self.authenticate(self.BODY["email"], self.BODY["password"])
        home = self.url_open("/api/care/home")
        self.assertEqual(home.status_code, 200, home.text)
        self.assertEqual(json.loads(home.text)["partner"]["id"], user.partner_id.id)

    def test_refuses_a_phone_already_on_file(self):
        self._on()
        existing = self.env["res.partner"].create(
            {"name": "SYNTHETIC Existing", "phone": self.BODY["phone"], "is_faizy_customer": True}
        )
        status, data = self._post()
        self.assertEqual(status, 409)
        self.assertEqual(data["error"], "already_registered")
        self.assertFalse(self._users())
        self.assertFalse(existing.user_ids)

    def test_refuses_an_email_already_on_file(self):
        self._on()
        self._post()
        status, data = self._post(phone="+971500000002")
        self.assertEqual(status, 409)
        self.assertEqual(len(self._users()), 1)

    def test_validates_the_body(self):
        self._on()
        status, data = self._post(name=" ", email="not-an-email", password="short", phone="")
        self.assertEqual(status, 400)
        self.assertEqual(set(data["errors"]), {"name", "phone", "email", "password"})
        self.assertFalse(self._users())
