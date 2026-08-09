"""Apply the company identity to an instance installed before it existed.

Same reasoning as the currency migration: company details are applied from
code rather than a data file, so a fresh install gets them from the
post_init_hook and an existing one needs this.

apply_company_profile is conservative about what it overwrites — a company
already renamed to something real keeps its name, and an existing logo is not
replaced — so running it against a configured database is safe.
"""

import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.faizy_core.company_setup import apply_company_profile

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    apply_company_profile(env)
