from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Existing demo databases get the new scenarios on `-u pharma_demo_data`.
    The seeder is idempotent, so records created by 19.0.1.0.0 are kept, not duplicated."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["pharma.demo.seed"].seed()
