"""Plans, rate cards, their lines and company-owned outlets stay in their
company; a shared outlet is visible to both."""
from odoo.tests import tagged

from .common import TwoCompanyCase


@tagged("post_install", "-at_install")
class TestMediaCompanyScope(TwoCompanyCase):
    GROUPS = ["mumtaz_media_buying.group_media_user"]
    LOGIN_PREFIX = "media_scope"

    def test_plans_rate_cards_and_lines_stay_in_their_company(self):
        # Partners are made by the administrator: a media user does not get contact rights from this module.
        vendor = self.env["res.partner"].create({"name": "TEST Vendor", "is_media_vendor": True})
        client = self.env["res.partner"].create({"name": "TEST Client"})
        env = self.env(user=self.user_a)
        outlet = env["media.outlet"].create({"name": "TEST Outlet", "channel": "tv", "vendor_id": vendor.id})
        card = env["media.rate.card"].create({"name": "TEST Card", "vendor_id": vendor.id})
        card_line = env["media.rate.card.line"].create({"rate_card_id": card.id, "outlet_id": outlet.id, "name": "Prime", "rate": 1000.0})
        plan = env["media.plan"].create({"campaign": "TEST Campaign", "client_id": client.id,
                                        "date_from": "2026-01-01", "date_to": "2026-01-31"})
        line = env["media.plan.line"].create({"plan_id": plan.id, "outlet_id": outlet.id, "unit_rate": 1000.0})
        for rec in (plan, line, card, card_line, outlet):
            self.assertEqual(rec.sudo().company_id, self.company_a)
            self.assertHiddenFromB(rec.sudo())

    def test_a_shared_outlet_is_visible_to_both(self):
        vendor = self.env["res.partner"].create({"name": "TEST Shared Vendor", "is_media_vendor": True})
        shared = self.env["media.outlet"].create({"name": "TEST Shared", "channel": "radio", "vendor_id": vendor.id, "company_id": False})
        for user in (self.user_a, self.user_b):
            self.assertIn(shared, self.env["media.outlet"].with_user(user).search([("id", "=", shared.id)]))
