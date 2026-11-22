"""The role portals are for internal users; a portal (share) user is sent to
the customer portal before any figure is read."""
from odoo.tests import HttpCase, tagged

PW = "routing-test-pass-1"


@tagged("post_install", "-at_install")
class TestPortalRoutingAccess(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        field = "group_ids" if "group_ids" in Users._fields else "groups_id"
        cls.portal_user = Users.create({"name": "TEST Portal Customer", "login": "routing_portal_user", "password": PW,
                                        field: [(6, 0, [cls.env.ref("base.group_portal").id])]})
        cls.staff = Users.create({"name": "TEST Staff", "login": "routing_staff_user", "password": PW,
                                  field: [(6, 0, [cls.env.ref("base.group_user").id])]})

    def test_portal_user_is_sent_to_the_customer_portal(self):
        self.authenticate("routing_portal_user", PW)
        for path in ("/mumtaz/portal/admin", "/mumtaz/portal/erp", "/mumtaz/portal/zaki", "/mumtaz/portal/marketplace"):
            resp = self.url_open(path, allow_redirects=False)
            self.assertIn(resp.status_code, (301, 302, 303), path)
            self.assertIn("/my", resp.headers.get("Location", ""), path)

    def test_internal_user_without_a_portal_role_is_sent_to_the_backend(self):
        self.authenticate("routing_staff_user", PW)
        resp = self.url_open("/mumtaz/portal/admin", allow_redirects=False)
        self.assertIn(resp.status_code, (301, 302, 303))
        self.assertIn("/web", resp.headers.get("Location", ""))
