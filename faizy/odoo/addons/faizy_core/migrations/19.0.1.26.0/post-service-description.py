"""Drop the unapproved "5% platform fee" from the Product Finder description.

The data file is noupdate, so a running database keeps the old text. Only the
exact old text is replaced: a description someone edited by hand is left alone.
"""

from odoo import SUPERUSER_ID, api

OLD = "Describe any product. We source, quote and deliver, plus the 5% platform fee."
NEW = "Describe any product. We source, quote and deliver."


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    service = env.ref("faizy_core.service_product_request", raise_if_not_found=False)
    if service and service.description == OLD:
        service.description = NEW
