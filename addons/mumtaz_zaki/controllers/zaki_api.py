from odoo import http
from odoo.http import request


class ZakiApi(http.Controller):
    """Convenience JSON endpoint for an authenticated session. The primary
    path for the ZAKI backend is XML-RPC execute_kw on zaki.connector."""

    @http.route("/zaki/api/snapshot", type="jsonrpc", auth="user")
    def snapshot(self, **kw):
        return request.env["zaki.connector"].sudo().get_snapshot()
