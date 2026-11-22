import base64

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

# 1x1 PNG, enough to satisfy an Image field.
PNG = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
    )
)


@tagged("post_install", "-at_install", "faizy")
class TestHQ05Guards(TransactionCase):
    """FAIZY HQ05 PR (a): the guards that must hold before Mashood and Raza
    get logins. Each test names the HQ05 acceptance test it covers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # Agent = customer care (Mashood's base group, without Operations).
        cls.agent = mail_new_test_user(
            env, login="hq05_agent", name="Agent", groups="faizy_core.group_faizy_user"
        )
        cls.ops = mail_new_test_user(
            env, login="hq05_ops", name="Ops", groups="faizy_core.group_faizy_ops"
        )
        cls.manager = mail_new_test_user(
            env, login="hq05_mgr", name="Manager", groups="faizy_core.group_faizy_manager"
        )
        cls.customer = env["res.partner"].create(
            {"name": "Hamza", "phone": "+971 50 123 4567"}
        )
        cls.service = env["faizy.service"].create(
            {"name": "HQ05 errand", "code": "hq05_errand", "consumes_activity": False}
        )
        cls.worker = env["faizy.worker"].create(
            {"name": "Ali", "state": "active", "phone": "+923001234567", "city": "Karachi"}
        )
        cls.Queue = env["faizy.whatsapp.message"]
        cls.Param = env["ir.config_parameter"].sudo()

    def _order(self, **kw):
        vals = {
            "title": "Medicines",
            "city": "Karachi",
            "partner_id": self.customer.id,
            "service_id": self.service.id,
            "worker_id": self.worker.id,
        }
        vals.update(kw)
        return self.env["faizy.order"].create(vals)

    def _queued(self):
        return self.Queue.search_count([("state", "=", "queued")])

    # ── S1 / T2: customer care cannot move orders ───────────────────────

    def test_agent_cannot_run_order_actions(self):
        order = self._order()
        for action in (
            "action_confirm", "action_assign", "action_start",
            "action_complete", "action_cancel", "action_reset_to_pending",
        ):
            with self.assertRaises(AccessError, msg=action):
                getattr(order.with_user(self.agent), action)()
        self.assertEqual(order.state, "pending")

    def test_agent_cannot_write_state_or_assignment(self):
        order = self._order()
        with self.assertRaises(AccessError):
            order.with_user(self.agent).write({"state": "cancelled"})
        with self.assertRaises(AccessError):
            order.with_user(self.agent).write({"worker_id": False})
        with self.assertRaises(AccessError):
            order.with_user(self.agent).write({"purchase_value": 999})

    def test_agent_can_edit_description_only(self):
        order = self._order()
        order.with_user(self.agent).write({"description": "Ammi prefers mornings"})
        self.assertEqual(order.description, "Ammi prefers mornings")

    def test_agent_cannot_create_orders_directly(self):
        with self.assertRaises(AccessError):
            self.env["faizy.order"].with_user(self.agent).create(
                {
                    "title": "x",
                    "city": "Karachi",
                    "partner_id": self.customer.id,
                    "service_id": self.service.id,
                }
            )

    def test_ops_runs_the_whole_flow(self):
        order = self._order().with_user(self.ops)
        order.action_assign()
        order.action_start()
        order.write({"proof_image": PNG})
        order.action_complete()
        self.assertEqual(order.state, "completed")

    # ── S2 / T13: completion needs evidence ─────────────────────────────

    def test_completion_refused_without_proof(self):
        order = self._order(state="in_progress")
        with self.assertRaises(UserError):
            order.with_user(self.ops).action_complete()
        self.assertEqual(order.state, "in_progress")

    def test_completion_refused_without_receipt_when_money_spent(self):
        order = self._order(state="in_progress", purchase_value=4200, proof_image=PNG)
        with self.assertRaises(UserError):
            order.with_user(self.ops).action_complete()
        order.write({"receipt_image": PNG})
        order.with_user(self.ops).action_complete()
        self.assertEqual(order.state, "completed")
        # Operations has no Accounting rights, yet the draft invoice is made.
        self.assertTrue(order.customer_invoice_id)
        self.assertEqual(order.customer_invoice_id.state, "draft")

    def test_completion_cannot_bypass_the_button(self):
        order = self._order(state="in_progress")
        with self.assertRaises(UserError):
            order.with_user(self.ops).write({"state": "completed"})
        self.assertEqual(order.state, "in_progress")

    # ── S3 / T17, T19: WhatsApp containment ─────────────────────────────

    def test_sending_is_off_by_default(self):
        self.assertFalse(self.Param.get_param("faizy.whatsapp_send_mode"))
        self.assertFalse(self.Queue._faizy_sending_enabled())

    def test_order_flow_queues_nothing_while_off(self):
        before = self._queued()
        order = self._order().with_user(self.ops)
        order.action_assign()
        order.action_start()
        order.write({"proof_image": PNG})
        order.action_complete()
        self.assertEqual(self._queued(), before)
        notes = order.message_ids.mapped("body")
        self.assertTrue(any("WhatsApp sending is switched off" in (b or "") for b in notes))

    def test_direct_create_is_held_not_queued(self):
        msg = self.Queue.sudo().create(
            {"phone": "+923001234567", "body": "x", "message_type": "generic"}
        )
        self.assertEqual(msg.state, "held")

    def test_cron_sends_nothing_while_off(self):
        self.Param.set_param("faizy.whatsapp_send_mode", "on")
        msg = self.Queue.sudo().create(
            {"phone": "+923001234567", "body": "x", "message_type": "generic"}
        )
        self.assertEqual(msg.state, "queued")
        self.Param.set_param("faizy.whatsapp_send_mode", "off")
        self.Queue._cron_send_queued()
        msg.invalidate_recordset()
        self.assertEqual(msg.state, "queued")
        self.assertEqual(msg.attempts, 0)
        with self.assertRaises(UserError):
            msg.action_send()

    def test_order_flow_queues_when_switched_on(self):
        self.Param.set_param("faizy.whatsapp_send_mode", "on")
        before = self._queued()
        self._order().with_user(self.ops).action_assign()
        self.assertGreater(self._queued(), before)

    # ── S4 / T3: document files are Operations-only ─────────────────────

    def test_agent_sees_document_but_not_file_or_notes(self):
        doc = self.env["faizy.document"].create(
            {
                "name": "Ammi CNIC",
                "doc_type": "cnic",
                "partner_id": self.customer.id,
                "attachment": PNG,
                "attachment_name": "cnic.png",
                "notes": "Renewal at NADRA Gulshan",
            }
        )
        as_agent = doc.with_user(self.agent)
        self.assertEqual(as_agent.read(["name", "expiry_state"])[0]["name"], "Ammi CNIC")
        for field in ("attachment", "attachment_name", "notes", "reference"):
            with self.assertRaises(AccessError, msg=field):
                as_agent.read([field])
        # The stored file itself, fetched as an attachment record.
        att = self.env["ir.attachment"].sudo().search(
            [("res_model", "=", "faizy.document"), ("res_id", "=", doc.id),
             ("res_field", "=", "attachment")]
        )
        self.assertTrue(att)
        with self.assertRaises(AccessError):
            att.with_user(self.agent).read(["datas"])
        # Operations still reads all of it.
        self.assertTrue(doc.with_user(self.ops).read(["attachment"])[0]["attachment"])

    # ── S6 / T4, T5: no money movement, no deletes below Manager ────────

    def test_ops_cannot_create_wallet_transactions(self):
        with self.assertRaises(AccessError):
            self.env["faizy.wallet.transaction"].with_user(self.ops).create(
                {
                    "partner_id": self.customer.id,
                    "txn_type": "adjustment",
                    "amount": 100,
                    "currency_id": self.env.company.currency_id.id,
                }
            )

    def test_ops_cannot_delete(self):
        order = self._order()
        doc = self.env["faizy.document"].create(
            {"name": "Passport", "partner_id": self.customer.id}
        )
        with self.assertRaises(AccessError):
            order.with_user(self.ops).unlink()
        with self.assertRaises(AccessError):
            doc.with_user(self.ops).unlink()
        # Archiving is the way: documents carry `active`.
        doc.with_user(self.ops).write({"active": False})
        self.assertFalse(doc.active)

    def test_manager_can_still_delete(self):
        order = self._order()
        order.with_user(self.manager).unlink()
        self.assertFalse(order.exists())
