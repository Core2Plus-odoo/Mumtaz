import json

from odoo import http
from odoo.http import request, Response


class MumtazRoutingProbe(http.Controller):
    """Lightweight, secret-free host→tenant resolver. Useful for health checks
    and nginx auth_request. Returns whether the host maps to an active tenant;
    it deliberately does NOT expose the database name."""

    @http.route("/mumtaz/routing/whoami", type="http", auth="public",
                methods=["GET"], csrf=False, save_session=False)
    def whoami(self, **kwargs):
        host = (request.httprequest.headers.get("X-Forwarded-Host")
                or request.httprequest.host or "")
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
                "state": tenant.state,
            }),
            content_type="application/json",
        )
