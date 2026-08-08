import re

from odoo import fields, http
from odoo.http import request

# 00000-0000000-0
CNIC_RE = re.compile(r"^\d{5}-\d{7}-\d$")


class FaizyWebsite(http.Controller):
    """Public pages: the pitch, the pricing, and the worker sign-up."""

    @http.route("/", type="http", auth="public", website=True, sitemap=True)
    def faizy_home(self, **kw):
        plans = (
            request.env["faizy.plan"]
            .sudo()
            .search([("active", "=", True)], order="sequence")
        )
        services = (
            request.env["faizy.service"]
            .sudo()
            .search([("active", "=", True)], order="sequence")
        )
        return request.render(
            "faizy_website.home", {"plans": plans, "services": services}
        )

    @http.route("/pricing", type="http", auth="public", website=True, sitemap=True)
    def faizy_pricing(self, **kw):
        plans = (
            request.env["faizy.plan"]
            .sudo()
            .search([("active", "=", True)], order="sequence")
        )
        return request.render("faizy_website.pricing", {"plans": plans})

    # ── Worker sign-up ───────────────────────────────────────────────────

    @http.route("/join", type="http", auth="public", website=True, sitemap=True)
    def faizy_join(self, **kw):
        env = request.env
        return request.render(
            "faizy_website.join",
            {
                "services": env["faizy.service"].sudo().search([("active", "=", True)]),
                "areas": env["faizy.area"].sudo().search([("active", "=", True)]),
                "values": kw,
                "errors": {},
            },
        )

    @http.route(
        "/join/submit",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def faizy_join_submit(self, **post):
        """Accept an application from the public form.

        Validated server-side regardless of what the browser enforced — this
        endpoint is reachable directly.

        ⚠️ Anonymous POST needs abuse protection that application code cannot
        provide on its own. Put a CAPTCHA or per-IP rate limit in front of this
        before launch; the honeypot below stops naive bots and nothing more.
        """
        errors = {}

        # Honeypot: a real person never fills a hidden field.
        if post.get("website"):
            return request.redirect("/join/thanks?ref=")

        name = (post.get("name") or "").strip()
        phone = (post.get("phone") or "").strip()
        cnic = (post.get("cnic") or "").strip()
        city = (post.get("city") or "").strip()

        if not name:
            errors["name"] = "Please tell us your full name."
        if not phone:
            errors["phone"] = "We need a phone number to reach you on."
        if not CNIC_RE.match(cnic):
            errors["cnic"] = "CNIC should look like 00000-0000000-0."
        if not city:
            errors["city"] = "Which city do you work in?"
        if not post.get("code_of_conduct"):
            errors["code_of_conduct"] = "Please accept the code of conduct."
        if not post.get("rate_card"):
            errors["rate_card"] = "Please accept the rate card."

        if errors:
            env = request.env
            return request.render(
                "faizy_website.join",
                {
                    "services": env["faizy.service"].sudo().search([("active", "=", True)]),
                    "areas": env["faizy.area"].sudo().search([("active", "=", True)]),
                    "values": post,
                    "errors": errors,
                },
            )

        service_ids = [int(i) for i in request.httprequest.form.getlist("service_ids")]
        area_ids = [int(i) for i in request.httprequest.form.getlist("area_ids")]

        application = (
            request.env["faizy.application"]
            .sudo()
            .create(
                {
                    "name": name,
                    "phone": phone,
                    "cnic": cnic,
                    "email": (post.get("email") or "").strip() or False,
                    "city": city,
                    "service_ids": [(6, 0, service_ids)],
                    "area_ids": [(6, 0, area_ids)],
                    "availability": post.get("availability") or False,
                    "has_vehicle": bool(post.get("has_vehicle")),
                    "vehicle_type": post.get("vehicle_type") or False,
                    "experience_years": int(post.get("experience_years") or 0),
                    "experience_notes": post.get("experience_notes") or False,
                    "reference_contacts": post.get("reference_contacts") or False,
                    "code_of_conduct_accepted": True,
                    "rate_card_accepted": True,
                    "date_accepted": fields.Datetime.now(),
                }
            )
        )
        return request.redirect(f"/join/thanks?ref={application.reference}")

    @http.route("/join/thanks", type="http", auth="public", website=True, sitemap=False)
    def faizy_join_thanks(self, ref=None, **kw):
        return request.render("faizy_website.join_thanks", {"reference": ref})

    @http.route(
        "/join/status", type="http", auth="public", website=True, sitemap=False
    )
    def faizy_join_status(self, reference=None, phone=None, **kw):
        """Let an applicant check progress with their reference plus phone.

        Both are required together — a reference number alone would let anyone
        enumerate applications, which hold CNICs and selfies.
        """
        application = None
        searched = bool(reference and phone)
        if searched:
            application = (
                request.env["faizy.application"]
                .sudo()
                .search(
                    [
                        ("reference", "=", reference.strip().upper()),
                        ("phone", "=", phone.strip()),
                    ],
                    limit=1,
                )
            )
        return request.render(
            "faizy_website.join_status",
            {
                "application": application,
                "searched": searched,
                "reference": reference,
                "phone": phone,
            },
        )
