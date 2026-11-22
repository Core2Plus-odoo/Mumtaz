"""Owner cards never cross companies (gap-analysis finding 3)."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'mumtaz_jewel')
class TestCardsPerCompany(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company_a = env.company
        cls.company_b = env['res.company'].create({'name': 'TEST Second Jeweller'})
        Users = env['res.users'].with_context(no_reset_password=True)
        field = 'group_ids' if 'group_ids' in Users._fields else 'groups_id'
        g_mgr = env.ref('mumtaz_jewellery.group_jewellery_manager')
        cls.manager_b = Users.create({
            'name': 'TEST Manager B', 'login': 'card_manager_b', field: [(6, 0, [g_mgr.id])],
            'company_id': cls.company_b.id, 'company_ids': [(6, 0, [cls.company_b.id])]})
        cls.manager_a = Users.create({
            'name': 'TEST Manager A', 'login': 'card_manager_a', field: [(6, 0, [g_mgr.id])],
            'company_id': cls.company_a.id, 'company_ids': [(6, 0, [cls.company_a.id])]})
        cls.Card = env['jewellery.owner.card']

    def test_a_card_carries_its_company_and_stays_there(self):
        card_a = self.Card.with_user(self.manager_a).sudo().create({'kind': 'rate', 'title': 'TEST A card'})
        self.assertEqual(card_a.company_id, self.company_a)
        card_b = self.Card.with_company(self.company_b).sudo().create({'kind': 'rate', 'title': 'TEST B card'})
        self.assertEqual(card_b.company_id, self.company_b)
        seen_by_b = self.Card.with_user(self.manager_b).search([('title', 'like', 'TEST % card')])
        self.assertEqual(seen_by_b, card_b)
        seen_by_a = self.Card.with_user(self.manager_a).search([('title', 'like', 'TEST % card')])
        self.assertEqual(seen_by_a, card_a)

    def test_refresh_in_one_company_leaves_the_other_deck_alone(self):
        card_b = self.Card.with_company(self.company_b).sudo().create({'kind': 'rate', 'title': 'TEST B open'})
        self.Card.with_company(self.company_a).refresh()
        self.assertEqual(card_b.state, 'open', 'company A refresh must not resolve company B cards')
        for c in self.Card.sudo().search([('company_id', '=', self.company_a.id), ('state', '=', 'open')]):
            self.assertEqual(c.company_id, self.company_a)
