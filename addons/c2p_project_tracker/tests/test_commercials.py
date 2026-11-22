from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import C2pTrackerCommon


@tagged("post_install", "-at_install")
class TestCommercials(C2pTrackerCommon):
    """Outstanding, the 60/40 split and the collected-basis margin."""

    def test_outstanding_and_split(self):
        self.portfolio.write({
            "contract_value": 15000.0,
            "amount_received": 3000.0,
        })
        p = self.portfolio
        self.assertEqual(p.amount_received_effective, 3000.0)
        self.assertEqual(p.amount_outstanding, 12000.0)
        # 60% of the contract is payable to Solutions.
        self.assertEqual(p.subcontract_value, 9000.0)
        self.assertEqual(p.subcontract_outstanding, 9000.0)
        # The Consultants' 40% is earned on what was collected, not billed:
        # 40% of 3,000, not of 15,000.
        self.assertEqual(p.consultants_margin, 1200.0)

    def test_subcontract_paid_reduces_what_is_owed(self):
        self.portfolio.write({
            "contract_value": 10000.0, "subcontract_paid": 2000.0,
        })
        self.assertEqual(self.portfolio.subcontract_value, 6000.0)
        self.assertEqual(self.portfolio.subcontract_outstanding, 4000.0)

    def test_default_split_is_sixty_percent(self):
        self.assertEqual(self.portfolio.subcontract_pct, 60.0)

    def test_split_is_configurable_per_project(self):
        self.portfolio.write({"contract_value": 10000.0, "subcontract_pct": 50.0})
        self.assertEqual(self.portfolio.subcontract_value, 5000.0)
        self.assertEqual(self.portfolio.consultants_margin, 0.0,
                         "nothing collected means nothing earned")

    def test_impossible_split_is_rejected(self):
        for bad in (-1.0, 101.0):
            with self.assertRaises(ValidationError):
                self.portfolio.subcontract_pct = bad

    def test_commercials_missing_flag(self):
        self.assertTrue(self.portfolio.commercials_missing,
                        "a portfolio project with no contract value is missing "
                        "its commercials")
        self.portfolio.contract_value = 1000.0
        self.assertFalse(self.portfolio.commercials_missing)

    def test_delivery_project_is_never_flagged(self):
        """The flag drives a portfolio amber rule; delivery projects have no
        commercials by design and must not be marked incomplete."""
        self.assertFalse(self.delivery.commercials_missing)
