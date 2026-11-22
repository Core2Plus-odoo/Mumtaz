"""Rename the "Start free" menu entry to "Get started" on the running site.

"Free" is a promise nobody has approved (see docs/00-decisions.md section 17).
`website_menu_data.xml` is noupdate, so the data file alone never reaches a
database that already has the record. Only an entry still carrying the old
label is touched: if marketing already renamed it, their wording stays.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

OLD, NEW = "Start free", "Get started"


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    menus = env["website.menu"].search([("url", "=", "/start")]).filtered(lambda m: m.name == OLD)
    if menus:
        menus.write({"name": NEW})
    _logger.info("faizy_website: renamed %s menu entr(ies) from %r to %r", len(menus), OLD, NEW)
