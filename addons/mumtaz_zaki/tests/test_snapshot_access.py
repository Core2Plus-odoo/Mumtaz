"""The finance snapshot is served to accounting users only."""
import json

from odoo.tests import HttpCase, tagged

PW = "zaki-test-pass-1"


@tagged("post_install", "-at_install")
class TestZakiSnapshotAccess(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        field = "group_ids" if "group_ids" in Users._fields else "groups_id"
        cls.portal_user = Users.create({"name": "TEST Portal", "login": "zaki_portal", "password": PW,
                                        field: [(6, 0, [cls.env.ref("base.group_portal").id])]})
        cls.staff = Users.create({"name": "TEST Staff", "login": "zaki_staff", "password": PW,
                                  field: [(6, 0, [cls.env.ref("base.group_user").id])]})
        cls.accountant = Users.create({"name": "TEST Accountant", "login": "zaki_accountant", "password": PW,
                                       field: [(6, 0, [cls.env.ref("base.group_user").id,
                                                       cls.env.ref("account.group_account_invoice").id])]})

    def _snapshot(self):
        resp = self.url_open("/zaki/api/snapshot", data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": {}}),
                             headers={"Content-Type": "application/json"})
        return resp.json()

    def test_portal_and_plain_staff_are_refused(self):
        for login in ("zaki_portal", "zaki_staff"):
            self.authenticate(login, PW)
            out = self._snapshot()
            self.assertIn("error", out, login)
            self.assertIn("accounting users only", json.dumps(out), login)

    def test_accountant_gets_the_snapshot(self):
        self.authenticate("zaki_accountant", PW)
        out = self._snapshot()
        self.assertIn("result", out, out)
        self.assertIsInstance(out["result"], dict)
