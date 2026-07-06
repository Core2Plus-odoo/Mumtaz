from odoo import http

from ..services import response_builder
from .base import api_endpoint


class MumtazAuthController(http.Controller):
    # NOTE: gateway authentication is the X-API-Key header (see
    # services/auth_service.py + the api_endpoint decorator). There is
    # deliberately no username/password login endpoint here.

    @http.route("/api/v1/auth/logout", type="http", auth="public", methods=["POST"], csrf=False)
    @api_endpoint(require_api_key=True, required_feature_code="api_access")
    def logout(self, api_key=None, **kwargs):
        return response_builder.success({"api_key_prefix": api_key.key_prefix}, message="Logged out")

    @http.route("/api/v1/auth/refresh", type="http", auth="public", methods=["POST"], csrf=False)
    @api_endpoint(require_api_key=True, required_feature_code="api_access")
    def refresh(self, api_key=None, **kwargs):
        return response_builder.success({"token": f"refresh-{api_key.key_prefix}"}, message="Token refreshed")
