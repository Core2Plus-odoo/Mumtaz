"""The fifth user type: a VIP manager.

``group_vip_manager`` implies ``group_jewellery_user`` but NOT
``group_jewellery_manager``, so holding the VIP role must not confer the
right to approve a gold rate. This test lives in the VIP addon because the
core addon does not depend on it.
"""
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.mumtaz_jewellery.tests.common import JewelCommon


@tagged('post_install', '-at_install', 'mumtaz_jewel')
class TestVipManagerCannotApproveRates(JewelCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_vip = cls.env.ref('mumtaz_jewellery_vip.group_vip_manager')
        cls.user_vip = cls._make_user('demo_vip_manager', cls.base_user, cls.group_vip)

    def test_the_vip_role_does_not_imply_the_jewellery_manager_role(self):
        self.assertTrue(self.user_vip.has_group(
            'mumtaz_jewellery.group_jewellery_user'))
        self.assertFalse(self.user_vip.has_group(
            'mumtaz_jewellery.group_jewellery_manager'))

    def test_a_vip_manager_cannot_approve_a_rate(self):
        rate = self._draft_rate(self.user_manager_a)
        with self.assertRaises(UserError) as caught:
            rate.with_user(self.user_vip).action_approve()
        self.assertIn('manager', str(caught.exception).lower())
        self.assertEqual(rate.state, 'draft')

    def test_a_vip_manager_cannot_approve_an_old_gold_exchange(self):
        self._approved_rate(rate=100.0)
        self._set_param('mumtaz_jewellery.exchange_approval_threshold', '1')
        self.addCleanup(
            self._set_param, 'mumtaz_jewellery.exchange_approval_threshold', '0')
        intake = self.env['jewellery.old.gold'].with_user(self.user_staff).create({
            'gross_weight_g': 10.0,
            'karat': '22',
            'company_id': self.company.id,
        })
        intake.with_user(self.user_staff).action_confirm()
        self.assertEqual(intake.state, 'to_approve')
        with self.assertRaises(UserError):
            intake.with_user(self.user_vip).action_approve()
        self.assertEqual(intake.state, 'to_approve')
