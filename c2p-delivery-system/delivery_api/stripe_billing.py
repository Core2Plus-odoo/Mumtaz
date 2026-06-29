"""Thin Stripe REST client (urllib, no SDK) for per-tenant subscriptions.

Secrets from the environment ONLY:
  STRIPE_SECRET_KEY        the Stripe secret key
  STRIPE_WEBHOOK_SECRET    to verify webhook signatures (dev: unsigned accepted)
  STRIPE_PRICE_DELIVERY / STRIPE_PRICE_GROWTH / STRIPE_PRICE_AGENCY  price ids
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from typing import Optional

API = "https://api.stripe.com/v1/"


def _key() -> str:
    return (os.getenv("STRIPE_SECRET_KEY") or "").strip()


def configured() -> bool:
    return bool(_key())


def price_for(edition: str) -> Optional[str]:
    return os.getenv(f"STRIPE_PRICE_{(edition or '').upper()}")


def _request(method: str, path: str, data: Optional[dict] = None) -> dict:
    body = urllib.parse.urlencode(data, doseq=True).encode() if data else None
    req = urllib.request.Request(API + path, data=body, method=method)
    req.add_header("Authorization", "Bearer " + _key())
    if body:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def create_customer(name: str, email: str) -> dict:
    return _request("POST", "customers", {"name": name, "email": email})


def create_checkout_session(customer_id: str, price_id: str,
                            success_url: str, cancel_url: str) -> dict:
    return _request("POST", "checkout/sessions", {
        "mode": "subscription",
        "customer": customer_id,
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": 1,
        "success_url": success_url,
        "cancel_url": cancel_url,
    })


def verify_webhook(payload: bytes, sig_header: str) -> Optional[dict]:
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not secret:                                  # dev convenience: accept unsigned
        try:
            return json.loads(payload)
        except Exception:
            return None
    try:
        parts = dict(p.split("=", 1) for p in sig_header.split(","))
        t, v1 = parts.get("t"), parts.get("v1")
        signed = f"{t}.{payload.decode()}".encode()
        expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, v1 or ""):
            return None
        if abs(time.time() - int(t)) > 300:
            return None
        return json.loads(payload)
    except Exception:
        return None
