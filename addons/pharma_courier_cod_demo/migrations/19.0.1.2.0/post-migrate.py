from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Existing demo databases get the collection entries on `-u pharma_courier_cod_demo`. The seeder is idempotent."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["pharma.courier.demo.seed"].seed()
