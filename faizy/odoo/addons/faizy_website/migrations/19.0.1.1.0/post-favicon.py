"""Set the favicon on an instance installed before this existed.

post_init_hook only fires on install, so a running site would have kept
Odoo's purple default forever. Also re-runs whenever the packaged mark
changes — apply_favicon records a hash of what it installed, so replacing the
interim mark with the real logo reaches existing sites on the next upgrade
without touching one somebody uploaded by hand.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.faizy_website.favicon_setup import apply_favicon


def migrate(cr, version):
    apply_favicon(api.Environment(cr, SUPERUSER_ID, {}))
