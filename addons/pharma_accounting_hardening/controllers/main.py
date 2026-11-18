"""Guard for the accounting kit's Excel export route.

The kit's own route is `/xlsx_report` (auth='user', POST, csrf off). It reads `model` from the request,
calls `.sudo()` on it and then `get_xlsx_report`. Nothing checks who is asking, so any logged-in user,
a portal user included, can stream ledgers and partner statements. This subclass keeps the kit's routing
(`@http.route()` with no arguments inherits it) and adds, before the kit's code runs:

  1. the caller must hold one of the groups the kit itself uses to show its report menus
     (Accountant, or the kit's Chief Accountant);
  2. `model` must be a real model that really implements `get_xlsx_report`, not an arbitrary name.

Residual, deliberately not changed: after the checks the kit still runs the export as superuser, which is
correct for accountants in a single-company database. In a multi-company database an accountant restricted
to one company could still export another company's report; review before enabling a second company.
CSRF stays off because the kit's front end posts without a token and the route only produces a download.
"""
from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request
from odoo.addons.base_accounting_kit.controllers.statement_report import XLSXReportController

ACCOUNTING_GROUPS = ("account.group_account_user", "base_accounting_kit.group_account_chief")


class HardenedXLSXReportController(XLSXReportController):

    @http.route()
    def get_report_xlsx(self, model, options, output_format, report_name, report_action=None, **kwargs):
        user = request.env.user
        if not any(user.has_group(g) for g in ACCOUNTING_GROUPS):
            raise Forbidden("Accounting report export needs an accounting role.")
        if model not in request.env or not hasattr(request.env[model], "get_xlsx_report"):
            raise Forbidden("Not an exportable report model.")
        return super().get_report_xlsx(model, options, output_format, report_name,
                                       report_action=report_action, **kwargs)
