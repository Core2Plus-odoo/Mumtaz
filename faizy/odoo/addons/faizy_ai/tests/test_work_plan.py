"""§26: planned work on the desks, evidence before Done, task escalation,
one lead pipeline per executive."""
from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.faizy_ai.models.routing import T_ESCALATION, T_LEAD_QUALIFY

NOW_PATH = 'odoo.addons.faizy_ai.models.utils.fields.Datetime.now'
HOURS_PATH = 'odoo.addons.faizy_ai.models.routing.within_hours'


@tagged('post_install', '-at_install')
class TestWorkPlan(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        def user(login, *groups):
            return env['res.users'].create({
                'name': login, 'login': login, 'notification_type': 'inbox',
                'group_ids': [Command.set([env.ref(g).id for g in groups])]})

        cls.mashood = user('wp_mashood', 'faizy_ai.group_comms')
        cls.raza = user('wp_raza', 'faizy_core.group_faizy_ops')
        cls.umer = user('wp_umer', 'faizy_core.group_faizy_manager')
        Param = env['ir.config_parameter'].sudo()
        Param.set_param('faizy_ai.care_user_id', cls.mashood.id)
        Param.set_param('faizy_ai.ops_user_id', cls.raza.id)
        Param.set_param('faizy_ai.escalation_user_id', cls.umer.id)

        def project(name, role, owner):
            return env['project.project'].sudo().create({
                'name': name, 'faizy_role': role, 'faizy_evidence_required': True,
                'privacy_visibility': 'followers', 'user_id': owner.id,
                'message_partner_ids': [Command.link(owner.partner_id.id)],
            })
        cls.care_plan = project('wp care plan', 'care', cls.mashood)
        cls.ops_plan = project('wp ops plan', 'ops', cls.raza)

    def _task(self, project, user, **kw):
        vals = {'name': 'Daily routine', 'project_id': project.id,
                'user_ids': [Command.set([user.id])], 'allocated_hours': 1.5,
                'date_deadline': fields.Datetime.now().replace(hour=13, minute=0, second=0, microsecond=0)}
        vals.update(kw)
        return self.env['project.task'].sudo().create(vals)

    # ---------------------------------------------------------------- groups and visibility
    def test_desk_groups_imply_project_rights_and_plans_are_private(self):
        self.assertTrue(self.mashood.has_group('project.group_project_user'))
        self.assertTrue(self.raza.has_group('project.group_project_user'))
        self.assertTrue(self.umer.has_group('project.group_project_manager'))
        mine = self._task(self.care_plan, self.mashood)
        theirs = self._task(self.ops_plan, self.raza)
        self.assertEqual(mine.with_user(self.mashood).name, mine.name)
        with self.assertRaises(AccessError):
            theirs.with_user(self.mashood).read(['name'])
        self.assertEqual(len((mine | theirs).with_user(self.umer).read(['name'])), 2)
        Menu = self.env['ir.ui.menu']
        self.assertIn(self.env.ref('faizy_ai.menu_care_plan').id, Menu.with_user(self.mashood)._visible_menu_ids())
        self.assertIn(self.env.ref('faizy_ai.menu_ops_plan').id, Menu.with_user(self.raza)._visible_menu_ids())
        self.assertNotIn(self.env.ref('faizy_ai.menu_ops_plan').id, Menu.with_user(self.mashood)._visible_menu_ids())

    # ---------------------------------------------------------------- evidence before Done
    def test_done_needs_a_note_or_an_attachment(self):
        task = self._task(self.care_plan, self.mashood).with_user(self.mashood)
        with self.assertRaises(UserError):
            task.write({'state': '1_done'})
        self.assertEqual(task.state, '01_in_progress')
        task.message_post(body='Triaged 7 inbound messages, 2 became order drafts.',
                          message_type='comment', subtype_xmlid='mail.mt_note')
        task.write({'state': '1_done'})
        self.assertEqual(task.state, '1_done')
        self.assertEqual(task.faizy_evidence_count, 1)
        # Cancelling needs no evidence; a project without the rule needs none either.
        other = self._task(self.care_plan, self.mashood).with_user(self.mashood)
        other.write({'state': '1_canceled'})
        self.care_plan.sudo().faizy_evidence_required = False
        free = self._task(self.care_plan, self.mashood).with_user(self.mashood)
        free.write({'state': '1_done'})
        self.assertEqual(free.state, '1_done')

    def test_attachment_counts_as_evidence(self):
        task = self._task(self.ops_plan, self.raza)
        self.env['ir.attachment'].sudo().create({
            'name': 'proof.png', 'res_model': 'project.task', 'res_id': task.id,
            'datas': b'aGVsbG8=', 'mimetype': 'image/png'})
        task.invalidate_recordset()
        task.with_user(self.raza).write({'state': '1_done'})
        self.assertEqual(task.state, '1_done')

    # ---------------------------------------------------------------- overdue tasks escalate once
    def test_overdue_planned_task_escalates_once_to_umer(self):
        task = self._task(self.ops_plan, self.raza,
                          date_deadline=fields.Datetime.now() - timedelta(hours=5))
        Routing = self.env['faizy.routing']
        with patch(HOURS_PATH, return_value=True):
            self.assertEqual(Routing._cron_escalate(), 1)
            self.assertEqual(Routing._cron_escalate(), 0)
        esc = task.activity_ids.filtered(lambda a: a.activity_type_id == self.env.ref(T_ESCALATION))
        self.assertEqual(esc.user_id, self.umer)
        self.assertTrue(task.faizy_escalated)
        # Closing the task closes the escalation item.
        task.message_post(body='Done late.', message_type='comment', subtype_xmlid='mail.mt_note')
        task.with_user(self.raza).write({'state': '1_done'})
        self.assertFalse(task.activity_ids.filtered(lambda a: a.activity_type_id == self.env.ref(T_ESCALATION)))

    def test_task_inside_grace_does_not_escalate(self):
        self._task(self.ops_plan, self.raza, date_deadline=fields.Datetime.now() - timedelta(hours=1))
        with patch(HOURS_PATH, return_value=True):
            self.assertEqual(self.env['faizy.routing']._cron_escalate(), 0)

    # ---------------------------------------------------------------- one pipeline per executive
    def test_lead_source_picks_the_team_and_its_leader(self):
        Team = self.env['crm.team'].sudo()
        digital = Team.create({'name': 'wp digital', 'user_id': self.mashood.id,
                               'faizy_lead_sources': 'facebook, instagram, website, whatsapp'})
        partners = Team.create({'name': 'wp partners', 'user_id': self.raza.id,
                                'faizy_lead_sources': 'embassy,walk_in,other'})
        Lead = self.env['crm.lead']
        a = Lead.create({'name': 'from facebook', 'user_id': False, 'faizy_lead_source': 'facebook'})
        b = Lead.create({'name': 'from embassy', 'user_id': False, 'faizy_lead_source': 'embassy'})
        c = Lead.create({'name': 'explicit', 'user_id': self.mashood.id, 'faizy_lead_source': 'embassy'})
        d = Lead.create({'name': 'no source', 'user_id': False})
        self.assertEqual((a.user_id, a.team_id), (self.mashood, digital))
        self.assertEqual((b.user_id, b.team_id), (self.raza, partners))
        self.assertEqual(c.user_id, self.mashood)
        self.assertEqual(d.user_id, self.mashood)  # care role holder, no team match
        for lead in (a, b):
            act = lead.activity_ids.filtered(lambda x: x.activity_type_id == self.env.ref(T_LEAD_QUALIFY))
            self.assertEqual(act.user_id, lead.user_id)

    # ---------------------------------------------------------------- My desk and the summary
    def test_my_desk_counts_planned_work(self):
        today = self._task(self.care_plan, self.mashood, allocated_hours=2.0)
        self._task(self.care_plan, self.mashood, allocated_hours=1.0,
                   date_deadline=fields.Datetime.now() - timedelta(days=2))
        desk = self.env['faizy.my.desk'].with_user(self.mashood).create({})
        self.assertEqual(desk.plan_open, 2)
        self.assertEqual(desk.plan_due_today, 1)
        self.assertEqual(desk.plan_hours_today, 2.0)
        self.assertEqual(desk.plan_overdue, 1)
        self.assertEqual(desk.plan_done_week, 0)
        today.message_post(body='done', message_type='comment', subtype_xmlid='mail.mt_note')
        today.with_user(self.mashood).write({'state': '1_done'})
        desk = self.env['faizy.my.desk'].with_user(self.mashood).create({})
        self.assertEqual(desk.plan_done_week, 1)
        for name in ('action_open_plan_today', 'action_open_plan', 'action_open_plan_overdue'):
            self.assertEqual(getattr(desk, name)()['type'], 'ir.actions.act_window')
        team = self.env['faizy.my.desk'].with_user(self.umer).create({})
        self.assertIn('Plan: overdue', team.team_html)
        lines = self.env['faizy.routing']._summary_for(self.mashood)
        self.assertTrue(any('Planned tasks due today or earlier: 1' in line for line in lines))
