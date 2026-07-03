"""Consultant profile — the tenant's identity that drives the whole platform.

Stored per tenant in app_settings (the StoreProxy routes settings to the
tenant's own DB under MULTITENANT, so isolation is inherited). The profile is
what the intelligence engine reads to generate workflows, activate agents and
pick templates. `profile_block()` injects it into agent calls so every agent
knows WHO the consultant is and what they sell.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import service_catalog as cat

_KEY = "consultant_profile"


def default_profile() -> dict:
    return {"identity": {"name": "", "email": "", "company": "", "country": "UAE"},
            "roles": [], "client_types": [], "services": [],
            "output": {"proposal_template": "default", "brd_template": "default",
                        "sop_template": "default", "branding": "inherit"},
            "wizard_completed": False, "updated_at": None}


def get_profile(store) -> dict:
    try:
        p = store.get_setting(_KEY) or {}
    except Exception:
        p = {}
    base = default_profile()
    base.update({k: v for k, v in p.items() if v is not None})
    return base


def save_profile(store, patch: dict) -> dict:
    """Merge-and-save; validates role/client/service keys. Returns the profile
    or raises ValueError with the problems."""
    prof = get_profile(store)
    for k in ("identity", "output"):
        if isinstance(patch.get(k), dict):
            prof[k] = {**prof.get(k, {}), **patch[k]}
    for k in ("roles", "client_types", "services"):
        if isinstance(patch.get(k), list):
            prof[k] = list(dict.fromkeys(patch[k]))
    if "wizard_completed" in patch:
        prof["wizard_completed"] = bool(patch["wizard_completed"])
    errs = cat.validate(prof["roles"], prof["client_types"], prof["services"]) \
        if prof["wizard_completed"] else []
    if errs:
        raise ValueError("; ".join(errs))
    prof["updated_at"] = datetime.now(timezone.utc).isoformat()
    store.save_setting(_KEY, prof)
    return prof


def profile_block(store) -> str:
    """Prompt-ready block describing the consultant — injected into agent calls
    so outputs speak as THIS consultancy, scoped to THEIR services."""
    p = get_profile(store)
    if not p.get("roles"):
        return ""
    roles = ", ".join(cat.ROLES.get(r, r) for r in p["roles"])
    clients = ", ".join(cat.CLIENT_TYPES.get(c, c) for c in p["client_types"]) or "—"
    all_sv = {s: l for c in cat.SERVICE_CATALOG.values() for s, l in c.items()}
    services = ", ".join(all_sv.get(s, s) for s in p["services"]) or "—"
    ident = p.get("identity", {})
    return (f"\n\nCONSULTANT PROFILE (you work FOR this firm; scope everything to "
            f"their practice):\n- Firm: {ident.get('company') or 'the consultancy'} "
            f"({ident.get('country', 'UAE')})\n- Roles: {roles}\n"
            f"- Client segments: {clients}\n- Services sold: {services}")
