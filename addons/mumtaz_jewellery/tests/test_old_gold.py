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


@tagged('post_install', '-at_install', 'mumtaz_jewel')
class TestOldGoldStateGuard(JewelCommon):
    """The state and approver fields are writable only by the buttons.

    The same guard as on the gold rate. Without it the second-person rule
    above the threshold was advisory, and an intake could skip valuation
    entirely by going straight to ``confirmed``.
    """

    def _intake(self, user, gross=10.0):
        return self.env['jewellery.old.gold'].with_user(user).create({
            'gross_weight_g': gross,
            'karat': '22',
            'company_id': self.company.id,
        })

    def _above_threshold(self):
        self._set_param('mumtaz_jewellery.exchange_approval_threshold', '1')
        self.addCleanup(
            self._set_param, 'mumtaz_jewellery.exchange_approval_threshold', '0')

    def test_staff_cannot_confirm_past_the_approver(self):
        """The hole that matters: skipping the second person above the threshold."""
        self._approved_rate(rate=100.0)
        self._above_threshold()
        intake = self._intake(self.user_manager_a)
        intake.with_user(self.user_manager_a).action_confirm()
        self.assertEqual(intake.state, 'to_approve')
        with self.assertRaises(UserError) as caught:
            intake.with_user(self.user_staff).write({'state': 'confirmed'})
        self.assertIn('cannot be written directly', str(caught.exception))
        intake.invalidate_recordset()
        self.assertEqual(intake.state, 'to_approve')
        self.assertFalse(intake.approved_by_id)

    def test_the_maker_cannot_confirm_their_own_intake_by_writing_state(self):
        self._approved_rate(rate=100.0)
        self._above_threshold()
        intake = self._intake(self.user_manager_a)
        intake.with_user(self.user_manager_a).action_confirm()
        with self.assertRaises(UserError):
            intake.with_user(self.user_manager_a).write({'state': 'confirmed'})
        intake.invalidate_recordset()
        self.assertEqual(intake.state, 'to_approve')

    def test_a_draft_cannot_be_written_straight_to_confirmed(self):
        """That would skip action_confirm, so the intake would never be valued."""
        self._approved_rate(rate=100.0)
        intake = self._intake(self.user_staff)
        with self.assertRaises(UserError):
            intake.with_user(self.user_staff).write({'state': 'confirmed'})
        intake.invalidate_recordset()
        self.assertEqual(intake.state, 'draft')
        self.assertEqual(intake.value, 0.0)
        self.assertFalse(intake.rate_id)

    def test_sudo_cannot_write_the_state_either(self):
        intake = self._intake(self.user_staff)
        with self.assertRaises(UserError):
            intake.sudo().write({'state': 'confirmed'})
        intake.invalidate_recordset()
        self.assertEqual(intake.state, 'draft')

    def test_the_approver_cannot_be_written_directly(self):
        intake = self._intake(self.user_staff)
        with self.assertRaises(UserError):
            intake.with_user(self.user_manager_b).write(
                {'approved_by_id': self.user_manager_b.id})
        intake.invalidate_recordset()
        self.assertFalse(intake.approved_by_id)

    def test_an_intake_cannot_be_created_in_another_state(self):
        for state in ('to_approve', 'confirmed', 'issued'):
            with self.assertRaises(UserError) as caught:
                self.env['jewellery.old.gold'].with_user(self.user_staff).create({
                    'gross_weight_g': 10.0,
                    'karat': '22',
                    'state': state,
                    'company_id': self.company.id,
                })
            self.assertIn('created as a draft', str(caught.exception))

    def test_an_intake_cannot_be_created_with_an_approver(self):
        with self.assertRaises(UserError) as caught:
            self.env['jewellery.old.gold'].sudo().create({
                'gross_weight_g': 10.0,
                'karat': '22',
                'approved_by_id': self.user_manager_b.id,
                'company_id': self.company.id,
            })
        self.assertIn('recorded by approving', str(caught.exception))

    def test_a_draft_intake_is_still_editable(self):
        """Staff must still be able to correct a weight they mistyped."""
        intake = self._intake(self.user_staff)
        intake.with_user(self.user_staff).write({'gross_weight_g': 11.5})
        self.assertEqual(round(intake.gross_weight_g, 3), 11.5)

    def test_every_button_still_works_through_the_guard(self):
        self._approved_rate(rate=100.0)
        self._above_threshold()
        intake = self._intake(self.user_manager_a)
        intake.with_user(self.user_manager_a).action_confirm()
        self.assertEqual(intake.state, 'to_approve')
        intake.with_user(self.user_manager_b).action_approve()
        self.assertEqual(intake.state, 'confirmed')
        self.assertEqual(intake.approved_by_id, self.user_manager_b)
        intake.with_user(self.user_manager_b).action_issue_to_production()
        self.assertEqual(intake.state, 'issued')

    def test_cancel_still_works_through_the_guard(self):
        intake = self._intake(self.user_staff)
        intake.with_user(self.user_staff).action_cancel()
        self.assertEqual(intake.state, 'cancelled')

    def test_copying_an_intake_drops_the_state_and_the_valuation(self):
        self._approved_rate(rate=100.0)
        intake = self._intake(self.user_staff)
        intake.with_user(self.user_staff).action_confirm()
        self.assertEqual(intake.state, 'confirmed')
        duplicate = intake.with_user(self.user_staff).copy()
        self.assertEqual(duplicate.state, 'draft')
        self.assertFalse(duplicate.approved_by_id)
        self.assertFalse(duplicate.rate_id)
        self.assertEqual(duplicate.value, 0.0)

    def test_the_payout_cannot_be_written_by_hand(self):
        """The valuation comes from the engine at the approved rate, not a person."""
        self._approved_rate(rate=100.0)
        intake = self._intake(self.user_staff)
        intake.with_user(self.user_staff).action_confirm()
        honest = intake.value
        self.assertGreater(honest, 0.0)
        for values in ({'value': 999999.0},
                       {'applied_rate_per_g': 5000.0},
                       {'rate_id': False}):
            with self.assertRaises(UserError) as caught:
                intake.with_user(self.user_staff).write(values)
            self.assertIn('never from a person', str(caught.exception))
        intake.invalidate_recordset()
        self.assertEqual(intake.value, honest)

    def test_a_draft_cannot_be_given_a_payout_before_valuation(self):
        intake = self._intake(self.user_staff)
        with self.assertRaises(UserError):
            intake.with_user(self.user_staff).write({'value': 50000.0})
        intake.invalidate_recordset()
        self.assertEqual(intake.value, 0.0)
