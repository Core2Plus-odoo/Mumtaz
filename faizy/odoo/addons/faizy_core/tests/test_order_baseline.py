"""Baseline tests for faizy.order (audit M0). They pin today's behaviour so the
completion gate (B05) and send-window gate (B06) can be added without regressions."""
import unittest

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'faizy_core')
class TestOrderBaseline(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.customer = env['res.partner'].create({'name': 'Test Sponsor'})
        cls.service = env['faizy.service'].create({'name': 'Groceries (test)', 'code': 'groceries_t'})
        cls.worker = env['faizy.worker'].create({
            'name': 'Test Faizy', 'state': 'active', 'phone': '+920000000000', 'city': 'Karachi'})

    def _order(self, **kw):
        vals = {'title': 'Test errand', 'city': 'Karachi',
                'partner_id': self.customer.id, 'service_id': self.service.id}
        vals.update(kw)
        return self.env['faizy.order'].create(vals)

    def test_new_order_is_pending_with_reference(self):
        order = self._order()
        self.assertEqual(order.state, 'pending')
        self.assertNotIn(order.name, ('/', False))

    def test_references_are_unique(self):
        self.assertNotEqual(self._order().name, self._order().name)

    def test_assign_requires_worker(self):
        order = self._order()
        with self.assertRaises(UserError):
            order.action_assign()

    def test_assign_start_complete_flow(self):
        order = self._order(worker_id=self.worker.id)
        order.action_assign()
        self.assertEqual(order.state, 'assigned')
        order.action_start()
        self.assertEqual(order.state, 'in_progress')
        order.action_complete()
        self.assertEqual(order.state, 'completed')
        self.assertTrue(order.date_completed)

    def test_reset_to_pending_clears_worker(self):
        order = self._order(worker_id=self.worker.id)
        order.action_assign()
        order.action_reset_to_pending()
        self.assertEqual((order.state, bool(order.worker_id)), ('pending', False))

    def test_unapproved_vendor_is_rejected(self):
        prospect = self.env['res.partner'].create({
            'name': 'Prospect Pharmacy', 'is_faizy_vendor': True, 'faizy_vendor_state': 'prospect'})
        with self.assertRaises(ValidationError):
            self._order(vendor_id=prospect.id)

    @unittest.expectedFailure
    def test_completion_requires_photo_and_receipt(self):
        """KNOWN GAP F-1 (audit 20 Nov 2026): completion is currently allowed with no
        evidence. Remove expectedFailure when the evidence gate (B05) ships."""
        order = self._order(worker_id=self.worker.id)
        order.action_assign()
        with self.assertRaises(UserError):
            order.action_complete()
