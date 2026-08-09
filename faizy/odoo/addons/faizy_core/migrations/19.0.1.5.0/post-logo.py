"""Install the logo on an instance still showing Odoo's "Your Logo" placeholder.

The 19.0.1.2.0 run skipped it: the guard was `not company.logo`, and Odoo gives
every new company a placeholder, so the field was never empty and the branch
never fired.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.faizy_core.company_setup import apply_company_profile


def migrate(cr, version):
    apply_company_profile(api.Environment(cr, SUPERUSER_ID, {}))
