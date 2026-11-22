import logging

from odoo import _, http
from odoo.exceptions import AccessError
from odoo.http import request

_logger = logging.getLogger(__name__)


class ZakiApi(http.Controller):
    """Convenience JSON endpoint for an authenticated session. The primary
    path for the ZAKI backend is XML-RPC execute_kw on zaki.connector."""

    @http.route("/zaki/api/snapshot", type="jsonrpc", auth="user")
    def snapshot(self, **kw):
        # The snapshot is the company's books in figures. It is served only to
        # internal users who may read accounting; everyone else is refused
        # before any query runs.
        user = request.env.user
        if user.share or not (user.has_group("account.group_account_readonly")
                              or user.has_group("account.group_account_invoice")):
            raise AccessError(_("The ZAKI snapshot is available to accounting users only."))
        try:
            # sudo: the snapshot aggregates moves, payslips and leads company-wide for a user already checked above for accounting rights
            return request.env["zaki.connector"].sudo().get_snapshot()
        except Exception:
            _logger.exception("ZAKI snapshot failed for uid=%s company=%s",
                              request.env.uid, request.env.company.id)
            raise
