"""Old-gold exchange: valuation from the approved rate, and its own
maker-checker above the configured threshold.

The threshold is configuration a named finance manager confirms
(docs/mumtaz-jewel/CLAUDE.md); these tests set it explicitly so they never
depend on whatever a database happens to hold.
"""
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import JewelCommon


@tagged('post_install', '-at_install', 'mumtaz_jewel')
class TestOldGoldExchange(JewelCommon):

    def _intake(self, user, gross=10.0):
        return self.env['jewellery.old.gold'].with_user(user).create({
            'gross_weight_g': gross,
            'karat': '22',
            'melt_loss_pct': 2.0,
            'buyback_discount_pct': 3.0,
            'company_id': self.company.id,
        })

    def test_confirm_requires_an_approved_rate(self):
        self._draft_rate(self.user_manager_a)
        intake = self._intake(self.user_staff)
        with self.assertRaises(UserError) as caught:
            intake.with_user(self.user_staff).action_confirm()
        self.assertIn('No approved gold rate', str(caught.exception))
        self.assertEqual(intake.state, 'draft')

    def test_confirm_values_at_the_approved_rate_and_snapshots_it(self):
        rate = self._approved_rate(rate=100.0)
        intake = self._intake(self.user_staff)
        intake.with_user(self.user_staff).action_confirm()
        # The engine's own documented figures for this input.
        self.assertEqual(round(intake.fine_weight_g, 4), 8.9833)
        self.assertEqual(round(intake.applied_rate_per_g, 4), 97.0)
        self.assertEqual(round(intake.value, 2), 871.38)
        self.assertEqual(intake.rate_id, rate,
                         'the rate used must be snapshotted on the record')
        self.assertEqual(intake.state, 'confirmed',
                         'below the threshold it needs no second person')

    def test_above_threshold_a_second_person_must_approve(self):
        self._approved_rate(rate=100.0)
        self._set_param('mumtaz_jewellery.exchange_approval_threshold', '500')
        self.addCleanup(
            self._set_param, 'mumtaz_jewellery.exchange_approval_threshold', '0')
        intake = self._intake(self.user_manager_a)
        intake.with_user(self.user_manager_a).action_confirm()
        self.assertEqual(intake.state, 'to_approve')

        # Same user: refused.
        with self.assertRaises(UserError) as caught:
            intake.with_user(self.user_manager_a).action_approve()
        self.assertIn('Maker-checker', str(caught.exception))
        self.assertEqual(intake.state, 'to_approve')

        # Non-manager: refused.
        with self.assertRaises(UserError):
            intake.with_user(self.user_staff).action_approve()
        self.assertEqual(intake.state, 'to_approve')

        # A different manager: accepted.
        intake.with_user(self.user_manager_b).action_approve()
        self.assertEqual(intake.state, 'confirmed')
        self.assertEqual(intake.approved_by_id, self.user_manager_b)

    def test_an_issued_exchange_cannot_be_cancelled(self):
        self._approved_rate(rate=100.0)
        intake = self._intake(self.user_staff)
        intake.with_user(self.user_staff).action_confirm()
        intake.action_issue_to_production()
        self.assertEqual(intake.state, 'issued')
        with self.assertRaises(UserError):
            intake.action_cancel()
        self.assertEqual(intake.state, 'issued')

    def test_the_sequence_names_the_intake(self):
        intake = self._intake(self.user_staff)
        self.assertTrue(intake.name.startswith('OGX/'), intake.name)
