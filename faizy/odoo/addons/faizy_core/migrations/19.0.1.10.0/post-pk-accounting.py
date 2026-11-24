"""Move the running instance onto Pakistani books.

post_init_hook only fires on install, and this database was installed when the
company was set up as a UAE entity in AED with no chart of accounts at all —
which is why Invoicing has been present but not usable.

Muhammad's decision: the accounting entity is Pakistani. So the company gets
Pakistan as its country, PKR as its currency and the l10n_pk chart of accounts.

Timing matters and this is the window. The currency can only be changed while
the books are empty, and they are empty for a reason nobody should be pleased
about: the recurring billing cron has never successfully raised an invoice,
because no plan had a product. The migration in 19.0.1.9.0 fixes that. This one
must run after it and before the first invoice posts — which is exactly what
the version ordering guarantees.

apply_accounting_profile refuses each step on its own terms if that window has
already closed, and says so in the log rather than doing it anyway.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.faizy_core.accounting_setup import apply_accounting_profile


def migrate(cr, version):
    apply_accounting_profile(api.Environment(cr, SUPERUSER_ID, {}))
