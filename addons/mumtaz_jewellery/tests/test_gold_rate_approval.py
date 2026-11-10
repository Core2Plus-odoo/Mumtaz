"""Maker-checker on the gold rate, exercised as real users on a real database.

Closes unresolved issue 1 of docs/mumtaz-jewel/IMPLEMENTATION_ROADMAP.md
("same-user approval block untested"). Four behaviours are required by
Slice 0:

1. same-user rate approval is refused;
2. a non-manager is refused;
3. pricing uses an approved rate only;
4. two different managers succeed.

``TestRateStateOrmGap`` additionally probes an unverified gap flagged in the
handoff. It asserts what the code does TODAY, not what it should do; see its
docstring.
"""
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import JewelCommon, RATE_PER_GRAM


@tagged('post_install', '-at_install', 'mumtaz_jewel')
class TestGoldRateApproval(JewelCommon):

    # -- 1. same-user approval is refused ------------------------------
    def test_same_user_cannot_approve_own_rate(self):
        """The manager who entered a rate cannot approve it himself."""
        rate = self._draft_rate(self.user_manager_a)
        self.assertEqual(rate.create_uid, self.user_manager_a)
        with self.assertRaises(UserError) as caught:
            rate.with_user(self.user_manager_a).action_approve()
        self.assertIn('Maker-checker', str(caught.exception))
        self.assertEqual(rate.state, 'draft', 'the rate must stay in draft')
        self.assertFalse(rate.approved_by_id)
        self.assertFalse(rate.approved_at)

    def test_same_user_cannot_reject_own_rate(self):
        """Rejection runs through the same gate as approval."""
        rate = self._draft_rate(self.user_manager_a)
        with self.assertRaises(UserError):
            rate.with_user(self.user_manager_a).action_reject()
        self.assertEqual(rate.state, 'draft')

    def test_self_approval_only_when_the_parameter_allows_it(self):
        """The documented escape hatch, which ships disabled."""
        self._set_param('mumtaz_jewellery.allow_self_approval', '1')
        self.addCleanup(
            self._set_param, 'mumtaz_jewellery.allow_self_approval', '0')
        rate = self._draft_rate(self.user_manager_a)
        rate.with_user(self.user_manager_a).action_approve()
        self.assertEqual(rate.state, 'approved')
        self.assertEqual(rate.approved_by_id, self.user_manager_a)

    # -- 2. a non-manager is refused -----------------------------------
    def test_jewellery_user_cannot_approve(self):
        """Counter staff may enter a rate but never decide on one."""
        rate = self._draft_rate(self.user_manager_a)
        with self.assertRaises(UserError) as caught:
            rate.with_user(self.user_staff).action_approve()
        self.assertIn('manager', str(caught.exception).lower())
        self.assertEqual(rate.state, 'draft')

    def test_user_without_jewellery_groups_cannot_approve(self):
        """An employee outside the vertical is refused on groups or on rights.

        Either outcome is a correct refusal, so the exception type is checked
        by hand: Odoo's own ``assertRaises`` takes a single class, not a tuple.
        """
        rate = self._draft_rate(self.user_manager_a)
        try:
            rate.with_user(self.user_outsider).action_approve()
        except (UserError, AccessError):
            pass
        else:
            self.fail('an employee with no jewellery group approved a rate')
        self.assertEqual(rate.state, 'draft')

    def test_staff_may_still_enter_a_rate_for_a_manager_to_decide(self):
        """Maker-checker must not stop staff from doing the maker half."""
        rate = self._draft_rate(self.user_staff)
        self.assertEqual(rate.state, 'draft')
        rate.with_user(self.user_manager_a).action_approve()
        self.assertEqual(rate.state, 'approved')
        self.assertEqual(rate.approved_by_id, self.user_manager_a)

    # -- 3. an approved rate only ---------------------------------------
    def test_get_current_refuses_when_only_a_draft_exists(self):
        self._draft_rate(self.user_manager_a)
        with self.assertRaises(UserError) as caught:
            self.env['jewellery.gold.rate'].get_current(self.company)
        self.assertIn('No approved gold rate', str(caught.exception))

    def test_get_current_refuses_a_rejected_rate(self):
        rate = self._draft_rate(self.user_manager_a)
        rate.with_user(self.user_manager_b).action_reject()
        self.assertEqual(rate.state, 'rejected')
        with self.assertRaises(UserError):
            self.env['jewellery.gold.rate'].get_current(self.company)

    def test_get_current_returns_the_approved_rate(self):
        rate = self._approved_rate()
        self.assertEqual(
            self.env['jewellery.gold.rate'].get_current(self.company), rate)

    def test_a_later_draft_does_not_displace_the_approved_rate(self):
        """Prices stay on the approved rate until a new one is approved."""
        approved = self._approved_rate(rate=100.0)
        self._draft_rate(self.user_manager_a, rate=250.0)
        current = self.env['jewellery.gold.rate'].get_current(self.company)
        self.assertEqual(current, approved)
        self.assertEqual(current.rate_per_gram, 100.0)

    def test_pricing_a_piece_is_gated_on_an_approved_rate(self):
        """The real gated operation, not just the helper."""
        piece = self._piece()
        self._draft_rate(self.user_manager_a)
        with self.assertRaises(UserError):
            piece.get_price_breakdown()
        rate = self._approved_rate()
        breakdown = piece.get_price_breakdown()
        self.assertEqual(breakdown['rate_id'], rate.id)
        self.assertEqual(round(breakdown['total'], 2), 1130.50)

    def test_rate_must_be_positive(self):
        """A zero or negative rate is refused by the model constraint."""
        with self.assertRaises(UserError) as caught:
            self.env['jewellery.gold.rate'].create({
                'rate_per_gram': 0.0,
                'company_id': self.company.id,
            })
        self.assertIn('greater than zero', str(caught.exception))

    # -- 4. two managers succeed ----------------------------------------
    def test_two_managers_approve_successfully(self):
        """Manager A enters, manager B approves: the happy path."""
        rate = self._draft_rate(self.user_manager_a, rate=RATE_PER_GRAM)
        rate.with_user(self.user_manager_b).action_approve()
        self.assertEqual(rate.state, 'approved')
        self.assertEqual(rate.approved_by_id, self.user_manager_b)
        self.assertTrue(rate.approved_at)
        self.assertNotEqual(
            rate.create_uid, rate.approved_by_id,
            'the approver must be a different person from the maker')
        self.assertEqual(
            self.env['jewellery.gold.rate'].get_current(self.company), rate)

    def test_an_approved_rate_cannot_be_approved_again(self):
        """``approved`` is terminal."""
        rate = self._approved_rate()
        with self.assertRaises(UserError) as caught:
            rate.with_user(self.user_manager_a).action_approve()
        self.assertIn('draft', str(caught.exception).lower())
        self.assertEqual(rate.approved_by_id, self.user_manager_b)

    def test_a_rejected_rate_cannot_then_be_approved(self):
        """``rejected`` is terminal too."""
        rate = self._draft_rate(self.user_manager_a)
        rate.with_user(self.user_manager_b).action_reject()
        with self.assertRaises(UserError):
            rate.with_user(self.user_manager_b).action_approve()
        self.assertEqual(rate.state, 'rejected')


