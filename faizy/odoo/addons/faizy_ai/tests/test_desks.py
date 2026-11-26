"""§25: leads are work, checklists travel with the item, My desk shows the numbers."""
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.faizy_ai.models.routing import (
    CHECKLISTS, T_LEAD_FOLLOW_UP, T_LEAD_QUALIFY, T_REPLY,
)


@tagged('post_install', '-at_install')
class TestDesks(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        def user(login, *groups):
            return env['res.users'].create({
                'name': login, 'login': login, 'notification_type': 'inbox',
                'group_ids': [Command.set([env.ref(g).id for g in groups])]})

        cls.ai_user = user('dk_ai', 'faizy_ai.group_ai_agent')
        cls.mashood = user('dk_mashood', 'faizy_ai.group_comms')
        cls.raza = user('dk_raza', 'faizy_core.group_faizy_ops')
        cls.umer = user('dk_umer', 'faizy_core.group_faizy_manager')
        Param = env['ir.config_parameter'].sudo()
        Param.set_param('faizy_ai.care_user_id', cls.mashood.id)
        Param.set_param('faizy_ai.ops_user_id', cls.raza.id)
        Param.set_param('faizy_ai.escalation_user_id', cls.umer.id)
        cls.customer = env['res.partner'].create({'name': 'Hamza', 'phone': '+971 50 123 4567'})
        cls.agent = env['faizy.ai.agent'].search([('code', '=', 'rabta')])
        cls.agent.user_id = cls.ai_user

    def _acts(self, record, xmlid):
        return record.activity_ids.filtered(lambda a: a.activity_type_id == self.env.ref(xmlid))

    def _lead(self, user=None, **kw):
        vals = {'name': 'Family in Karachi, father needs medicines', 'type': 'lead',
                'faizy_family_city': 'karachi', 'faizy_expat_country': 'ae'}
        vals.update(kw)
        return self.env['crm.lead'].with_user(user or self.umer).create(vals)

    # ---------------------------------------------------------------- R13: leads are work
    def test_lead_without_a_salesperson_goes_to_care_with_a_checklist(self):
        # An API client (or an import) that sets no salesperson: care gets it.
        lead = self._lead(user_id=False)
        self.assertEqual(lead.user_id, self.mashood)
        act = self._acts(lead, T_LEAD_QUALIFY)
        self.assertEqual(len(act), 1)
        self.assertEqual(act.user_id, self.mashood)
        self.assertEqual(act.date_deadline, fields.Date.context_today(lead))
        self.assertIn('Checklist', act.note)
        self.assertIn(CHECKLISTS[T_LEAD_QUALIFY][0], act.note)

    def test_lead_keeps_its_salesperson_and_the_item_follows_a_reassignment(self):
        lead = self._lead(user_id=self.raza.id)
        self.assertEqual(self._acts(lead, T_LEAD_QUALIFY).user_id, self.raza)
        lead.write({'user_id': self.mashood.id})
        self.assertEqual(self._acts(lead, T_LEAD_QUALIFY).user_id, self.mashood)
        # Handing a lead to an AI agent is not an assignment: it comes back to care.
        lead.write({'user_id': self.ai_user.id})
        self.assertEqual(lead.user_id, self.mashood)
        self.assertEqual(self._acts(lead, T_LEAD_QUALIFY).user_id, self.mashood)
        # A lead created for an AI agent lands on care too.
        bounced = self._lead(user_id=self.ai_user.id)
        self.assertEqual(bounced.user_id, self.mashood)

    def test_qualified_closes_qualify_and_opens_follow_up_due_tomorrow(self):
        lead = self._lead()
        lead.write({'stage_id': self.env.ref('crm.stage_lead2').id})
        self.assertFalse(self._acts(lead, T_LEAD_QUALIFY))
        follow = self._acts(lead, T_LEAD_FOLLOW_UP)
        self.assertEqual(follow.user_id, self.umer)
        self.assertEqual(follow.date_deadline, fields.Date.context_today(lead) + timedelta(days=1))
        lead.action_set_won()
        self.assertFalse(lead.activity_ids.filtered(lambda a: a.activity_type_id.faizy_route))

    def test_lost_lead_closes_its_items(self):
        lead = self._lead(user_id=self.mashood.id)
        lead.with_user(self.mashood).action_set_lost()
        self.assertFalse(lead.activity_ids.filtered(lambda a: a.activity_type_id.faizy_route))

    # ---------------------------------------------------------------- CRM rights follow the desks
    def test_care_and_ops_open_their_own_leads_only_and_the_manager_sees_all(self):
        mine = self._lead(user_id=self.mashood.id)
        theirs = self._lead(user_id=self.raza.id)
        self.assertEqual(mine.with_user(self.mashood).name, mine.name)
        with self.assertRaises(AccessError):
            theirs.with_user(self.mashood).read(['name'])
        self.assertEqual(theirs.with_user(self.raza).name, theirs.name)
        self.assertEqual(len((mine | theirs).with_user(self.umer).read(['name'])), 2)
        # The AI agent group has no CRM right at all.
        with self.assertRaises(AccessError):
            self.env['crm.lead'].with_user(self.ai_user).search([])

    def test_desk_menus_carry_leads_and_kpis(self):
        Menu = self.env['ir.ui.menu']
        care = Menu.with_user(self.mashood)._visible_menu_ids()
        ops = Menu.with_user(self.raza)._visible_menu_ids()
        for xid in ('menu_care_leads', 'menu_care_kpis'):
            self.assertIn(self.env.ref('faizy_ai.%s' % xid).id, care)
        for xid in ('menu_ops_leads', 'menu_ops_kpis'):
            self.assertIn(self.env.ref('faizy_ai.%s' % xid).id, ops)
        self.assertNotIn(self.env.ref('faizy_ai.menu_ops_kpis').id, care)
        self.assertIn(self.env.ref('faizy_ai.menu_cc_kpis').id,
                      Menu.with_user(self.umer)._visible_menu_ids())

    # ---------------------------------------------------------------- checklists
    def test_checklists_fill_empty_notes_and_never_overwrite(self):
        Routing = self.env['faizy.routing']
        for xmlid in CHECKLISTS:
            self.assertTrue(self.env.ref(xmlid).default_note, xmlid)
        reply = self.env.ref(T_REPLY)
        reply.default_note = '<p>Umer wrote this</p>'
        self.assertEqual(Routing._apply_checklists(), 0)
        self.assertIn('Umer wrote this', reply.default_note)
        draft = self.env['faizy.ai.draft'].with_user(self.ai_user).create({
            'subject': 'Reply', 'kind': 'customer_message', 'body': 'Salam',
            'partner_id': self.customer.id})
        self.assertIn('Umer wrote this', self._acts(draft, T_REPLY).note)

    # ---------------------------------------------------------------- My desk
    def test_my_desk_counts_waiting_done_and_leads(self):
        draft = self.env['faizy.ai.draft'].with_user(self.ai_user).create({
            'subject': 'Reply', 'kind': 'customer_message', 'body': 'Salam',
            'partner_id': self.customer.id})
        self._lead(user_id=self.mashood.id)
        desk = self.env['faizy.my.desk'].with_user(self.mashood).create({})
        self.assertEqual(desk.work_open, 2)
        self.assertEqual(desk.work_due_today, 2)
        self.assertEqual(desk.work_overdue, 0)
        self.assertEqual(desk.leads_mine, 1)
        self.assertEqual(desk.leads_waiting, 1)
        self.assertEqual(desk.done_today, 0)
        self.assertFalse(desk.is_manager)

        draft.with_user(self.mashood).action_approve()
        draft.with_user(self.mashood).action_mark_sent_manually()
        desk = self.env['faizy.my.desk'].with_user(self.mashood).create({})
        self.assertEqual(desk.work_open, 1)
        self.assertEqual(desk.done_today, 1)
        self.assertEqual(desk.replies_week, 1)
        self.assertIn('Approve reply', desk.done_week_html)

        team = self.env['faizy.my.desk'].with_user(self.umer).create({})
        self.assertTrue(team.is_manager)
        self.assertIn('dk_mashood', team.team_html)
        self.assertIn('dk_raza', team.team_html)
        for name in ('action_open_work', 'action_open_overdue', 'action_open_escalated',
                     'action_open_leads', 'action_open_leads_waiting', 'action_open_orders_week'):
            self.assertEqual(getattr(desk, name)()['type'], 'ir.actions.act_window')

    def test_morning_summary_mentions_leads(self):
        self._lead(user_id=self.mashood.id)
        lines = self.env['faizy.routing']._summary_for(self.mashood)
        self.assertTrue(any('Leads waiting on you: 1' in line for line in lines))
