import base64

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

PNG = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478"
    "9c6360000002000001e221bc330000000049454e44ae426082"
))


@tagged("post_install", "-at_install", "faizy")
class TestEvidenceGate(TransactionCase):
    """An order must not complete, or be billed, without reviewed evidence."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        def mk(login, groups):
            return mail_new_test_user(cls.env, login=login, name=login, groups=groups)

        cls.agent = mk("pilot_agent", "faizy_core.group_faizy_user")
        cls.ops = mk("pilot_ops", "faizy_core.group_faizy_ops")
        cls.manager = mk("pilot_manager", "faizy_core.group_faizy_manager")
        cls.cust_a = mk("pilot_cust_a", "base.group_portal")
        cls.cust_b = mk("pilot_cust_b", "base.group_portal")
        cls.service = cls.env["faizy.service"].search([], limit=1) or cls.env["faizy.service"].create(
            {"name": "Pilot test service"}
        )

    def _order(self, **extra):
        vals = {
            "title": "SYNTHETIC pilot order",
            "partner_id": self.cust_a.partner_id.id,
            "service_id": self.service.id,
            "city": "Karachi",
            "state": "in_progress",
        }
        vals.update(extra)
        return self.env["faizy.order"].create(vals)

    def _complete_refused(self, order, user=None):
        order = order.with_user(user or self.ops)
        with self.assertRaises(UserError):
            order.action_complete()
        self.assertNotEqual(order.sudo().state, "completed")

    # ── the gate ─────────────────────────────────────────────────────────
    def test_complete_without_evidence_is_refused(self):
        order = self._order()
        self._complete_refused(order)

    def test_complete_with_unreviewed_images_is_refused(self):
        order = self._order(proof_image=PNG, purchase_value=100, receipt_image=PNG)
        self.assertEqual(order.evidence_state, "submitted")
        self._complete_refused(order)

    def test_receipt_required_only_when_money_was_spent(self):
        free = self._order(proof_image=PNG)
        free.with_user(self.ops).action_approve_evidence()
        free.with_user(self.ops).action_complete()
        self.assertEqual(free.state, "completed")

        paid = self._order(proof_image=PNG, purchase_value=250)
        with self.assertRaises(UserError):
            paid.with_user(self.ops).action_approve_evidence()  # receipt missing
        self._complete_refused(paid)

    def test_approved_evidence_allows_completion(self):
        order = self._order(proof_image=PNG, receipt_image=PNG, purchase_value=250)
        order.with_user(self.ops).action_approve_evidence()
        self.assertEqual(order.evidence_state, "approved")
        self.assertEqual(order.evidence_reviewer_id, self.ops)
        order.with_user(self.ops).action_complete()
        self.assertEqual(order.state, "completed")

    def test_state_write_cannot_bypass_the_gate(self):
        order = self._order()
        for user in (self.agent, self.ops):
            with self.assertRaises(UserError):
                order.with_user(user).write({"state": "completed"})
        self.assertEqual(order.state, "in_progress")

    def test_no_invoice_when_the_gate_refuses(self):
        order = self._order(purchase_value=100)
        self._complete_refused(order)
        self.assertFalse(order.customer_invoice_id)

    # ── review integrity ─────────────────────────────────────────────────
    def test_client_cannot_set_review_fields_or_context_bypass(self):
        order = self._order(proof_image=PNG)
        with self.assertRaises(AccessError):
            order.with_user(self.ops).write({"evidence_state": "approved"})
        # A client can send any JSON context; only an in-process object passes.
        with self.assertRaises(AccessError):
            order.with_user(self.ops).with_context(faizy_evidence_internal=True).write(
                {"evidence_state": "approved"})
        with self.assertRaises(UserError):
            order.with_user(self.ops).with_context(faizy_gate_passed=True).write({"state": "completed"})
        with self.assertRaises(AccessError):
            self.env["faizy.order"].with_user(self.ops).create({
                "title": "x", "partner_id": self.cust_a.partner_id.id, "service_id": self.service.id,
                "city": "Karachi", "evidence_state": "approved"})

    def test_agent_cannot_approve(self):
        order = self._order(proof_image=PNG)
        with self.assertRaises(AccessError):
            order.with_user(self.agent).action_approve_evidence()

    def test_reject_needs_a_reason_and_blocks_completion(self):
        order = self._order(proof_image=PNG)
        with self.assertRaises(UserError):
            order.with_user(self.ops).action_reject_evidence("   ")
        order.with_user(self.ops).action_reject_evidence("Photo is blurry")
        self.assertEqual(order.evidence_state, "rejected")
        self.assertEqual(order.evidence_reject_reason, "Photo is blurry")
        self._complete_refused(order)

    def test_changing_an_approved_image_sends_it_back_to_review(self):
        order = self._order(proof_image=PNG)
        order.with_user(self.ops).action_approve_evidence()
        order.with_user(self.agent).write({"proof_image": PNG})
        self.assertEqual(order.evidence_state, "submitted")
        self.assertFalse(order.evidence_reviewer_id)
        self._complete_refused(order)

    # ── exception path ───────────────────────────────────────────────────
    def test_exception_needs_manager_and_reason_and_is_logged(self):
        order = self._order()
        with self.assertRaises(AccessError):
            order.with_user(self.ops).action_complete_with_exception("urgent")
        with self.assertRaises(UserError):
            order.with_user(self.manager).action_complete_with_exception("  ")
        order.with_user(self.manager).action_complete_with_exception("Customer confirmed by phone")
        self.assertEqual(order.state, "completed")
        self.assertEqual(order.evidence_exception_by, self.manager)
        self.assertIn("WITHOUT approved evidence", " ".join(order.message_ids.mapped("body")))

    # ── customer visibility (G3) ─────────────────────────────────────────
    def test_customer_cannot_read_image_fields_even_when_approved(self):
        order = self._order(proof_image=PNG, receipt_image=PNG, purchase_value=10)
        for state_action in (None, "approve"):
            if state_action:
                order.with_user(self.ops).action_approve_evidence()
            o = order.with_user(self.cust_a)
            self.assertEqual(o.name, order.name)  # own order is readable
            with self.assertRaises(AccessError):
                o.proof_image
            with self.assertRaises(AccessError):
                o.receipt_image

    def test_visibility_flags_follow_approval(self):
        order = self._order(proof_image=PNG)
        o = order.with_user(self.cust_a)
        self.assertFalse(o.proof_visible)
        order.with_user(self.ops).action_approve_evidence()
        self.assertTrue(order.with_user(self.cust_a).proof_visible)
        self.assertFalse(order.with_user(self.cust_a).receipt_visible)

    def test_other_customer_cannot_see_the_order_at_all(self):
        order = self._order(proof_image=PNG)
        order.with_user(self.ops).action_approve_evidence()
        found = self.env["faizy.order"].with_user(self.cust_b).search([("id", "=", order.id)])
        self.assertFalse(found)


@tagged("post_install", "-at_install", "faizy")
class TestExistingEvidenceMigration(TransactionCase):
    """Orders that already held images before the addon existed keep working."""

    def test_post_init_hook_grandfathers_existing_orders(self):
        from odoo.addons.faizy_pilot.hooks import post_init_hook
        from odoo.addons.faizy_pilot.models.faizy_order import _TOKEN

        customer = mail_new_test_user(
            self.env, login="mig_cust", name="mig_cust", groups="base.group_portal")
        service = self.env["faizy.service"].search([], limit=1) or self.env["faizy.service"].create(
            {"name": "Migration test service"})
        base = {"title": "SYNTHETIC", "partner_id": customer.partner_id.id,
                "service_id": service.id, "city": "Karachi"}
        done = self.env["faizy.order"].create(dict(base, state="completed", proof_image=PNG))
        running = self.env["faizy.order"].create(dict(base, state="in_progress", receipt_image=PNG))
        empty = self.env["faizy.order"].create(dict(base, state="in_progress"))
        # Put them in the pre-install condition: images present, state 'none'.
        (done | running).with_context(faizy_evidence_internal=_TOKEN).write({"evidence_state": "none"})
        self.env.flush_all()

        post_init_hook(self.env)

        self.assertEqual(done.evidence_state, "approved")
        self.assertTrue(done.with_user(customer).proof_visible)
        self.assertEqual(running.evidence_state, "submitted")
        self.assertEqual(empty.evidence_state, "none")
