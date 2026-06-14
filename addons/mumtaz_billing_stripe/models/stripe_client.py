import hashlib
import hmac
import logging
import os
import time

import requests

from odoo import api, models

_logger = logging.getLogger(__name__)

_STRIPE_API_BASE = "https://api.stripe.com/v1"
_HTTP_TIMEOUT = 20
_WEBHOOK_TOLERANCE = 300  # seconds


class StripeError(Exception):
    """Raised for Stripe API failures. The .user_message is safe to surface;
    the underlying detail is logged server-side only."""

    def __init__(self, user_message, detail=None, code=None):
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail
        self.code = code


class MumtazStripeClient(models.AbstractModel):
    """Thin Stripe REST client. Secrets come from the environment
    (/opt/mumtaz/.env), never the database."""
    _name = "mumtaz.stripe.client"
    _description = "Mumtaz Stripe API Client"

    # ── Secret access (environment only) ──────────────────────────────────
    @api.model
    def _secret_key(self):
        return (os.environ.get("STRIPE_SECRET_KEY") or "").strip()

    @api.model
    def _webhook_secret(self):
        return (os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()

    @api.model
    def _is_configured(self):
        return bool(self._secret_key())

    # ── Core request ──────────────────────────────────────────────────────
    @api.model
    def _request(self, method, path, data=None, idempotency_key=None):
        secret = self._secret_key()
        if not secret:
            raise StripeError(
                "Stripe is not configured. Set STRIPE_SECRET_KEY in /opt/mumtaz/.env.",
                detail="STRIPE_SECRET_KEY missing",
            )
        headers = {"Authorization": f"Bearer {secret}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        url = f"{_STRIPE_API_BASE}/{path.lstrip('/')}"
        try:
            resp = requests.request(
                method, url, headers=headers, data=data or {}, timeout=_HTTP_TIMEOUT
            )
        except requests.exceptions.Timeout:
            raise StripeError("Stripe request timed out. Please try again.",
                              detail=f"timeout {method} {path}")
        except requests.exceptions.RequestException as exc:
            raise StripeError("Could not reach Stripe.", detail=str(exc))

        payload = {}
        try:
            payload = resp.json()
        except ValueError:
            pass

        if resp.status_code >= 400:
            err = (payload or {}).get("error", {})
            # Never surface raw Stripe internals; log them, return a safe message.
            _logger.warning(
                "Stripe API error %s on %s %s: %s",
                resp.status_code, method, path, err,
            )
            raise StripeError(
                err.get("message") or "Stripe rejected the request.",
                detail=f"{resp.status_code} {err}",
                code=err.get("code") or err.get("decline_code"),
            )
        return payload

    # ── High-level helpers ────────────────────────────────────────────────
    @api.model
    def create_customer(self, name, email, metadata=None):
        data = {"name": name or "", "email": email or ""}
        for key, val in (metadata or {}).items():
            data[f"metadata[{key}]"] = val
        return self._request("POST", "customers", data)

    @api.model
    def create_setup_intent(self, customer_id):
        return self._request("POST", "setup_intents", {
            "customer": customer_id,
            "usage": "off_session",
            "payment_method_types[]": "card",
        })

    @api.model
    def create_payment_intent(self, *, amount_minor, currency, customer_id,
                              payment_method_id, metadata=None, idempotency_key=None):
        data = {
            "amount": amount_minor,
            "currency": currency.lower(),
            "customer": customer_id,
            "payment_method": payment_method_id,
            "off_session": "true",
            "confirm": "true",
        }
        for key, val in (metadata or {}).items():
            data[f"metadata[{key}]"] = val
        return self._request("POST", "payment_intents", data,
                             idempotency_key=idempotency_key)

    # ── Webhook signature verification ────────────────────────────────────
    @api.model
    def verify_webhook(self, raw_body, sig_header):
        """Validate a Stripe-Signature header. Returns True/False.
        raw_body must be the exact bytes/str received."""
        secret = self._webhook_secret()
        if not secret or not sig_header:
            return False
        ts = None
        signatures = []
        for part in sig_header.split(","):
            if "=" not in part:
                continue
            label, _, value = part.partition("=")
            label = label.strip()
            if label == "t":
                ts = value.strip()
            elif label == "v1":
                signatures.append(value.strip())
        if not ts or not signatures:
            return False
        # Reject stale timestamps (replay protection).
        try:
            if abs(time.time() - int(ts)) > _WEBHOOK_TOLERANCE:
                return False
        except (TypeError, ValueError):
            return False
        if isinstance(raw_body, bytes):
            raw_body = raw_body.decode("utf-8")
        signed_payload = f"{ts}.{raw_body}".encode("utf-8")
        expected = hmac.new(secret.encode("utf-8"), signed_payload,
                            hashlib.sha256).hexdigest()
        return any(hmac.compare_digest(expected, sig) for sig in signatures)
