from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from .main import whatsapp_url

# The portal is read-only on purpose — no forms, no buttons, which is what
# lets portal users hold read access and nothing more. So every "do something"
# link on it has to leave for WhatsApp, which is where the product actually
# takes instructions. Each opener names the customer's intent so the first
# message is already a sentence.
WA_ADD_MEMBER = "Assalam o Alaikum! I'd like to add a family member to my Faizy account."
WA_CHANGE_PLAN = "Assalam o Alaikum! I'd like to change my Faizy plan."
WA_NEW_TASK = "Assalam o Alaikum! I'd like to ask for help with something."


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
            {"page_name": "faizy_orders", "order": order},
        )
