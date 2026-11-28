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
    which has no portal ACL on purpose. Evidence images are returned as
    /faizy/evidence URLs (the session cookie fetches them directly) and only
    once a reviewer has approved them; `proof_visible` / `receipt_visible`
    come from faizy_pilot and are computed with sudo, because the customer
    cannot read the image fields themselves.
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
        # Only reviewed evidence. The raw /web/image URLs are staff-only now;
        # this route is served by faizy_pilot after the record rule and approval.
        "proof_image_url": (
            "/faizy/evidence/%s/proof" % order.id if order.proof_visible else None
        ),
        "receipt_image_url": (
            "/faizy/evidence/%s/receipt" % order.id if order.receipt_visible else None
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

    # ── Sign-up from the app ─────────────────────────────────────────────
    #
    # The one route here that is not behind a session, because the caller
    # has no account yet. Three rules keep an anonymous write safe:
    #
    # 1. Shipped off. Nothing is created unless a Manager sets the system
    #    parameter `faizy.app_signup` to "on" (same pattern as
    #    `faizy.show_plan_prices`). Missing or anything else means off.
    # 2. Never attach to an existing customer. The website's /start matches a
    #    returning customer by phone, which is right there because it hands
    #    back no access. Here the caller walks away with a login, so matching
    #    by phone would give a stranger who knows a customer's number that
    #    customer's family and orders. An email or phone already on file is
    #    refused and the person is sent to sign in or to WhatsApp.
    # 3. Portal user only, never internal.
    #
    # 4. Rate limited. Every attempt, accepted or refused, is counted per
    #    caller address and across all callers, so the route cannot be used
    #    to flood the customer list or to test which numbers are customers.
    #
    # Not done here, and needed before this is switched on for the public:
    # proof that the caller owns the email or the number (docs/app/README.md,
    # gap A1). The limits slow abuse down; they do not prove who is asking.

    _SIGNUP_PARAM = "faizy.app_signup"
    _SIGNUP_MIN_PASSWORD = 8
    _SIGNUP_PER_ADDRESS = 5      # attempts per address per hour
    _SIGNUP_ALL_CALLERS = 60     # attempts from everyone per hour
    _SIGNUP_WINDOW_MINUTES = 60

    def _app_signup_enabled(self):
        value = request.env["ir.config_parameter"].sudo().get_param(self._SIGNUP_PARAM)
        return value == "on"

    @http.route(
        ["/api/care/signup"],
        type="http", auth="public", website=True, methods=["POST"], csrf=False,
    )
    def api_care_signup(self, **kw):
        """Create a customer and their portal login from a JSON body.

        Body: name, phone (WhatsApp number), email, password, and optionally
        country_code (ISO alpha-2). On success the app calls
        `/web/session/authenticate` with the same email and password, exactly
        as for any other login; this route does not open a session itself.
        """
        if not self._app_signup_enabled():
            return request.make_json_response(
                {"ok": False, "error": "signup_closed"}, status=403
            )

        throttle = request.env["faizy.api.throttle"].sudo()
        address = request.httprequest.remote_addr or "unknown"
        within_own = throttle.allow(
            "signup", address, self._SIGNUP_PER_ADDRESS, self._SIGNUP_WINDOW_MINUTES
        )
        within_all = throttle.allow(
            "signup_all", "all", self._SIGNUP_ALL_CALLERS, self._SIGNUP_WINDOW_MINUTES
        )
        if not (within_own and within_all):
            return request.make_json_response(
                {"ok": False, "error": "too_many_attempts"}, status=429
            )

        post = request.get_json_data() or {}
        name = (post.get("name") or "").strip()
        phone = (post.get("phone") or "").strip()
        email = (post.get("email") or "").strip().lower()
        password = post.get("password") or ""
        country_code = (post.get("country_code") or "").strip().upper()

        errors = {}
        if not name:
            errors["name"] = "required"
        if not phone:
            errors["phone"] = "required"
        if not email or "@" not in email or email.startswith("@") or email.endswith("@"):
            errors["email"] = "invalid"
        if len(password) < self._SIGNUP_MIN_PASSWORD:
            errors["password"] = "too_short"
        if errors:
            return request.make_json_response(
                {"ok": False, "errors": errors}, status=400
            )

        env = request.env
        Users = env["res.users"].sudo().with_context(active_test=False)
        Partner = env["res.partner"].sudo().with_context(active_test=False)
        if (
            Users.search_count([("login", "=ilike", email)], limit=1)
            or Partner.search_count([("email", "=ilike", email)], limit=1)
            or Partner.search_count([("phone", "=", phone)], limit=1)
        ):
            # One answer for all three, so the route does not say which of
            # the email or the number is already a customer.
            return request.make_json_response(
                {"ok": False, "error": "already_registered"}, status=409
            )

        country = env["res.country"].sudo().search(
            [("code", "=", country_code)], limit=1
        ) if country_code else env["res.country"]

        partner = env["res.partner"].sudo().create({
            "name": name,
            "phone": phone,
            "email": email,
            "country_id": country.id or False,
            "is_faizy_customer": True,
        })
        env["res.users"].sudo().with_context(no_reset_password=True).create({
            "name": name,
            "login": email,
            "email": email,
            "password": password,
            "partner_id": partner.id,
            "group_ids": [(6, 0, [env.ref("base.group_portal").id])],
        })
        partner.message_post(body=env._("Signed up from the mobile app."))

        return request.make_json_response(
            {"ok": True, "partner": {"id": partner.id, "name": partner.name}}
        )

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
