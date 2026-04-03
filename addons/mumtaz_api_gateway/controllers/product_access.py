from odoo import http

from ..services import response_builder
from .base import api_endpoint


class MumtazProductAccessController(http.Controller):
    @http.route("/api/v1/ai/ping", type="http", auth="public", methods=["GET"], csrf=False)
    @api_endpoint(require_api_key=True, required_feature_code="ai_access")
    def ai_ping(self, **kwargs):
        return response_builder.success({"service": "ai", "access": "granted"})

    @http.route("/api/v1/marketplace/ping", type="http", auth="public", methods=["GET"], csrf=False)
    @api_endpoint(require_api_key=True, required_feature_code="marketplace_access")
    def marketplace_ping(self, **kwargs):
        return response_builder.success({"service": "marketplace", "access": "granted"})

    @http.route("/api/v1/partner/ping", type="http", auth="public", methods=["GET"], csrf=False)
    @api_endpoint(require_api_key=True, required_feature_code="partner_embedded_access")
    def partner_ping(self, **kwargs):
        return response_builder.success({"service": "partner", "access": "granted"})
