import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ZakiApi(http.Controller):
    """Convenience JSON endpoint for an authenticated session. The primary
    path for the ZAKI backend is XML-RPC execute_kw on zaki.connector."""

    @http.route("/zaki/api/snapshot", type="jsonrpc", auth="user")
    def snapshot(self, **kw):
        try:
            return request.env["zaki.connector"].sudo().get_snapshot()
        except Exception:
            _logger.exception("ZAKI snapshot failed for uid=%s company=%s",
                              request.env.uid, request.env.company.id)
            raise
