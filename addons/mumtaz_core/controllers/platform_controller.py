import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MumtazPlatformController(http.Controller):
    """Inbound push endpoint — app.mumtaz.digital calls this to distribute
    updated credentials without waiting for the daily pull cron."""

    @http.route(
        "/mumtaz/platform/push-credentials",
        type="jsonrpc",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def push_credentials(self, **payload):
        token = (
            request.httprequest.headers.get("Authorization", "")
            .removeprefix("Bearer ")
            .strip()
        )
        if not token:
            return {"error": "Unauthorized"}

        settings = (
            request.env["mumtaz.core.settings"]
            .sudo()
            .search([("platform_token", "=", token), ("active", "=", True)], limit=1)
        )
        if not settings:
            return {"error": "Unauthorized"}

        try:
            settings._apply_platform_credentials(payload)
            return {"status": "ok", "tenant_code": settings.tenant_code}
        except Exception as exc:
            _logger.warning("Mumtaz platform push-credentials failed: %s", exc)
            return {"error": "Internal error"}
