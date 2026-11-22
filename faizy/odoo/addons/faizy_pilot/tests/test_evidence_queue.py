import base64

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import TransactionCase, tagged

PNG = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478"
    "9c6360000002000001e221bc330000000049454e44ae426082"
))


@tagged("post_install", "-at_install", "faizy")
class TestEvidenceQueue(TransactionCase):
    """The review desk shows what is waiting and is for reviewers only."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ops = mail_new_test_user(cls.env, login="q_ops", name="q_ops", groups="faizy_core.group_faizy_ops")
        cls.agent = mail_new_test_user(
            cls.env, login="q_agent", name="q_agent", groups="faizy_core.group_faizy_user")
        cust = mail_new_test_user(cls.env, login="q_cust", name="q_cust", groups="base.group_portal")
        service = cls.env["faizy.service"].search([], limit=1) or cls.env["faizy.service"].create(
            {"name": "Queue test"})
        base = {"title": "SYNTHETIC", "partner_id": cust.partner_id.id, "service_id": service.id,
                "city": "Karachi", "state": "in_progress"}
        cls.waiting = cls.env["faizy.order"].create(dict(base, proof_image=PNG))
        cls.empty = cls.env["faizy.order"].create(dict(base))

    def test_default_filter_lists_only_orders_waiting_for_review(self):
        action = self.env.ref("faizy_pilot.action_faizy_order_evidence")
        self.assertEqual(action.res_model, "faizy.order")
        found = self.env["faizy.order"].with_user(self.ops).search([("evidence_state", "=", "submitted")])
        self.assertIn(self.waiting, found)
        self.assertNotIn(self.empty, found)

    def test_menu_is_for_reviewers_only(self):
        menu = self.env.ref("faizy_pilot.menu_faizy_evidence_review")
        self.assertIn(self.env.ref("faizy_core.group_faizy_ops"), menu.group_ids)
        visible = self.env["ir.ui.menu"].with_user(self.ops)._visible_menu_ids()
        self.assertIn(menu.id, visible)
        self.assertNotIn(menu.id, self.env["ir.ui.menu"].with_user(self.agent)._visible_menu_ids())

    def test_views_load(self):
        for xmlid in ("view_faizy_order_evidence_list", "view_faizy_order_evidence_search"):
            view = self.env.ref("faizy_pilot." + xmlid)
            self.env["faizy.order"].with_user(self.ops).get_view(view.id, view.type)
