"""Rename the company from the legal entity to the trading name.

19.0.1.2.0 set res.company.name to "C2P Consultants FZC LLC". Muhammad's call
is that the company in Odoo should be "Faizy" — that is what a customer
recognises at the top of an invoice.

The legal entity does not disappear: it moves to report_footer, which prints at
the bottom of every invoice and report. A customer disputing a charge, or a
bank tracing one, still finds a registered name.

apply_company_profile only renames a company still carrying the name this
module set, so running it against a database somebody has renamed by hand
changes nothing.
"""

import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.faizy_core.company_setup import apply_company_profile

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    apply_company_profile(env)
