"""Campaigns and their steps stay in their company; a scoring rule without
a company is shared."""
from odoo.tests import tagged

from .common import TwoCompanyCase


@tagged("post_install", "-at_install")
class TestNurtureCompanyScope(TwoCompanyCase):
    GROUPS = ["mumtaz_lead_nurture.group_lead_nurture_manager"]
    LOGIN_PREFIX = "nurture_scope"

    def test_campaigns_and_steps_stay_in_their_company(self):
        env = self.env(user=self.user_a)
        campaign = env["lead.nurture.campaign"].create({"name": "TEST Campaign"})
        step = env["lead.nurture.step"].create({"campaign_id": campaign.id, "name": "Call", "step_number": 1, "channel": "activity"})
        self.assertEqual(campaign.sudo().company_id, self.company_a)
        self.assertEqual(step.sudo().company_id, self.company_a)
        self.assertHiddenFromB(campaign.sudo())
        self.assertHiddenFromB(step.sudo())

    def test_a_shared_rule_is_visible_to_both(self):
        rule = self.env["lead.nurture.rule"].create({"name": "TEST Rule", "trigger_event": "email_opened", "score_change": 5, "company_id": False})
        for user in (self.user_a, self.user_b):
            self.assertIn(rule, self.env["lead.nurture.rule"].with_user(user).search([("id", "=", rule.id)]))
