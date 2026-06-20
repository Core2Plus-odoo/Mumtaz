import json
import logging

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class MumtazStripeWebhook(http.Controller):

    @http.route("/mumtaz/stripe/webhook", type="http", auth="public",
                methods=["POST"], csrf=False, save_session=False)
    def stripe_webhook(self, **kwargs):
        raw = request.httprequest.get_data(as_text=True)
        sig = request.httprequest.headers.get("Stripe-Signature", "")
        client = request.env["mumtaz.stripe.client"].sudo()

        if not client.verify_webhook(raw, sig):
            _logger.warning("Stripe webhook rejected: invalid signature.")
            return Response("invalid signature", status=400)

        try:
            event = json.loads(raw)
        except ValueError:
            return Response("bad payload", status=400)

        event_id = event.get("id")
        event_type = event.get("type")
        if not event_id:
            return Response("missing id", status=400)

        Event = request.env["mumtaz.stripe.event"].sudo()
        # Idempotency: a duplicate delivery is acknowledged but not reprocessed.
        if Event.search_count([("stripe_event_id", "=", event_id)]):
            return Response("ok", status=200)

        log = Event.create({"stripe_event_id": event_id, "event_type": event_type})
        try:
            self._dispatch(event, log)
            log.processed = True
        except Exception as exc:  # noqa: BLE001 - never leak internals to Stripe
            _logger.exception("Stripe webhook processing error (%s): %s",
                              event_type, exc)
            log.note = "processing error"
            # 200 so Stripe doesn't retry a poison event indefinitely; we have
            # the record and can reprocess manually.
        return Response("ok", status=200)

    # ── Dispatch ──────────────────────────────────────────────────────────
    def _dispatch(self, event, log):
        obj = (event.get("data") or {}).get("object") or {}
        etype = event.get("type")
        if etype == "setup_intent.succeeded":
            self._handle_setup_intent(obj, log)
        elif etype == "payment_intent.succeeded":
            self._handle_payment_success(obj, log)
        elif etype in ("payment_intent.payment_failed", "payment_intent.canceled"):
            self._handle_payment_failure(obj, log)
        else:
            log.note = "ignored"

    def _tenant_from_customer(self, customer_id):
        if not customer_id:
            return request.env["mumtaz.tenant"]
        return request.env["mumtaz.tenant"].sudo().search(
            [("stripe_customer_id", "=", customer_id)], limit=1
        )

    def _subscription_from_meta(self, obj):
        meta = obj.get("metadata") or {}
        sub_id = meta.get("subscription_id")
        customer_id = obj.get("customer")
        Sub = request.env["mumtaz.subscription"].sudo()
        if sub_id:
            sub = Sub.browse(int(sub_id))
            if sub.exists():
                # Cross-validate: subscription must belong to the same Stripe customer
                # as the payment object to prevent metadata injection.
                if customer_id and sub.tenant_id.stripe_customer_id != customer_id:
                    _logger.warning(
                        "Webhook metadata mismatch: sub %s has customer %s but "
                        "payload customer is %s — ignoring",
                        sub_id, sub.tenant_id.stripe_customer_id, customer_id,
                    )
                    return Sub
                return sub
        return Sub

    def _handle_setup_intent(self, obj, log):
        tenant = self._tenant_from_customer(obj.get("customer"))
        pm_id = obj.get("payment_method")
        if not tenant or not pm_id:
            log.note = "setup_intent: tenant/pm not found"
            return
        card = None
        try:
            pm = request.env["mumtaz.stripe.client"].sudo()._request(
                "GET", f"payment_methods/{pm_id}"
            )
            card = pm.get("card")
        except Exception:  # noqa: BLE001 - card detail is best-effort
            card = None
        tenant._set_default_payment_method(pm_id, card=card)
        log.tenant_id = tenant.id
        log.note = "card saved"

    def _handle_payment_success(self, obj, log):
        sub = self._subscription_from_meta(obj)
        intent_id = obj.get("id")
        if not sub:
            log.note = "payment success: subscription not found"
            return
        log.subscription_id = sub.id
        log.tenant_id = sub.tenant_id.id
        # Idempotency: skip if this intent already produced a billing record.
        already = request.env["mumtaz.subscription.billing.record"].sudo().search_count(
            [("external_reference", "=", intent_id)]
        )
        if already or (sub.payment_status == "paid"
                       and sub.external_billing_ref == intent_id):
            log.note = "already applied"
            return
        amount = sub.outstanding_amount or sub.plan_id.list_price
        sub._stripe_mark_paid(intent_id, amount)
        log.note = "marked paid"

    def _handle_payment_failure(self, obj, log):
        sub = self._subscription_from_meta(obj)
        if not sub:
            log.note = "payment failure: subscription not found"
            return
        log.subscription_id = sub.id
        log.tenant_id = sub.tenant_id.id
        if sub.payment_status == "paid":
            log.note = "ignored (already paid)"
            return
        err = (obj.get("last_payment_error") or {}).get("message") or "payment failed"
        sub._stripe_mark_failed(err)
        log.note = "marked overdue"
