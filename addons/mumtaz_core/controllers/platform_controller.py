import logging
from datetime import datetime, timedelta

from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)

_RATE_LIMIT_SECONDS = 30  # minimum seconds between credential pushes


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
            _logger.warning(
                "push-credentials: invalid token from %s",
                request.httprequest.remote_addr,
            )
            return {"error": "Unauthorized"}

        # Rate limit: reject if last push was within the window.
        if settings.platform_last_sync:
            elapsed = (datetime.utcnow() - settings.platform_last_sync).total_seconds()
            if elapsed < _RATE_LIMIT_SECONDS:
                _logger.warning(
                    "push-credentials: rate limit hit for tenant %s (%.0fs ago)",
                    settings.tenant_code or settings.id,
                    elapsed,
                )
                return {"error": "Too many requests"}

        try:
            settings._apply_platform_credentials(payload)
            settings.sudo().write({"platform_last_sync": fields.Datetime.now()})
            _logger.info(
                "push-credentials: credentials applied for tenant %s from %s",
                settings.tenant_code or settings.id,
                request.httprequest.remote_addr,
            )
            return {"status": "ok", "tenant_code": settings.tenant_code}
        except Exception as exc:
            _logger.warning("push-credentials failed for tenant %s: %s",
                            settings.tenant_code or settings.id, exc)
            return {"error": "Internal error"}
