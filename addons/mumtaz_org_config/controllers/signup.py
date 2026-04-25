"""
SME Organisation signup API endpoint.

POST /mumtaz/org/signup  — creates a mumtaz.org in 'pending' state.
GET  /mumtaz/org/check   — checks slug availability.
"""
import json
import logging
import re

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$")
_RESERVED = frozenset({
    "admin", "api", "app", "www", "mail", "smtp", "support",
    "help", "mumtaz", "platform", "portal", "vendor", "marketplace",
})


class OrgSignupController(http.Controller):

    # ── Slug availability check ───────────────────────────────────────────

    @http.route(
        "/mumtaz/org/check",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def check_slug(self, slug="", **_kw):
        slug = (slug or "").strip().lower()
        if not slug:
            return {"available": False, "reason": "empty"}
        if slug in _RESERVED:
            return {"available": False, "reason": "reserved"}
        if not _SLUG_RE.match(slug):
            return {"available": False, "reason": "invalid"}
        exists = request.env["mumtaz.org"].sudo().search_count(
            [("slug", "=", slug)]
        )
        return {"available": exists == 0, "slug": slug}

    # ── Organisation signup ───────────────────────────────────────────────

    @http.route(
        "/mumtaz/org/signup",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def org_signup(self, **kw):
        name       = (kw.get("name") or "").strip()
        slug       = (kw.get("slug") or "").strip().lower()
        admin_email = (kw.get("admin_email") or "").strip().lower()
        admin_name  = (kw.get("admin_name") or "").strip()
        phone       = (kw.get("phone") or "").strip()
        country_code = (kw.get("country") or "").strip().upper()

        # Validation
        errors = {}
        if not name:
            errors["name"] = "Organisation name is required."
        if not slug:
            errors["slug"] = "URL slug is required."
        elif slug in _RESERVED or not _SLUG_RE.match(slug):
            errors["slug"] = "Invalid or reserved slug."
        elif request.env["mumtaz.org"].sudo().search_count([("slug", "=", slug)]):
            errors["slug"] = "This slug is already taken."
        if not admin_email or "@" not in admin_email:
            errors["admin_email"] = "A valid email address is required."
        if errors:
            return {"success": False, "errors": errors}

        country = None
        if country_code:
            country = request.env["res.country"].sudo().search(
                [("code", "=", country_code)], limit=1
            )

        try:
            org = request.env["mumtaz.org"].sudo().create({
                "name":        name,
                "slug":        slug,
                "admin_email": admin_email,
                "admin_name":  admin_name or admin_email,
                "phone":       phone or False,
                "country_id":  country.id if country else False,
                "plan":        "trial",
                "state":       "pending",
            })
            _logger.info("Org signup: %s (%s) by %s", name, slug, admin_email)
        except Exception as exc:
            _logger.exception("Org signup failed: %s", exc)
            return {"success": False, "errors": {"_": "Internal error. Please try again."}}

        return {
            "success": True,
            "org_id": org.id,
            "slug":   org.slug,
            "url":    org.subdomain_url,
            "message": (
                f"Your organisation '{name}' has been registered at "
                f"{org.subdomain_url}. Our team will activate it within 24 hours."
            ),
        }
