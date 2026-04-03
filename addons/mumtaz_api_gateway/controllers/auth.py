import json

from odoo import http
from odoo.http import request

from ..services import response_builder
from .base import api_endpoint


class MumtazAuthController(http.Controller):
    @http.route("/api/v1/auth/login", type="http", auth="public", methods=["POST"], csrf=False)
    @api_endpoint(require_api_key=False)
    def login(self, **kwargs):
        payload = json.loads(request.httprequest.data or b"{}")
        username = payload.get("username")
        return response_builder.success({"token": f"token-for-{username or 'anonymous'}"}, message="Authenticated")

    @http.route("/api/v1/auth/logout", type="http", auth="public", methods=["POST"], csrf=False)
    @api_endpoint(require_api_key=True)
    def logout(self, api_key=None, **kwargs):
        return response_builder.success({"api_key_prefix": api_key.key_prefix}, message="Logged out")

    @http.route("/api/v1/auth/refresh", type="http", auth="public", methods=["POST"], csrf=False)
    @api_endpoint(require_api_key=True)
    def refresh(self, api_key=None, **kwargs):
        return response_builder.success({"token": f"refresh-{api_key.key_prefix}"}, message="Token refreshed")
