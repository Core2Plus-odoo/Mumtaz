from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from .main import whatsapp_url
from .portal import (
    WA_ADD_MEMBER,
    WA_CHANGE_PLAN,
    WA_NEW_TASK,
    FaizyCustomerPortal,
)


# ── Serializers ──────────────────────────────────────────────────────────
#
# One function per model, called from every route that touches that model, so
# the same order never gets described two different ways depending on which
# endpoint returned it. Dates and Monetary values are converted explicitly
# rather than left for json.dumps to choke on.

def _family_member(member):
    return {
        "id": member.id,
        "name": member.name,
        "relationship": member.relationship,
        "relationship_label": dict(
            member._fields["relationship"].selection
        ).get(member.relationship),
        "city": member.city or None,
        "fmb_id": member.fmb_id,
    }


def _family_row(row):
    """A `_member_rows()` dict — {member, hint, tone} — as JSON."""
    data = _family_member(row["member"])
    data["hint"] = row["hint"]
    data["tone"] = row["tone"]
    return data


def _subscription(sub):
    if not sub:
        return None
    return {
        "id": sub.id,
        "plan": sub.plan_id.name,
        "state": sub.state,
        "activities_used": sub.activities_used,
        "activities_included": sub.activities_included,
        "activities_remaining": sub.activities_remaining,
        "period_end": sub.period_end.isoformat() if sub.period_end else None,
        "currency": sub.currency_id.name,
    }


def _order_summary(order):
    return {
        "id": order.id,
        "name": order.name,
        "title": order.title,
        "state": order.state,
        "state_label": dict(order._fields["state"].selection).get(order.state),
        "priority": order.priority,
        "is_urgent": order.priority == "1",
        "family_member": order.family_member_id.name or None,
        "fmb_id": order.fmb_id or None,
        "created_at": order.create_date.isoformat() if order.create_date else None,
        "amount_total": order.amount_total,
        "currency": order.currency_id.name,
    }


def _order_detail(order):
    """Everything the web order-detail page shows, and nothing it doesn't.

    `worker_name` is read via sudo() for the same reason the HTML route does
    it that way: the customer is entitled to know who is coming, not to the
    roster faizy.worker carries alongside it — cnic, phone, email, base_rate —
    which has no portal ACL on purpose. Images are returned as the same
    /web/image URL the browser uses, which the app's session cookie can fetch
    directly; the truthiness check on the field mirrors the QWeb template's
    `t-if`, which already accepts the cost of reading the image to know that.
    """
    data = _order_summary(order)
    data.update({
        "service": order.service_id.name,
        "city": order.city,
        "street": order.street or None,
        "worker_name": order.worker_id.sudo().name or None,
        "description": order.description or None,
        "completion_note": order.completion_note or None,
        "receipt_note": order.receipt_note or None,
        "proof_image_url": (
            "/web/image/faizy.order/%s/proof_image" % order.id
            if order.proof_image else None
        ),
        "receipt_image_url": (
            "/web/image/faizy.order/%s/receipt_image" % order.id
            if order.receipt_image else None
        ),
        "purchase_value": order.purchase_value,
        "service_fee": order.service_fee,
        "platform_fee": order.platform_fee,
        "privacy_mode": order.privacy_mode,
        "scheduled_date": (
            order.scheduled_date.isoformat() if order.scheduled_date else None
        ),
    })
    return data


def _catalog():
    categories = (
        request.env["faizy.service.category"].sudo().search([], order="sequence")
    )
    out = []
    for category in categories:
        services = category.service_ids.filtered("active")
        if not services:
            continue
        out.append({
            "id": category.id,
            "name": category.name,
            "icon": category.icon or None,
            "services": [
                {
                    "id": service.id,
                    "name": service.name,
                    "icon": service.icon or category.icon or None,
                    "description": service.description or None,
                }
                for service in services
            ],
        })
    return out


