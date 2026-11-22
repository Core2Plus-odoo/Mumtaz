"""A draft listing and an inquiry stay in their company; a published
listing is on the marketplace for everyone (that is its purpose)."""
from odoo.tests import tagged

from .common import TwoCompanyCase


@tagged("post_install", "-at_install")
class TestMarketplaceCompanyScope(TwoCompanyCase):
    GROUPS = ["mumtaz_marketplace.group_mumtaz_marketplace_manager"]
    LOGIN_PREFIX = "market_scope"

    def _listing(self, env, name):
        Category = env["mumtaz.marketplace.category"]
        category = Category.search([], limit=1) or Category.create({"name": "TEST Category"})
        return env["mumtaz.marketplace.listing"].create({
            "name": name, "category_id": category.id, "description": "<p>TEST</p>", "short_description": "TEST"})

    def test_a_draft_listing_and_an_inquiry_stay_in_their_company(self):
        env = self.env(user=self.user_a)
        listing = self._listing(env, "TEST Draft Listing")
        self.assertHiddenFromB(listing.sudo())
        inquiry = env["mumtaz.marketplace.inquiry"].create({"listing_id": listing.id, "message": "TEST", "inquirer_name": "TEST Buyer", "inquirer_email": "buyer@example.test"})
        self.assertHiddenFromB(inquiry.sudo())

    def test_a_published_listing_is_visible_to_both(self):
        listing = self._listing(self.env(user=self.user_a), "TEST Public Listing")
        listing.sudo().write({"state": "published"})
        self.assertIn(listing, self.env["mumtaz.marketplace.listing"].with_user(self.user_b).search([("id", "=", listing.id)]))
