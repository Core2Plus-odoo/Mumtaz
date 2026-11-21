"""The command centre's data is for its group only, whichever way it is
called (the client action or a direct RPC)."""
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCommandCenterAccess(TransactionCase):

    def test_a_user_outside_the_group_is_refused(self):
        Users = self.env["res.users"].with_context(no_reset_password=True)
        field = "group_ids" if "group_ids" in Users._fields else "groups_id"
        staff = Users.create({"name": "TEST Staff", "login": "cc_staff",
                              field: [(6, 0, [self.env.ref("base.group_user").id])]})
        with self.assertRaises(AccessError):
            self.env["c2p.command.center"].with_user(staff).get_data()

    def test_a_member_gets_the_sections(self):
        Users = self.env["res.users"].with_context(no_reset_password=True)
        field = "group_ids" if "group_ids" in Users._fields else "groups_id"
        member = Users.create({"name": "TEST Owner", "login": "cc_owner",
                               field: [(6, 0, [self.env.ref("base.group_user").id,
                                               self.env.ref("c2p_command_center.group_c2p_command_center").id])]})
        data = self.env["c2p.command.center"].with_user(member).get_data()
        self.assertIn("kpis", data)
        self.assertIn("generated_at", data)
