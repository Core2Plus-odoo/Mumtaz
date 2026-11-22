import base64
import json
from datetime import date, datetime, timedelta
from unittest.mock import patch

from odoo import Command
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval

IN_HOURS = datetime(2026, 11, 3, 8, 0, 0)    # 13:00 Karachi
NOW_PATH = 'odoo.addons.faizy_ai.models.utils.fields.Datetime.now'
HOURS_PATH = 'odoo.addons.faizy_ai.models.routing.within_hours'

PNG = base64.b64encode(bytes.fromhex(
    '89504e470d0a1a0a0000000d4948445200000001000000010806000000'
    '1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082'))


@tagged('post_install', '-at_install')
class TestRouting(TransactionCase):
    """FAIZY HQ05 PR (b): work lands on the right person as an activity,
    closes when done and escalates once when left too long."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        def user(login, *groups):
            return env['res.users'].create({
                'name': login, 'login': login,
                'notification_type': 'inbox',
                'group_ids': [Command.set([env.ref(g).id for g in groups])]})

        cls.ai_user = user('rt_ai', 'faizy_ai.group_ai_agent')
        cls.mashood = user('rt_mashood', 'faizy_ai.group_comms')
        cls.raza = user('rt_raza', 'faizy_core.group_faizy_ops')
        cls.umer = user('rt_umer', 'faizy_core.group_faizy_manager')
        Param = env['ir.config_parameter'].sudo()
        Param.set_param('faizy_ai.care_user_id', cls.mashood.id)
        Param.set_param('faizy_ai.ops_user_id', cls.raza.id)
        Param.set_param('faizy_ai.escalation_user_id', cls.umer.id)

        cls.customer = env['res.partner'].create({'name': 'Hamza', 'phone': '+971 50 123 4567'})
        cls.service = env['faizy.service'].create(
            {'name': 'RT errand', 'code': 'rt_errand', 'consumes_activity': False})
        cls.worker = env['faizy.worker'].create(
            {'name': 'Ali', 'state': 'active', 'phone': '+923001234567', 'city': 'Karachi'})
        cls.agent = env['faizy.ai.agent'].search([('code', '=', 'rabta')])
        cls.agent.user_id = cls.ai_user

    def _acts(self, record, xmlid):
        return record.activity_ids.filtered(
            lambda a: a.activity_type_id == self.env.ref(xmlid))

    def _draft(self, **kw):
        vals = {'subject': 'Reply to Hamza', 'kind': 'customer_message',
                'body': 'Subah bakhair!', 'partner_id': self.customer.id}
        vals.update(kw)
        return self.env['faizy.ai.draft'].with_user(self.ai_user).create(vals)

    def _order(self, **kw):
        vals = {'title': 'Medicines', 'city': 'Karachi', 'partner_id': self.customer.id,
                'service_id': self.service.id}
        vals.update(kw)
        return self.env['faizy.order'].create(vals)

    # ---------------------------------------------------------------- T9, T11, T12
    def test_reply_draft_goes_to_care_and_closes_on_approval(self):
        draft = self._draft()
        acts = self._acts(draft, 'faizy_ai.act_approve_reply')
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts.user_id, self.mashood)
        with patch(NOW_PATH, return_value=IN_HOURS):
            draft.with_user(self.mashood).action_approve()
        # Sending is off: the draft waits to be sent by hand, still care's work.
        self.assertEqual(draft.state, 'to_send')
        self.assertTrue(self._acts(draft, 'faizy_ai.act_approve_reply'))
        draft.with_user(self.mashood).action_mark_sent_manually()
        self.assertFalse(self._acts(draft, 'faizy_ai.act_approve_reply'))

    def test_order_draft_goes_to_ops_not_care(self):
        order = self._order()
        draft = self._draft(kind='order_update', order_id=order.id, subject='Assign Ali',
                            payload=json.dumps({'write': {'worker_id': self.worker.id}}))
        acts = self._acts(draft, 'faizy_ai.act_approve_order')
        self.assertEqual(acts.user_id, self.raza)
        self.assertFalse(self._acts(draft, 'faizy_ai.act_approve_reply'))

    def test_escalation_draft_goes_to_umer(self):
        draft = self._draft(kind='other', subject='Refund request')
        self.assertEqual(self._acts(draft, 'faizy_ai.act_approve_escalation').user_id, self.umer)

    # ---------------------------------------------------------------- T10, T13
    def test_new_order_goes_to_ops_and_closes_on_assign(self):
        order = self._order(priority='1')
        acts = self._acts(order, 'faizy_ai.act_assign_faizy')
        self.assertEqual(acts.user_id, self.raza)
        self.assertTrue(acts.faizy_urgent)
        order.write({'worker_id': self.worker.id})
        order.with_user(self.raza).action_assign()
        self.assertFalse(self._acts(order, 'faizy_ai.act_assign_faizy'))

    def test_sample_orders_are_not_routed(self):
        order = self._order(is_sample=True)
        self.assertFalse(order.activity_ids)

    def test_proof_then_completion_routes_message_to_care(self):
        order = self._order(worker_id=self.worker.id).with_user(self.raza)
        order.action_assign()
        order.action_start()
        order.write({'proof_image': PNG})
        self.assertEqual(self._acts(order, 'faizy_ai.act_review_proof').user_id, self.raza)
        order.action_complete()
        self.assertFalse(self._acts(order, 'faizy_ai.act_review_proof'))
        self.assertEqual(self._acts(order, 'faizy_ai.act_completion_message').user_id,
                         self.mashood)

    def test_inbound_goes_to_care(self):
        rec = self.env['faizy.ai.inbound'].create({'phone': '+971501234567', 'body': 'Salam'})
        self.assertEqual(self._acts(rec, 'faizy_ai.act_handle_inbound').user_id, self.mashood)
        rec.with_user(self.mashood).action_handled()
        self.assertFalse(self._acts(rec, 'faizy_ai.act_handle_inbound'))

    def test_overdue_job_flagged_once(self):
        order = self._order(worker_id=self.worker.id,
                            scheduled_date=datetime.now() - timedelta(hours=3))
        order.with_user(self.raza).action_assign()
        Routing = self.env['faizy.routing']
        Routing._cron_overdue_jobs()
        Routing._cron_overdue_jobs()
        self.assertEqual(len(self._acts(order, 'faizy_ai.act_follow_up_job')), 1)

    # ---------------------------------------------------------------- T14
    def test_overdue_activity_escalates_once(self):
        draft = self._draft()
        act = self._acts(draft, 'faizy_ai.act_approve_reply')
        Routing = self.env['faizy.routing']
        # 3 h after the activity was created (window: 2 h), inside working hours.
        with patch(NOW_PATH, return_value=act.create_date + timedelta(hours=3)), \
                patch(HOURS_PATH, return_value=True):
            self.assertEqual(Routing._cron_escalate(), 1)
            self.assertEqual(Routing._cron_escalate(), 0)
        esc = self._acts(draft, 'faizy_ai.act_approve_escalation')
        self.assertEqual(len(esc), 1)
        self.assertEqual(esc.user_id, self.umer)
        self.assertTrue(act.faizy_escalated)
        self.assertTrue(any('Escalated to' in (m.body or '') for m in draft.message_ids))

    def test_no_escalation_outside_hours(self):
        draft = self._draft()
        act = self._acts(draft, 'faizy_ai.act_approve_reply')
        with patch(NOW_PATH, return_value=act.create_date + timedelta(hours=5)), \
                patch(HOURS_PATH, return_value=False):
            self.assertEqual(self.env['faizy.routing']._cron_escalate(), 0)

    def test_not_escalated_before_window(self):
        draft = self._draft()
        act = self._acts(draft, 'faizy_ai.act_approve_reply')
        with patch(NOW_PATH, return_value=act.create_date + timedelta(hours=1)), \
                patch(HOURS_PATH, return_value=True):
            self.assertEqual(self.env['faizy.routing']._cron_escalate(), 0)

    # ---------------------------------------------------------------- T15
    def test_morning_summary_lands_in_inbox(self):
        self._draft()
        Notification = self.env['mail.notification'].sudo()
        before = Notification.search_count([('res_partner_id', '=', self.mashood.partner_id.id)])
        self.env['faizy.routing']._cron_morning_summary()
        notes = Notification.search([('res_partner_id', '=', self.mashood.partner_id.id)])
        self.assertGreater(len(notes), before)
        self.assertTrue(all(n.notification_type == 'inbox' for n in notes))
        self.assertFalse(self.env['faizy.whatsapp.message'].search_count(
            [('partner_id', '=', self.mashood.partner_id.id)]))

    # ---------------------------------------------------------------- T16
    def test_archived_role_holder_falls_back_to_group_then_umer(self):
        Routing = self.env['faizy.routing']
        backup = self.env['res.users'].create({
            'name': 'rt_backup', 'login': 'rt_backup',
            'group_ids': [Command.set([self.env.ref('faizy_ai.group_comms').id])]})
        self.mashood.active = False
        self.assertEqual(Routing._role_user('care'), backup)
        # No active care member left at all: the escalation owner gets it.
        backup.active = False
        self.assertEqual(Routing._role_user('care'), self.umer)

    # ---------------------------------------------------------------- desks (T1)
    def test_each_person_sees_their_desk(self):
        Menu = self.env['ir.ui.menu']

        def visible(user):
            ids = Menu.with_user(user)._visible_menu_ids()
            return {xid for xid in ('faizy_ai.menu_care_desk', 'faizy_ai.menu_ops_desk',
                                    'faizy_ai.menu_command_centre')
                    if self.env.ref(xid).id in ids}

        self.assertEqual(visible(self.mashood), {'faizy_ai.menu_care_desk'})
        self.assertEqual(visible(self.raza), {'faizy_ai.menu_ops_desk'})
        self.assertEqual(visible(self.umer), {'faizy_ai.menu_care_desk', 'faizy_ai.menu_ops_desk',
                                              'faizy_ai.menu_command_centre'})

    def test_desk_lists_open_for_their_owner(self):
        self._draft()
        self._order()
        desks = {
            self.mashood: ('action_faizy_my_work', 'action_care_replies_waiting',
                           'action_care_to_send', 'action_care_inbound'),
            self.raza: ('action_faizy_my_work', 'action_ops_unassigned', 'action_ops_order_drafts',
                        'action_ops_not_started', 'action_ops_proof_review'),
            self.umer: ('action_cc_escalations', 'action_faizy_all_work'),
        }
        for user, actions in desks.items():
            for xid in actions:
                action = self.env.ref('faizy_ai.%s' % xid).sudo()
                Model = self.env[action.res_model].with_user(user)
                domain = safe_eval(action.domain or '[]', {
                    'uid': user.id, 'context_today': date.today})
                Model.get_views([(False, 'list'), (False, 'form')])
                Model.search_read(domain, ['display_name'], limit=5)
        mine = self.env['mail.activity'].with_user(self.mashood).search(
            [('user_id', '=', self.mashood.id), ('activity_type_id.faizy_route', '=', True)])
        self.assertTrue(mine)
