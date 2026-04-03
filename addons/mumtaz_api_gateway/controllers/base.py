import json
import time
from functools import wraps

from odoo import http
from odoo.http import request

from ..services import auth_service, rate_limiter, response_builder


def api_endpoint(require_api_key=True):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            api_key = None
            try:
                if require_api_key:
                    raw_key = request.httprequest.headers.get("X-API-Key")
                    api_key = auth_service.resolve_api_key(request.env, raw_key)
                    rate_limiter.check_rate_limit(api_key)

                result = func(*args, api_key=api_key, **kwargs)
                payload = result if isinstance(result, dict) else response_builder.success(result)
                status = payload.get("status", 200)
                _log_usage(api_key, status, int((time.time() - start) * 1000), endpoint=request.httprequest.path)
                return request.make_json_response(payload, status=status)
            except Exception as exc:  # pylint: disable=broad-except
                payload = response_builder.error(message=str(exc), status=400)
                _log_usage(api_key, 400, int((time.time() - start) * 1000), endpoint=request.httprequest.path, error=str(exc))
                return request.make_json_response(payload, status=400)

        return wrapper

    return decorator


def _log_usage(api_key, status_code, duration_ms, endpoint, error=None):
    request.env["mumtaz.api.usage.log"].sudo().create({
        "api_key_id": api_key.id if api_key else False,
        "tenant_id": api_key.tenant_id.id if api_key else False,
        "endpoint": endpoint,
        "method": request.httprequest.method,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "request_id": request.httprequest.headers.get("X-Request-ID"),
        "ip_address": request.httprequest.remote_addr,
        "user_agent": request.httprequest.headers.get("User-Agent"),
        "payload_size": request.httprequest.content_length or 0,
        "response_size": 0,
        "error_message": error,
    })


class MumtazApiBaseController(http.Controller):
    @http.route("/api/v1/admin/health", type="http", auth="public", methods=["GET"], csrf=False)
    def health(self):
        return request.make_json_response(response_builder.success({"service": "mumtaz_api_gateway"}))
