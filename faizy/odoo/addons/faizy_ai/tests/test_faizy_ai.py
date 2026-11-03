import json
from datetime import datetime
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

IN_HOURS = datetime(2026, 11, 3, 8, 0, 0)    # 13:00 Karachi
OUT_HOURS = datetime(2026, 11, 3, 18, 0, 0)  # 23:00 Karachi
NOW_PATH = 'odoo.addons.faizy_ai.models.utils.fields.Datetime.now'


@tagged('post_install', '-at_install')
class TestFaizyAI(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.g_ai = env.ref('faizy_ai.group_ai_agent')
        cls.g_comms = env.ref('faizy_ai.group_comms')
        cls.g_ops = env.ref('faizy_core.group_faizy_ops')
        cls.g_manager = env.ref('faizy_core.group_faizy_manager')

        def user(login, group):
            return env['res.users'].create({
                'name': login, 'login': login,
                'group_ids': [Command.set([group.id])]})

        cls.ai_user = user('rabta_ai', cls.g_ai)
        cls.mashood = user('mashood_t', cls.g_comms)
        cls.raza = user('raza_t', cls.g_ops)
        cls.umer = user('umer_t', cls.g_manager)
        cls.customer = env['res.partner'].create({'name': 'Hamza', 'phone': '+971 50 123 4567'})
        cls.service = env['faizy.service'].create({'name': 'Monthly medicines', 'code': 'monthly_medicines_t'})
        cls.agent = env['faizy.ai.agent'].search([('code', '=', 'rabta')])
        cls.agent.user_id = cls.ai_user

    def _draft(self, **kw):
        vals = {'subject': 'Reply to Hamza', 'kind': 'customer_message',
                'body': 'Subah bakhair! Abbu ki dawai ka kaam shuru.',
                'partner_id': self.customer.id}
        vals.update(kw)
        return self.env['faizy.ai.draft'].with_user(self.ai_user).create(vals)

    # ---------------------------------------------------------------- guardrails
    def test_ai_cannot_force_state_or_approve(self):
        draft = self._draft(state='executed')
        self.assertEqual(draft.state, 'draft')
        with self.assertRaises(AccessError):
            draft.write({'state': 'approved'})
        with self.assertRaises(AccessError):
            draft.action_approve()

    def test_ai_cannot_touch_orders(self):
        order = self.env['faizy.order'].create({
            'title': 'T', 'city': 'Karachi', 'partner_id': self.customer.id, 'service_id': self.service.id})
        with self.assertRaises(AccessError):
            order.with_user(self.ai_user).write({'state': 'completed'})
        with self.assertRaises(AccessError):
            self.env['faizy.whatsapp.message'].with_user(self.ai_user).create({
                'phone': '+923001234567', 'body': 'x'})

    def test_stale_number_rejected(self):
        with self.assertRaises(ValidationError):
            self._draft(body='WhatsApp karein 0334 272 6048')
        with self.assertRaises(ValidationError):
            self._draft(payload=json.dumps({'note': '+92 335 3043972'}))

    def test_order_update_blocks_complete_and_cancel(self):
        order = self.env['faizy.order'].create({
            'title': 'T', 'city': 'Karachi', 'partner_id': self.customer.id, 'service_id': self.service.id})
        with self.assertRaises(ValidationError):
            self._draft(kind='order_update', order_id=order.id,
                        payload=json.dumps({'action': 'action_complete'}))
        with self.assertRaises(ValidationError):
            self._draft(kind='order_update', order_id=order.id,
                        payload=json.dumps({'write': {'state': 'completed'}}))

    # ---------------------------------------------------------------- approval routing
    def test_customer_message_needs_comms_not_ops(self):
        draft = self._draft()
        with self.assertRaises(AccessError):
            draft.with_user(self.raza).action_approve()
        with patch(NOW_PATH, return_value=IN_HOURS):
            draft.with_user(self.mashood).action_approve()
        self.assertEqual(draft.state, 'executed')
        msg = draft.message_ref_id
        self.assertEqual(msg.state, 'queued')
        self.assertEqual(msg.phone, '+971501234567')
        self.assertEqual(draft.approver_id, self.mashood)

    def test_held_outside_hours_then_released(self):
        draft = self._draft()
        with patch(NOW_PATH, return_value=OUT_HOURS):
            draft.with_user(self.mashood).action_approve()
            self.assertEqual(draft.state, 'approved')
            self.assertFalse(draft.message_ref_id)
            self.env['faizy.ai.draft']._cron_release_held()
            self.assertEqual(draft.state, 'approved')
        with patch(NOW_PATH, return_value=IN_HOURS):
            self.env['faizy.ai.draft']._cron_release_held()
        self.assertEqual(draft.state, 'executed')
        self.assertEqual(draft.message_ref_id.state, 'queued')

    def test_otp_type_refused(self):
        draft = self._draft(payload=json.dumps({'message_type': 'otp'}))
        with patch(NOW_PATH, return_value=IN_HOURS), self.assertRaises(UserError):
            draft.with_user(self.mashood).action_approve()

    def test_order_create_and_update_by_ops(self):
        create = self._draft(
            kind='order_create', subject='Monthly medicines', body='Pharmacy run',
            payload=json.dumps({'service_id': self.service.id, 'city': 'Karachi'}))
        with self.assertRaises(AccessError):
            create.with_user(self.mashood).action_approve()
        create.with_user(self.raza).action_approve()
        order = create.result_order_id
        self.assertEqual(order.state, 'pending')
        self.assertEqual(order.partner_id, self.customer)

        worker = self.env['faizy.worker'].create({'name': 'Ali', 'state': 'active', 'phone': '+923001234567', 'city': 'Karachi'})
        update = self._draft(
            kind='order_update', order_id=order.id, subject='Assign Ali',
            payload=json.dumps({'write': {'worker_id': worker.id}, 'action': 'action_assign'}))
        update.with_user(self.raza).action_approve()
        self.assertEqual(order.state, 'assigned')
        self.assertEqual(order.worker_id, worker)

    def test_failed_execution_leaves_draft_waiting(self):
        order = self.env['faizy.order'].create({
            'title': 'T', 'city': 'Karachi', 'partner_id': self.customer.id, 'service_id': self.service.id})
        update = self._draft(kind='order_update', order_id=order.id,
                             payload=json.dumps({'action': 'action_assign'}))
        with self.assertRaises(UserError):
            with self.env.cr.savepoint():
                update.with_user(self.raza).action_approve()
        update.invalidate_recordset()
        self.assertEqual(update.state, 'draft')

    def test_manager_can_approve_anything_and_reject_needs_reason(self):
        draft = self._draft()
        with self.assertRaises(UserError):
            draft.with_user(self.umer).action_reject()
        draft.with_user(self.umer).write({'reject_reason': 'Wrong tone'})
        draft.with_user(self.umer).action_reject()
        self.assertEqual(draft.state, 'rejected')

    # ---------------------------------------------------------------- inbound + digest
    def test_inbound_payload_logged_once_and_matched(self):
        payload = {'entry': [{'changes': [{'value': {'messages': [{
            'id': 'wamid.1', 'from': '971501234567', 'type': 'text',
            'text': {'body': 'Abbu ki dawai?'}}]}}]}]}
        Inbound = self.env['faizy.ai.inbound']
        first = Inbound.process_whatsapp_payload(payload)
        again = Inbound.process_whatsapp_payload(payload)
        self.assertEqual(len(first), 1)
        self.assertFalse(again)
        self.assertEqual(first.partner_id, self.customer)
        self.assertEqual(first.state, 'new')

    def test_digest_shape(self):
        digest = self.env['faizy.ai.draft'].with_user(self.ai_user).get_digest()
        for key in ('open_orders', 'overdue_orders', 'completed_without_proof',
                    'pending_drafts', 'unhandled_inbound', 'failed_whatsapp_messages'):
            self.assertIn(key, digest)
