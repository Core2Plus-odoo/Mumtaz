"""
Stripe Checkout + webhook helpers for Mumtaz.

Internal plan keys are mapped to Stripe Price IDs via environment variables:
    STRIPE_PRICE_STARTER  = price_xxx
    STRIPE_PRICE_GROWTH   = price_xxx
    STRIPE_PRICE_SCALE    = price_xxx
    STRIPE_SECRET_KEY     = sk_live_... or sk_test_...
    STRIPE_WEBHOOK_SECRET = whsec_...

If STRIPE_SECRET_KEY is unset, billing endpoints will return a clear error
so the front-end can fall back to the current direct-plan-change flow.
"""

import os, sqlite3
from typing import Optional

import settings_store as store

try:
    import stripe  # type: ignore
except ImportError:  # pragma: no cover — package optional during dev
    stripe = None  # type: ignore


def _key() -> Optional[str]:
    k = (store.get("STRIPE_SECRET_KEY", "") or "").strip()
    return k or None


def is_configured() -> bool:
    return _key() is not None and stripe is not None


def _init():
    """Set the API key on the stripe module (idempotent)."""
    if stripe is None:
        return
    stripe.api_key = _key()


PLAN_TO_PRICE_ENV = {
    "starter": "STRIPE_PRICE_STARTER",
    "growth":  "STRIPE_PRICE_GROWTH",
    "scale":   "STRIPE_PRICE_SCALE",
}

def price_id_for(plan_key: str) -> Optional[str]:
    env = PLAN_TO_PRICE_ENV.get(plan_key)
    if not env:
        return None
    pid = (store.get(env, "") or "").strip()
    return pid or None


def get_or_create_customer(email: str, name: str | None) -> Optional[str]:
    """Look up an existing Stripe customer by email, or create one. Returns customer id."""
    if not is_configured():
        return None
    _init()
    existing = stripe.Customer.list(email=email, limit=1)
    if existing.data:
        return existing.data[0].id
    cust = stripe.Customer.create(
        email=email,
        name=name or None,
        metadata={"source": "mumtaz-portal"},
    )
    return cust.id


def create_checkout_session(*, email: str, name: str | None, plan_key: str,
                            success_url: str, cancel_url: str) -> str:
    """Create a Stripe Checkout Session for a subscription. Returns the session URL."""
    if not is_configured():
        raise RuntimeError("Stripe is not configured (STRIPE_SECRET_KEY missing).")
    _init()
    price = price_id_for(plan_key)
    if not price:
        raise RuntimeError(f"No Stripe price configured for plan '{plan_key}'.")

    customer_id = get_or_create_customer(email, name)
    sess = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        allow_promotion_codes=True,
        billing_address_collection="auto",
        metadata={"plan": plan_key, "email": email},
        subscription_data={"metadata": {"plan": plan_key, "email": email}},
    )
    return sess.url


def create_portal_session(*, email: str, return_url: str) -> str:
    """Create a Customer Portal session so users can manage their subscription."""
    if not is_configured():
        raise RuntimeError("Stripe is not configured.")
    _init()
    customer_id = get_or_create_customer(email, None)
    sess = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return sess.url


def parse_webhook(payload: bytes, signature_header: str | None):
    """Verify a webhook signature and return the parsed event. Raises on invalid signature."""
    if not is_configured():
        raise RuntimeError("Stripe not configured.")
    _init()
    secret = (store.get("STRIPE_WEBHOOK_SECRET", "") or "").strip()
    if not secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET missing.")
    return stripe.Webhook.construct_event(payload, signature_header or "", secret)


# ── Plan mapping back from Stripe ───────────────────────────────────

def plan_from_event(event_obj: dict) -> Optional[str]:
    """Best-effort extraction of internal plan key from a webhook event."""
    md = (event_obj.get("metadata") or {})
    plan = md.get("plan")
    if plan:
        return plan
    items = (event_obj.get("items") or {}).get("data") or []
    for it in items:
        price_id = (it.get("price") or {}).get("id")
        if not price_id:
            continue
        for plan_key, env in PLAN_TO_PRICE_ENV.items():
            if price_id == (store.get(env, "") or "").strip():
                return plan_key
    return None


def email_from_event(event_obj: dict) -> Optional[str]:
    md = (event_obj.get("metadata") or {})
    if md.get("email"):
        return md["email"]
    if event_obj.get("customer_email"):
        return event_obj["customer_email"]
    return None
