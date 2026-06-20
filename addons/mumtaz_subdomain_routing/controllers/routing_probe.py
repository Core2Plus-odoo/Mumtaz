import json

from odoo import http
from odoo.http import request, Response


class MumtazRoutingProbe(http.Controller):
    """Lightweight host→tenant resolver for nginx auth_request health checks.

    Uses only the request Host header (set by nginx). Deliberately returns
    minimal information — no tenant state, no database names.
    """

    @http.route("/mumtaz/routing/whoami", type="http", auth="public",
                methods=["GET"], csrf=False, save_session=False)
    def whoami(self, **kwargs):
        # Use only the actual Host header; never trust client-supplied
        # X-Forwarded-Host as it can be spoofed to enumerate tenants.
        host = request.httprequest.host or ""
        tenant = request.env["mumtaz.tenant"].sudo()._resolve_for_host(host)
        if not tenant:
            return Response(
                json.dumps({"resolved": False}),
                status=404, content_type="application/json",
            )
        return Response(
            json.dumps({
                "resolved": True,
                "subdomain": tenant.subdomain or "",
            }),
            content_type="application/json",
        )
