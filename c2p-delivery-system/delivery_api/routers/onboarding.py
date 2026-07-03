"""Onboarding router — the consultant wizard API (Consulting OS slice 1).

Endpoints:
  GET  /consulting/catalog            roles / client types / service catalog
  GET  /consulting/profile            the tenant's consultant profile
  POST /consulting/profile            merge-save a partial profile (wizard steps)
  POST /consulting/suggest-services   auto-suggested services for roles×clients
  POST /consulting/wizard/complete    finalise → validated profile + summary

main.py wires dependencies via init(store, ks) to avoid circular imports; the
router never touches main.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from consulting import consultant_profile as cp
from consulting import intelligence_engine as ie
from consulting import service_catalog as cat

router = APIRouter(prefix="/consulting", tags=["consulting"])
_store = None
_ks = None


def init(store, ks=None) -> None:
    global _store, _ks
    _store, _ks = store, ks


@router.get("/catalog")
def get_catalog():
    return cat.catalog()


@router.get("/profile")
def get_profile():
    return cp.get_profile(_store)


@router.post("/profile")
def save_profile(body: dict):
    try:
        return cp.save_profile(_store, body or {})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/suggest-services")
def suggest(body: dict):
    body = body or {}
    return {"services": cat.suggest_services(body.get("roles") or [],
                                             body.get("client_types") or [])}


@router.post("/wizard/complete")
def complete_wizard(body: dict):
    """Final wizard step: validate + persist the full profile and return the
    activation summary (what the platform will generate for this consultant)."""
    body = dict(body or {})
    body["wizard_completed"] = True
    try:
        prof = cp.save_profile(_store, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    all_sv = {s: l for c in cat.SERVICE_CATALOG.values() for s, l in c.items()}
    summary = {
        "roles": [cat.ROLES[r] for r in prof["roles"]],
        "client_types": [cat.CLIENT_TYPES[c] for c in prof["client_types"]],
        "services": [all_sv.get(s, s) for s in prof["services"]],
    }
    # Compose the workflows/agents/documents this consultant will run.
    blueprint = ie.generate(_store)
    return {"profile": prof, "summary": summary, "blueprint": blueprint,
            "event": "wizard.completed"}
