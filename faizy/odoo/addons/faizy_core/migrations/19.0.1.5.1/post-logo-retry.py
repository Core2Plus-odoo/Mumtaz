"""Install the logo, third attempt.

19.0.1.2.0 guarded on `not company.logo` — Odoo ships a placeholder, so it
never fired. 19.0.1.5.0 added a stamp but still required either an empty logo
or an existing stamp, which on a first run is neither. Both shipped "Your Logo"
to the live header.

The rule now: the first run installs the packaged mark, and after that only a
change to the mark re-installs it.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.faizy_core.company_setup import apply_company_profile


def migrate(cr, version):
    apply_company_profile(api.Environment(cr, SUPERUSER_ID, {}))
