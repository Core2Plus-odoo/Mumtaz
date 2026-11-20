"""Looking at a Private or Royal client leaves a trace: one line per form
view, one line per list, search or export (gap-analysis finding 1)."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'mumtaz_jewel')
class TestAccessLog(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Users = env['res.users'].with_context(no_reset_password=True)
        field = 'group_ids' if 'group_ids' in Users._fields else 'groups_id'
        g_vip = env.ref('mumtaz_jewellery_vip.group_vip_manager')
        g_export = env.ref('base.group_allow_export')
        cls.vip = Users.create({'name': 'TEST VIP Mgr', 'login': 'log_vip', field: [(6, 0, [g_vip.id, g_export.id])]})
        cls.royal = env['res.partner'].create({'name': 'TEST Log Royal', 'jewellery_tier': 'royal', 'relationship_manager_id': cls.vip.id})
        cls.private = env['res.partner'].create({'name': 'TEST Log Private', 'jewellery_tier': 'private', 'relationship_manager_id': cls.vip.id})
        cls.plain = env['res.partner'].create({'name': 'TEST Log Plain', 'jewellery_tier': 'standard'})
        cls.Log = env['jewellery.vip.access.log'].sudo()

    def _logs(self):
        return self.Log.search([('user_id', '=', self.vip.id)])

    def test_a_list_logs_one_line_with_the_restricted_clients_it_returned(self):
        before = len(self._logs())
        Partner = self.env['res.partner'].with_user(self.vip)
        rows = Partner.search_read([('name', 'like', 'TEST Log %')], ['name'])
        self.assertEqual(len(rows), 3)
        new = self._logs()[:len(self._logs()) - before]
        self.assertEqual(len(new), 1, 'one query, one line')
        self.assertEqual(new.action, 'list')
        self.assertEqual(new.count, 2)
        self.assertEqual(set(new.partner_ids.ids), {self.royal.id, self.private.id})

    def test_a_list_without_restricted_clients_logs_nothing(self):
        before = len(self._logs())
        self.env['res.partner'].with_user(self.vip).search_read([('name', '=', 'TEST Log Plain')], ['name'])
        self.assertEqual(len(self._logs()), before)

    def test_an_export_is_logged_with_its_fields(self):
        before = len(self._logs())
        (self.royal | self.plain).with_user(self.vip).export_data(['name', 'phone'])
        new = self._logs()[:len(self._logs()) - before]
        self.assertEqual(new.action, 'export')
        self.assertEqual(new.partner_ids, self.royal)
        self.assertIn('phone', new.note)

    def test_the_superuser_is_not_logged(self):
        before = len(self.Log.search([]))
        self.env['res.partner'].sudo().search_read([('name', 'like', 'TEST Log %')], ['name'])
        self.assertEqual(len(self.Log.search([])), before)
