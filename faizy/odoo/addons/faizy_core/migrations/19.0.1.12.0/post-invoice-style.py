"""Brand the printed documents on an instance installed before this existed.

post_init_hook only fires on install, so the running database still prints
invoices in Odoo's default Lato-on-grey with no tagline and no colour. Nothing
about that is broken, which is exactly why it would have stayed that way.

apply_company_profile is idempotent and only fills fields that are still empty
or still on Odoo's default, so this is safe to re-run and will not overrule a
colour somebody picked by hand in Settings → Document Layout.

`overwrite_name=False`: renaming the company is the 19.0.1.4.0 migration's job
and it has already run. This one is only here for the report style.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.faizy_core.company_setup import apply_company_profile


def migrate(cr, version):
    apply_company_profile(api.Environment(cr, SUPERUSER_ID, {}), overwrite_name=False)
