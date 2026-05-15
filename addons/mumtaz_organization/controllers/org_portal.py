import logging
from odoo import http
from odoo.http import request

_log = logging.getLogger(__name__)


class OrgPortalController(http.Controller):

    # ── Public org profile ─────────────────────────────────────────
    @http.route("/org/<slug>", auth="public", website=True, methods=["GET"])
    def org_profile(self, slug, **kwargs):
        org = request.env["mumtaz.organization"].sudo().search(
            [("slug", "=", slug), ("is_public", "=", True), ("state", "=", "active")],
            limit=1,
        )
        if not org:
            return request.not_found()
        return request.render("mumtaz_organization.org_profile", {"org": org})

    # ── SME signup form (GET) ──────────────────────────────────────
    @http.route("/org/<slug>/join", auth="public", website=True, methods=["GET"])
    def org_join(self, slug, **kwargs):
        org = request.env["mumtaz.organization"].sudo().search(
            [("slug", "=", slug), ("is_public", "=", True), ("state", "=", "active")],
            limit=1,
        )
        if not org:
            return request.not_found()
        countries = request.env["res.country"].sudo().search([])
        return request.render("mumtaz_organization.org_join", {
            "org": org,
            "countries": countries,
            "error": kwargs.get("error"),
        })

    # ── SME signup form (POST) ─────────────────────────────────────
    @http.route("/org/<slug>/join", auth="public", website=True, methods=["POST"], csrf=True)
    def org_join_submit(self, slug, **kwargs):
        org = request.env["mumtaz.organization"].sudo().search(
            [("slug", "=", slug), ("is_public", "=", True), ("state", "=", "active")],
            limit=1,
        )
        if not org:
            return request.not_found()

        company_name = (kwargs.get("company_name") or "").strip()
        contact_name = (kwargs.get("contact_name") or "").strip()
        email        = (kwargs.get("email") or "").strip()
        phone        = (kwargs.get("phone") or "").strip()
        country_id   = int(kwargs.get("country_id") or 0) or False
        industry     = (kwargs.get("industry") or "").strip()
        website      = (kwargs.get("website") or "").strip()
        message      = (kwargs.get("message") or "").strip()

        if not company_name or not contact_name or not email:
            countries = request.env["res.country"].sudo().search([])
            return request.render("mumtaz_organization.org_join", {
                "org": org,
                "countries": countries,
                "error": "Please fill in company name, contact name, and email.",
                "values": kwargs,
            })

        try:
            request.env["mumtaz.sme.signup"].sudo().create({
                "org_id": org.id,
                "company_name": company_name,
                "contact_name": contact_name,
                "email": email,
                "phone": phone,
                "country_id": country_id,
                "industry": industry,
                "website": website,
                "message": message,
            })
        except Exception:
            _log.exception("SME signup failed for org=%s email=%s", slug, email)
            countries = request.env["res.country"].sudo().search([])
            return request.render("mumtaz_organization.org_join", {
                "org": org,
                "countries": countries,
                "error": "Something went wrong. Please try again.",
                "values": kwargs,
            })

        return request.render("mumtaz_organization.org_join_success", {"org": org})

    # ── General SME registration landing ──────────────────────────
    @http.route("/org/register", auth="public", website=True, methods=["GET"])
    def org_register(self, **kwargs):
        orgs = request.env["mumtaz.organization"].sudo().search(
            [("is_public", "=", True), ("state", "=", "active")],
            order="name",
        )
        return request.render("mumtaz_organization.org_register", {"orgs": orgs})
