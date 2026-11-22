"""The app portal is for the tenant's staff: a portal user is sent to the
customer portal; an internal user gets the page and sees only what their
own rights allow (business data is read as the user)."""
from odoo.tests import HttpCase, tagged

PW = "app-test-pass-1"


@tagged("post_install", "-at_install")
class TestAppPortalAccess(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        field = "group_ids" if "group_ids" in Users._fields else "groups_id"
        portal = cls.env.ref("base.group_portal")
        internal = cls.env.ref("base.group_user")
        cls.portal_user = Users.create({"name": "TEST Portal Customer", "login": "app_portal_user", "password": PW,
                                        field: [(6, 0, [portal.id])]})
        cls.staff = Users.create({"name": "TEST Staff", "login": "app_staff_user", "password": PW,
                                  field: [(6, 0, [internal.id])]})

    def test_portal_user_is_sent_to_the_customer_portal(self):
        self.authenticate("app_portal_user", PW)
        for path in ("/app", "/app/erp", "/app/zaki", "/app/marketplace", "/app/account"):
            resp = self.url_open(path, allow_redirects=False)
            self.assertIn(resp.status_code, (301, 302, 303), path)
            self.assertIn("/my", resp.headers.get("Location", ""), path)

    def test_internal_user_gets_the_page(self):
        self.authenticate("app_staff_user", PW)
        resp = self.url_open("/app", allow_redirects=False)
        self.assertEqual(resp.status_code, 200)

    def test_anonymous_is_sent_to_login(self):
        resp = self.url_open("/app", allow_redirects=False)
        self.assertIn(resp.status_code, (301, 302, 303))
        self.assertIn("/web/login", resp.headers.get("Location", ""))
