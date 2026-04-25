"""
ZATCA Phase 2 e-invoicing scaffold (Saudi Arabia).

This module is a SCAFFOLD. It implements the parts that don't require
production certificates (TLV-encoded QR codes, status checks) and exposes
a clean API surface for the parts that do (CSID onboarding, signing,
clearance, reporting). Replace the stubs with real ZATCA SDK calls when
you have production credentials.

Required env vars (all optional — module is gated by zatca_configured()):
    ZATCA_ENV          = sandbox | simulation | production
    ZATCA_VAT_NUMBER   = 15-digit VAT number (e.g. 300000000000003)
    ZATCA_SELLER_NAME  = legal name of the seller
    ZATCA_CSID         = CSID from compliance API (after onboarding)
    ZATCA_PRIVATE_KEY  = base64 PEM private key (after CSR generation)

Reference: https://zatca.gov.sa/en/E-Invoicing/Pages/default.aspx
"""

from __future__ import annotations

import base64
import os
from datetime import datetime, timezone


# ── Configuration ──────────────────────────────────────────────────

def zatca_env() -> str:
    return (os.environ.get("ZATCA_ENV") or "").strip().lower()


def is_configured() -> bool:
    """True if at minimum the VAT number + seller name are set.
    Cryptographic operations require ZATCA_CSID + ZATCA_PRIVATE_KEY too."""
    return bool(
        (os.environ.get("ZATCA_VAT_NUMBER") or "").strip() and
        (os.environ.get("ZATCA_SELLER_NAME") or "").strip()
    )


def has_credentials() -> bool:
    """True when CSID + private key are loaded — required for signing."""
    return bool(
        (os.environ.get("ZATCA_CSID") or "").strip() and
        (os.environ.get("ZATCA_PRIVATE_KEY") or "").strip()
    )


def status() -> dict:
    return {
        "configured":     is_configured(),
        "has_credentials": has_credentials(),
        "env":            zatca_env() or "not-set",
        "vat_number":     os.environ.get("ZATCA_VAT_NUMBER", "") if is_configured() else None,
        "seller_name":    os.environ.get("ZATCA_SELLER_NAME", "") if is_configured() else None,
    }


# ── TLV (Tag-Length-Value) QR encoding per ZATCA spec ─────────────

def _tlv(tag: int, value: str | bytes) -> bytes:
    """Encode a single TLV tuple. Tag 1 byte, length 1 byte (UTF-8 bytes), then value."""
    if isinstance(value, str):
        value = value.encode("utf-8")
    if len(value) > 255:
        raise ValueError(f"TLV value too long for tag {tag}: {len(value)} bytes")
    return bytes([tag, len(value)]) + value


def build_qr(*, seller_name: str, vat_number: str, timestamp: str,
             total_with_vat: str, vat_amount: str) -> str:
    """Return a base64 string suitable for embedding in a QR code on a
    simplified tax invoice, per ZATCA Phase 1 spec.

    timestamp must be ISO 8601 UTC, e.g. '2024-04-25T10:30:00Z'.
    Amounts are strings to preserve formatting (e.g. '1150.00').
    """
    payload = (
        _tlv(1, seller_name) +
        _tlv(2, vat_number) +
        _tlv(3, timestamp) +
        _tlv(4, total_with_vat) +
        _tlv(5, vat_amount)
    )
    return base64.b64encode(payload).decode("ascii")


# ── Stubs — replace with real ZATCA API calls in production ────────

def onboard(otp: str) -> dict:
    """Onboarding step 1: exchange ZATCA-issued OTP for a CSID.

    PRODUCTION: POST to /onboarding/v2/CSID with the CSR generated from
    ZATCA_PRIVATE_KEY. Returns a CSID + secret to be persisted.
    """
    if not is_configured():
        raise RuntimeError("ZATCA not configured (set ZATCA_VAT_NUMBER + ZATCA_SELLER_NAME).")
    if not otp:
        raise ValueError("OTP required.")
    return {
        "stub": True,
        "message": "Onboarding endpoint is a stub. Wire up ZATCA Compliance CSID API to issue real credentials.",
    }


def submit_invoice(*, invoice_xml: str, kind: str = "standard") -> dict:
    """Submit an invoice to ZATCA.

    kind == 'simplified'  → /reporting/single   (B2C, after-the-fact)
    kind == 'standard'    → /invoices/clearance/single (B2B, before issuing)

    PRODUCTION:
        - Sign invoice_xml with ZATCA_PRIVATE_KEY (UBL 2.1 + XAdES)
        - Compute the SHA-256 invoice hash
        - POST to clearance/reporting endpoint with CSID basic auth
        - Parse response, persist clearance UUID + cleared XML
    """
    if not has_credentials():
        raise RuntimeError("ZATCA credentials missing (need ZATCA_CSID + ZATCA_PRIVATE_KEY).")
    if kind not in ("standard", "simplified"):
        raise ValueError("kind must be 'standard' or 'simplified'.")
    return {
        "stub": True,
        "kind": kind,
        "message": "Submit endpoint is a stub. Implement signing + clearance/reporting POST.",
    }


# ── Helpers used by the front-end / dashboard ─────────────────────

def sample_qr() -> str:
    """A self-contained example QR string for UI testing."""
    return build_qr(
        seller_name="Mumtaz Demo Co",
        vat_number=os.environ.get("ZATCA_VAT_NUMBER", "300000000000003"),
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        total_with_vat="1150.00",
        vat_amount="150.00",
    )
