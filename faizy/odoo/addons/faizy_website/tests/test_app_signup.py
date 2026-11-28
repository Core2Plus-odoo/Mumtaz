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

    def test_sixth_attempt_from_one_address_in_an_hour_is_refused(self):
        self._on()
        for n in range(5):
            status, data = self._post(email="not-an-email")
            self.assertEqual(status, 400, n)
        status, data = self._post()
        self.assertEqual(status, 429)
        self.assertEqual(data["error"], "too_many_attempts")
        self.assertFalse(self._users())

    def test_attempts_are_not_counted_while_sign_up_is_closed(self):
        for n in range(7):
            self._post()
        self.assertFalse(self.env["faizy.api.throttle"].sudo().search_count([]))

    def test_old_attempts_are_cleaned_up(self):
        Throttle = self.env["faizy.api.throttle"].sudo()
        row = Throttle.create({"scope": "signup", "key": "203.0.113.9"})
        self.env.cr.execute(
            "UPDATE faizy_api_throttle SET create_date = now() - interval '2 days' WHERE id = %s", [row.id]
        )
        Throttle.invalidate_model()
        Throttle._gc_attempts()
        self.assertFalse(row.exists())


@tagged("post_install", "-at_install", "faizy")
class TestAppApiCarriesNoPlanPrices(HttpCase):
    """The service catalogue the app shows before a request carries no price."""

    def test_request_options_have_no_price_fields(self):
        from odoo.addons.mail.tests.common import mail_new_test_user

        mail_new_test_user(self.env, login="noprice_cust", name="SYNTHETIC No Price", groups="base.group_portal")
        self.authenticate("noprice_cust", "noprice_cust")
        response = self.url_open("/api/care/request/options")
        self.assertEqual(response.status_code, 200, response.text)

        def keys(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    yield key
                    yield from keys(value)
            elif isinstance(node, list):
                for item in node:
                    yield from keys(item)

        for key in set(keys(json.loads(response.text))):
            for forbidden in ("price", "amount", "fee", "cost"):
                self.assertNotIn(forbidden, key.lower())