@tagged('post_install', '-at_install', 'mumtaz_jewel')
class TestRateStateOrmGap(JewelCommon):
    """Probe for the gap named in the Slice 0 handoff, not a fix for it.

    ``state``, ``approved_by_id`` and ``approved_at`` are read-only in the
    views only. The ACL grants a Jewellery User write and create on
    ``jewellery.gold.rate``, and there is no record rule and no guard in
    ``create``/``write``. So a rate can in principle reach ``approved``
    through the ORM or RPC without ``action_approve`` ever running, which
    would sidestep maker-checker entirely.

    These tests assert the CURRENT behaviour so the suite stays an honest
    description of the code. They are the evidence for a decision the owner
    has to take (guard ``state`` in ``write``/``create``, or drop write from
    the user ACL); per docs/mumtaz-jewel/CLAUDE.md the approval flow is not
    changed without a named approval. When the guard lands, these two tests
    are the ones to invert.
    """

    def test_staff_can_write_state_approved_directly(self):
        rate = self._draft_rate(self.user_staff)
        rate.with_user(self.user_staff).write({'state': 'approved'})
        self.assertEqual(
            rate.state, 'approved',
            'GAP: a non-manager moved a rate to approved without '
            'action_approve(); no guard exists yet.')
        # And the bypass is not cosmetic: pricing now trusts this rate.
        self.assertEqual(
            self.env['jewellery.gold.rate'].get_current(self.company), rate)
        # The audit trail stays empty, which is how the bypass is detectable.
        self.assertFalse(rate.approved_by_id)
        self.assertFalse(rate.approved_at)

    def test_staff_can_create_an_already_approved_rate(self):
        rate = self.env['jewellery.gold.rate'].with_user(self.user_staff).create({
            'rate_per_gram': 123.0,
            'state': 'approved',
            'company_id': self.company.id,
        })
        self.assertEqual(
            rate.state, 'approved',
            'GAP: a rate was created already approved, skipping maker-checker.')
        self.assertFalse(rate.approved_by_id)
