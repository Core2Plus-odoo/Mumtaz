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

import settings_store as store


# ── Configuration ──────────────────────────────────────────────────

def zatca_env() -> str:
    return (store.get("ZATCA_ENV") or "").strip().lower()


def is_configured() -> bool:
    """True if at minimum the VAT number + seller name are set.
    Cryptographic operations require ZATCA_CSID + ZATCA_PRIVATE_KEY too."""
    return bool(
        (store.get("ZATCA_VAT_NUMBER") or "").strip() and
        (store.get("ZATCA_SELLER_NAME") or "").strip()
    )


def has_credentials() -> bool:
    """True when CSID + private key are loaded — required for signing."""
    return bool(
        (store.get("ZATCA_CSID") or "").strip() and
        (store.get("ZATCA_PRIVATE_KEY") or "").strip()
    )


def status() -> dict:
    return {
        "configured":     is_configured(),
        "has_credentials": has_credentials(),
        "env":            zatca_env() or "not-set",
        "vat_number":     store.get("ZATCA_VAT_NUMBER", "") if is_configured() else None,
        "seller_name":    store.get("ZATCA_SELLER_NAME", "") if is_configured() else None,
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
        vat_number=store.get("ZATCA_VAT_NUMBER", "300000000000003"),
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        total_with_vat="1150.00",
        vat_amount="150.00",
    )


# ── Real CSR generation (production-ready) ─────────────────────────

def generate_keypair_and_csr(*, common_name: str, vat_number: str,
                             serial_number: str, organization: str,
                             organizational_unit: str = "ZATCA",
                             country: str = "SA",
                             email: str | None = None) -> dict:
    """Generate a fresh EC private key + CSR ready to submit to ZATCA's
    Compliance API. Returns base64-encoded PEM key + base64-encoded CSR.

    The caller is responsible for storing the private key securely
    (settings 'ZATCA_PRIVATE_KEY') — once submitted with an OTP, ZATCA
    returns a CSID that pairs with this exact key."""
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256K1())

    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME,             common_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME,       organization),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, organizational_unit),
        x509.NameAttribute(NameOID.COUNTRY_NAME,            country),
    ])

    # ZATCA-specific subject alternative names
    san_pairs = [
        ("SN",       serial_number),
        ("UID",      vat_number),
        ("title",    "1100"),  # invoice type: 1=standard, 1=simplified, 0=third-party, 0=nominal
        ("registeredAddress", "Saudi Arabia"),
        ("businessCategory",  organization),
    ]

    builder = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(subject)
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DirectoryName(x509.Name([
                    x509.NameAttribute(x509.ObjectIdentifier("2.5.4.4"),  san_pairs[0][1]),  # SN
                    x509.NameAttribute(x509.ObjectIdentifier("0.9.2342.19200300.100.1.1"), san_pairs[1][1]),  # UID
                    x509.NameAttribute(x509.ObjectIdentifier("2.5.4.12"), san_pairs[2][1]),  # title
                    x509.NameAttribute(x509.ObjectIdentifier("2.5.4.26"), san_pairs[3][1]),  # registered address
                    x509.NameAttribute(x509.ObjectIdentifier("2.5.4.15"), san_pairs[4][1]),  # business category
                ]))
            ]),
            critical=False,
        )
    )
    csr = builder.sign(key, hashes.SHA256())

    pem_key = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pem_csr = csr.public_bytes(serialization.Encoding.PEM)

    return {
        "private_key_pem": pem_key.decode("ascii"),
        "csr_pem":         pem_csr.decode("ascii"),
        # ZATCA wants the CSR base64'd (without PEM headers) for the API call
        "csr_base64":      base64.b64encode(pem_csr).decode("ascii"),
    }


def submit_csr_for_csid(*, csr_base64: str, otp: str, env: str | None = None) -> dict:
    """Exchange a CSR + OTP for a Compliance CSID via ZATCA's onboarding API.

    Endpoints:
      sandbox    https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal/compliance
      simulation https://gw-fatoora.zatca.gov.sa/e-invoicing/simulation/compliance
      production https://gw-fatoora.zatca.gov.sa/e-invoicing/core/compliance
    """
    import requests
    env = (env or zatca_env() or "sandbox").lower()
    base = {
        "sandbox":    "https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal",
        "simulation": "https://gw-fatoora.zatca.gov.sa/e-invoicing/simulation",
        "production": "https://gw-fatoora.zatca.gov.sa/e-invoicing/core",
    }.get(env, "https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal")

    r = requests.post(
        f"{base}/compliance",
        headers={
            "Accept":         "application/json",
            "Accept-Version": "V2",
            "OTP":            otp,
            "Content-Type":   "application/json",
        },
        json={"csr": csr_base64},
        timeout=30,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"ZATCA onboarding failed: HTTP {r.status_code} — {r.text[:300]}")
    data = r.json()
    # Returns: dispositionMessage, binarySecurityToken (CSID), secret, requestID
    return data


def hash_invoice_xml(xml_str: str) -> str:
    """Compute the canonical SHA-256 hash of an UBL invoice XML, base64'd —
    required for ZATCA invoice headers and previous-invoice chaining."""
    import hashlib
    return base64.b64encode(
        hashlib.sha256(xml_str.encode("utf-8")).digest()
    ).decode("ascii")
