from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'faizy')
class TestTaskChecklist(TransactionCase):
    def test_checklist_attaches_to_a_project_task(self):
        user = mail_new_test_user(self.env, login='wp_user', name='wp_user', groups='faizy_core.group_faizy_ops')
        project = self.env['project.project'].create({'name': 'SYNTHETIC project'})
        task = self.env['project.task'].create({'name': 'SYNTHETIC task', 'project_id': project.id})
        template = self.env['faizy.checklist.template'].create({
            'name': 'SYNTHETIC task checklist', 'code': 'synthetic_task', 'res_model': 'project.task',
            'item_ids': [(0, 0, {'name': 'Step one', 'sop': 'Do it.'})]})
        template.action_release()
        ck = self.env['faizy.checklist']._start(template, record=task, owner=user)
        again = self.env['faizy.checklist']._start(template, record=task, owner=user)
        self.assertEqual(ck, again)
        self.assertEqual(task.checklist_count, 1)
        self.assertEqual(ck.res_model, 'project.task')
