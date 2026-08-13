from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from .main import whatsapp_url

# WhatsApp openers, each naming the customer's intent so the first message is
# already a sentence. Account changes still leave for WhatsApp — the portal
# does not edit family or plans — but requesting care no longer does.
WA_ADD_MEMBER = "Assalam o Alaikum! I'd like to add a family member to my Faizy account."
WA_CHANGE_PLAN = "Assalam o Alaikum! I'd like to change my Faizy plan."
WA_NEW_TASK = "Assalam o Alaikum! I'd like to ask for help with something."

# A customer with this many unfinished orders is either in trouble or is a
# script. Refused with a message naming the number rather than silently
# dropped, and deliberately high enough that a real family never meets it.
MAX_OPEN_ORDERS = 15


class FaizyCustomerPortal(CustomerPortal):
    """The customer's own view of their account.

    Reads go through the normal portal machinery so the record rules in
    faizy_core apply — a customer sees their own family and orders and nothing
    else. Nothing here uses sudo() on customer data; that would bypass exactly
    the protection this needs.
    """

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        if "faizy_order_count" in counters:
            values["faizy_order_count"] = request.env["faizy.order"].search_count(
                [("partner_id", "=", partner.id)]
            )
        if "faizy_family_count" in counters:
            values["faizy_family_count"] = request.env[
                "faizy.family.member"
            ].search_count([("partner_id", "=", partner.id)])
        return values

    @http.route(["/my/care"], type="http", auth="user", website=True)
    def portal_care_home(self, **kw):
        """One screen answering "how is my family, and what have I got left?"."""
        partner = request.env.user.partner_id
        subscription = partner.faizy_subscription_id

        orders = request.env["faizy.order"]
        family = request.env["faizy.family.member"].search(
            [("partner_id", "=", partner.id)]
        )
        return request.render(
            "faizy_website.portal_care_home",
            {
                "page_name": "faizy_care",
                "partner": partner,
                # Split here rather than in the template: QWeb expressions
                # should not be calling string methods, and a partner with a
                # one-word name still has to greet correctly.
                "first_name": (partner.name or "").split(" ")[0],
                "subscription": subscription,
                "family": family,
                "family_count": len(family),
                "recent_orders": orders.search(
                    [("partner_id", "=", partner.id)], limit=5
                ),
                "order_count": orders.search_count(
                    [("partner_id", "=", partner.id)]
                ),
                "open_count": orders.search_count(
                    [
                        ("partner_id", "=", partner.id),
                        ("state", "not in", ("completed", "cancelled")),
                    ]
                ),
                # None when the company phone is unset — every template that
                # uses these guards on t-if, so the link disappears rather
                # than rendering href="None".
                "wa_add_member": whatsapp_url(WA_ADD_MEMBER),
                "wa_change_plan": whatsapp_url(WA_CHANGE_PLAN),
                "wa_new_task": whatsapp_url(WA_NEW_TASK),
            },
        )

    @http.route(["/my/orders", "/my/orders/page/<int:page>"], type="http", auth="user", website=True)
    def portal_faizy_orders(self, page=1, **kw):
        partner = request.env.user.partner_id
        Order = request.env["faizy.order"]
        domain = [("partner_id", "=", partner.id)]

        total = Order.search_count(domain)
        pager = request.website.pager(
            url="/my/orders",
            total=total,
            page=page,
            step=self._items_per_page,
        )
        orders = Order.search(
            domain, limit=self._items_per_page, offset=pager["offset"]
        )
        return request.render(
            "faizy_website.portal_orders",
            {
                "page_name": "faizy_orders",
                "orders": orders,
                "pager": pager,
                "order_count": total,
                "wa_new_task": whatsapp_url(WA_NEW_TASK),
            },
        )

    @http.route(["/my/orders/<int:order_id>"], type="http", auth="user", website=True)
    def portal_faizy_order_detail(self, order_id, **kw):
        try:
            order = request.env["faizy.order"].browse(order_id)
            # Forces the record rule to run — a foreign id raises rather than
            # rendering someone else's family details.
            order.check_access("read")
            order.read(["name"])
        except (AccessError, MissingError):
            return request.redirect("/my")

        return request.render(
            "faizy_website.portal_order_detail",
            {
                "page_name": "faizy_orders",
                "order": order,
                # Set by the redirect after a request is filed, so the customer
                # lands on a page that confirms it rather than one that merely
                # happens to contain it.
                "just_created": bool(kw.get("new")),
                # The tab bar renders on this page too, and its WhatsApp tab
                # guards on this being present.
                "wa_new_task": whatsapp_url(WA_NEW_TASK),
            },
        )

    # ── Requesting care ──────────────────────────────────────────────────

    def _request_values(self, post=None, errors=None):
        partner = request.env.user.partner_id
        post = post or {}
        return {
            "page_name": "faizy_request",
            "partner": partner,
            "categories": request.env["faizy.service.category"]
            .sudo()
            .search([], order="sequence"),
            "family": request.env["faizy.family.member"].search(
                [("partner_id", "=", partner.id)]
            ),
            "post": post,
            "errors": errors or {},
            "wa_new_task": whatsapp_url(WA_NEW_TASK),
        }

    @http.route(["/my/care/request"], type="http", auth="user", website=True)
    def portal_request_form(self, **kw):
        """The form a customer fills in to ask for something.

        Until now the only way to ask for care was to leave the site for
        WhatsApp. That is the right channel for a conversation and the wrong
        one for "collect Ammi's prescription from the usual pharmacy" — which
        is a form with four fields, and which nobody has to be awake to
        receive.
        """
        return request.render(
            "faizy_website.portal_request_form", self._request_values(kw)
        )

    @http.route(
        ["/my/care/request/submit"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_request_submit(self, **post):
        """Create the order, or re-render the form saying what was wrong.

        `sudo()` on the create, deliberately, and every field that decides
        who this belongs to is taken from the session rather than the form:

          * `partner_id` is `request.env.user.partner_id`, never posted.
          * `family_member_id` is re-read from the customer's own family, so
            posting somebody else's id selects nothing rather than filing an
            order against a stranger's mother.
          * `service_id` must be an active catalogue service.

        The alternative — granting `base.group_portal` create rights on
        faizy.order — would let a portal user set `purchase_value`,
        `service_fee` and `state` over RPC, which is the hole that was just
        closed on the write side. One audited function is a smaller surface
        than a permission.
        """
        partner = request.env.user.partner_id
        errors = {}

        service = (
            request.env["faizy.service"]
            .sudo()
            .search([("id", "=", int(post.get("service_id") or 0)),
                     ("active", "=", True)], limit=1)
        )
        if not service:
            errors["service_id"] = "Choose what you need help with."

        member = request.env["faizy.family.member"]
        if post.get("family_member_id"):
            member = member.search(
                [("id", "=", int(post["family_member_id"])),
                 ("partner_id", "=", partner.id)],
                limit=1,
            )
            if not member:
                errors["family_member_id"] = "Choose someone from your family."

        city = (post.get("city") or "").strip()
        if not city:
            errors["city"] = "Tell us which city, so we send someone close by."

        open_orders = request.env["faizy.order"].search_count(
            [("partner_id", "=", partner.id),
             ("state", "not in", ("completed", "cancelled"))]
        )
        if open_orders >= MAX_OPEN_ORDERS:
            errors["__all__"] = (
                "You already have %s care tasks open. We will finish those "
                "first — message us on WhatsApp if something is urgent."
                % open_orders
            )

        if errors:
            values = self._request_values(post, errors)
            return request.render("faizy_website.portal_request_form", values)

        order = (
            request.env["faizy.order"]
            .sudo()
            .create(
                {
                    "title": service.name,
                    "description": (post.get("description") or "").strip(),
                    "partner_id": partner.id,
                    "family_member_id": member.id or False,
                    "service_id": service.id,
                    "city": city,
                    "street": (post.get("street") or "").strip(),
                    "priority": "1" if post.get("urgent") else "0",
                    # Never trusted from the form: a customer cannot file an
                    # order that is already assigned, already completed, or
                    # carries a purchase value.
                    "state": "pending",
                }
            )
        )
        return request.redirect("/my/orders/%s?new=1" % order.id)