class FaizyCareAPI(FaizyCustomerPortal):
    """The JSON data API behind /care, for the Android/iOS app.

    Same server, same models, same rules as the web portal — this is a data
    facade in front of it, not a second backend. Every route below reuses the
    exact validation the web form uses (`_create_care_request`, `_needs_plan`,
    `_member_rows`, inherited from FaizyCustomerPortal) rather than
    re-implementing it, so a booking cannot be accepted by the app and
    refused by the website, or the free-activity gate enforced in one place
    and forgotten in the other.

    Auth is the same session cookie a web login sets. There is deliberately
    no login route here: call Odoo's own `/web/session/authenticate` — plain
    JSON-RPC, unchanged across Odoo versions, exactly what the website login
    page itself calls — to establish the session, then every route below
    checks it the same way the website does (`auth="user"`). Reimplementing
    login would mean duplicating password verification and lockout behaviour
    Odoo already gets right, to save the mobile client one JSON-RPC envelope.

    `csrf=False` throughout: CSRF is an attack where a page in the victim's
    *browser* forges a request using cookies the browser attaches
    automatically. A native app is not a browser tab and does not attach
    this session cookie to requests it did not make itself, so the attack
    this token defends against does not apply here — `auth="user"` still
    requires the caller to hold a real session.
    """

    _ITEMS_PER_PAGE = 30

    @http.route(["/api/care/home"], type="http", auth="user", website=True, csrf=False)
    def api_care_home(self, **kw):
        partner = request.env.user.partner_id
        orders = request.env["faizy.order"]
        family = request.env["faizy.family.member"].search(
            [("partner_id", "=", partner.id)]
        )

        return request.make_json_response({
            "partner": {
                "id": partner.id,
                "name": partner.name,
                "first_name": (partner.name or "").split(" ")[0],
            },
            "free_activities": partner.faizy_free_activities,
            "needs_plan": self._needs_plan(partner),
            "subscription": _subscription(partner.faizy_subscription_id),
            "family": [_family_row(r) for r in self._member_rows(family)],
            "family_count": len(family),
            "order_count": orders.search_count([("partner_id", "=", partner.id)]),
            "open_count": orders.search_count([
                ("partner_id", "=", partner.id),
                ("state", "not in", ("completed", "cancelled")),
            ]),
            "recent_orders": [
                _order_summary(o)
                for o in orders.search([("partner_id", "=", partner.id)], limit=5)
            ],
            "wa_new_task": whatsapp_url(WA_NEW_TASK),
            "wa_add_member": whatsapp_url(WA_ADD_MEMBER),
            "wa_change_plan": whatsapp_url(WA_CHANGE_PLAN),
        })

    @http.route(["/api/care/orders"], type="http", auth="user", website=True, csrf=False)
    def api_care_orders(self, page="1", **kw):
        partner = request.env.user.partner_id
        Order = request.env["faizy.order"]
        domain = [("partner_id", "=", partner.id)]

        try:
            page_num = max(int(page), 1)
        except (TypeError, ValueError):
            page_num = 1

        step = self._ITEMS_PER_PAGE
        total = Order.search_count(domain)
        orders = Order.search(domain, limit=step, offset=(page_num - 1) * step)

        return request.make_json_response({
            "orders": [_order_summary(o) for o in orders],
            "page": page_num,
            "page_size": step,
            "total": total,
        })

    @http.route(
        ["/api/care/orders/<int:order_id>"],
        type="http", auth="user", website=True, csrf=False,
    )
    def api_care_order_detail(self, order_id, **kw):
        try:
            order = request.env["faizy.order"].browse(order_id)
            # Forces the record rule to run — a foreign id raises rather than
            # returning someone else's family details as JSON.
            order.check_access("read")
            order.read(["name"])
        except (AccessError, MissingError):
            return request.make_json_response({"error": "not_found"}, status=404)

        return request.make_json_response(_order_detail(order))

    @http.route(
        ["/api/care/request/options"],
        type="http", auth="user", website=True, csrf=False,
    )
    def api_care_request_options(self, **kw):
        partner = request.env.user.partner_id
        family = request.env["faizy.family.member"].search(
            [("partner_id", "=", partner.id)]
        )
        return request.make_json_response({
            "needs_plan": self._needs_plan(partner),
            "categories": _catalog(),
            "family": [_family_member(m) for m in family],
            "wa_new_task": whatsapp_url(WA_NEW_TASK),
        })

    @http.route(
        ["/api/care/request"],
        type="http", auth="user", website=True, methods=["POST"], csrf=False,
    )
    def api_care_request_submit(self, **kw):
        """Create an order from a JSON body.

        Body shape mirrors the web form's POST fields exactly — service_id,
        family_member_id, city, street, scheduled_date (YYYY-MM-DD),
        description, urgent, privacy_mode — because `_create_care_request`
        is the same function the web form calls and expects the same keys.
        """
        partner = request.env.user.partner_id
        post = request.get_json_data() or {}

        if self._needs_plan(partner):
            return request.make_json_response(
                {"ok": False, "needs_plan": True}, status=402
            )

        order, errors = self._create_care_request(partner, post)
        if errors:
            return request.make_json_response(
                {"ok": False, "errors": errors}, status=400
            )

        return request.make_json_response({"ok": True, "order": _order_summary(order)})
