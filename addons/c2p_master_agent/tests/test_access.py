"""The master agent is for its group only.

It sends pipeline, receivables and staffing summaries to a language model and
creates or assigns project tasks from the reply, so who may reach it is the
control that matters. Until 24 Nov 2026 the access list granted it to every
internal user.
"""
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMasterAgentAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        field = "group_ids" if "group_ids" in Users._fields else "groups_id"
        internal = cls.env.ref("base.group_user").id
        cls.group = cls.env.ref("c2p_master_agent.group_c2p_master_agent_user")
        cls.staff = Users.create({"name": "TEST Staff", "login": "agent_staff",
                                  field: [(6, 0, [internal])]})
        cls.member = Users.create({"name": "TEST Owner", "login": "agent_owner",
                                   field: [(6, 0, [internal, cls.group.id])]})
        cls.Agent = cls.env["c2p.master.agent"]

    def test_an_ordinary_employee_cannot_open_the_agent(self):
        with self.assertRaises(AccessError):
            self.Agent.with_user(self.staff).create({})

    def test_the_entry_point_refuses_a_non_member_on_its_own(self):
        """Independent of the access list, which is one CSV line from reopening."""
        with self.assertRaises(AccessError):
            self.Agent.with_user(self.staff)._check_agent_access()

    def test_a_non_member_cannot_send_on_a_record_someone_else_made(self):
        agent = self.Agent.create({"command": "Assign all unassigned tasks"})
        with patch.object(type(self.Agent), "_call_ollama") as llm:
            with self.assertRaises(AccessError):
                agent.with_user(self.staff).action_send()
            llm.assert_not_called()

    def test_the_access_list_no_longer_names_every_internal_user(self):
        model = self.env["ir.model"]._get("c2p.master.agent")
        groups = self.env["ir.model.access"].search(
            [("model_id", "=", model.id)]).mapped("group_id")
        self.assertEqual(groups, self.group)

    def test_a_member_can_use_the_agent(self):
        agent = self.Agent.with_user(self.member).create({"command": "Briefing"})
        cls = type(self.Agent)
        with patch.object(cls, "_get_system_context", return_value={}), \
                patch.object(cls, "_call_ollama", return_value="All quiet."):
            agent.action_send()
        self.assertIn("All quiet.", agent.conversation)
