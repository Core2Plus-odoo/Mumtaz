from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Existing demo databases get the wellness storefront on `-u pharma_website_demo`: categories renamed,
    products re-ordered, logo set. The seeder is idempotent."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["pharma.website.demo.seed"].seed()
