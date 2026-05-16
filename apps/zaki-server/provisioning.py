"""
Tenant provisioning — creates an isolated Odoo database for each new customer.

Flow per signup:
  1. generate_db_name(company)    → "mt_acme_3a7f2b"
  2. create_odoo_db(db_name, ...) → POST /web/database/create  (~30-60 s)
  3. install_addons(db_name, ...) → XML-RPC to new DB (non-fatal)
  4. provision_tenant(...)        → orchestrates 1-3, returns {ok, db_name, error}

The caller stores db_name in SQLite and updates tenant status to
'active' or 'error'.
"""

import json
import os
import re
import secrets
import urllib.error
import urllib.request
import xmlrpc.client
from typing import Optional

ODOO_URL         = os.environ.get("ODOO_URL",         "http://localhost:8069")
ODOO_MASTER_PASS = os.environ.get("ODOO_MASTER_PASS", "admin")
ODOO_ADMIN_USER  = os.environ.get("ODOO_ADMIN",       "admin@mumtaz.digital")
ODOO_ADMIN_PASS  = os.environ.get("ODOO_PASS",        "admin")
ODOO_TIMEOUT     = int(os.environ.get("ODOO_PROVISION_TIMEOUT", "120"))

# Addons installed in every new tenant DB (order matters — dependencies first).
DEFAULT_ADDONS: list[str] = [
    "mumtaz_theme",
    "mumtaz_base",
    "mumtaz_branding",
    "mumtaz_einvoicing",
    "mumtaz_lead_scraper",
    "mumtaz_lead_nurture",
    "mumtaz_proposal",
    "mumtaz_tenant_profile",   # hides Apps menu, wires CRM→Lead Scraper groups
]


# ── Helpers ───────────────────────────────────────────────────────────

def generate_db_name(company: str) -> str:
    """Return a unique Odoo DB name, e.g. 'mt_acme_3a7f2b'."""
    slug = re.sub(r"[^a-z0-9]", "", company.lower())[:10] or "co"
    rand = secrets.token_hex(3)   # 6 hex chars → 16M combinations
    return f"mt_{slug}_{rand}"


def _http_post(path: str, payload: dict, timeout: int = ODOO_TIMEOUT) -> dict:
    raw = json.dumps(payload).encode()
    req = urllib.request.Request(
        ODOO_URL.rstrip("/") + path,
        data=raw,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from Odoo: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach Odoo at {ODOO_URL}: {exc.reason}") from exc


# ── Step 1: Create the database ───────────────────────────────────────

def create_odoo_db(db_name: str, admin_email: str) -> None:
    """
    Create a new Odoo database via the built-in database manager API.
    Blocks until Odoo confirms (typically 30-60 s).
    Raises RuntimeError on failure.
    """
    body = _http_post("/web/database/create", {
        "jsonrpc": "2.0",
        "method":  "call",
        "id":      1,
        "params": {
            "master_pwd":   ODOO_MASTER_PASS,
            "name":         db_name,
            "lang":         "en_US",
            "password":     ODOO_ADMIN_PASS,
            "email":        admin_email,
            "phone":        "",
            "demo":         False,
            "country_code": "AE",
        },
    })
    if "error" in body:
        err = body["error"]
        msg = (err.get("data", {}) or {}).get("message") or err.get("message") or "Unknown error"
        raise RuntimeError(f"Odoo DB creation failed: {msg}")


# ── Step 2: Install Mumtaz addons ──────────────────────────────────────

def _admin_uid(db_name: str) -> Optional[int]:
    common = xmlrpc.client.ServerProxy(
        f"{ODOO_URL}/xmlrpc/2/common", allow_none=True
    )
    try:
        uid = common.authenticate(db_name, ODOO_ADMIN_USER, ODOO_ADMIN_PASS, {})
        return uid if uid else None
    except Exception:
        return None


def install_addons(db_name: str, addons: list[str]) -> bool:
    """
    Install Mumtaz addons in a freshly-created tenant DB.
    Non-fatal — returns False on failure instead of raising.
    """
    uid = _admin_uid(db_name)
    if not uid:
        print(f"[provision] install_addons: auth failed for {db_name}")
        return False
    obj = xmlrpc.client.ServerProxy(
        f"{ODOO_URL}/xmlrpc/2/object", allow_none=True
    )
    try:
        module_ids = obj.execute_kw(
            db_name, uid, ODOO_ADMIN_PASS,
            "ir.module.module", "search",
            [[["name", "in", addons], ["state", "=", "uninstalled"]]],
        )
        if module_ids:
            obj.execute_kw(
                db_name, uid, ODOO_ADMIN_PASS,
                "ir.module.module", "button_immediate_install",
                [module_ids],
            )
        print(f"[provision] installed {len(module_ids or [])} addons in {db_name}")
        return True
    except Exception as exc:
        print(f"[provision] install_addons error for {db_name}: {exc}")
        return False


# ── Orchestrator ──────────────────────────────────────────────────────

def provision_tenant(company: str, admin_email: str) -> dict:
    """
    Full tenant provisioning.

    Returns:
        {"ok": True,  "db_name": "mt_acme_3a7f2b", "error": None}
        {"ok": False, "db_name": "mt_acme_3a7f2b", "error": "reason"}
    """
    db_name = generate_db_name(company)
    print(f"[provision] starting: company={company!r} db={db_name}")

    try:
        create_odoo_db(db_name, admin_email)
        print(f"[provision] db created: {db_name}")
    except RuntimeError as exc:
        return {"ok": False, "db_name": db_name, "error": str(exc)}

    # Non-fatal — skip if addons aren't on the Odoo server yet
    try:
        install_addons(db_name, DEFAULT_ADDONS)
    except Exception as exc:
        print(f"[provision] addon install skipped for {db_name}: {exc}")

    return {"ok": True, "db_name": db_name, "error": None}
