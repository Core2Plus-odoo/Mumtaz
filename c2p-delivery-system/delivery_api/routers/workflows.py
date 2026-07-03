"""Workflows router — Consulting OS slice 2 (intelligence + workflow engine).

Exposes the blueprint the intelligence engine composes from the tenant's
consultant profile: the workflows they run, the agents those activate and the
documents produced. Read endpoints serve the persisted blueprint (generated
once on demand); POST /generate recomputes it after a profile change.

Endpoints:
  GET  /consulting/blueprint            full blueprint (workflows+agents+docs)
  GET  /consulting/blueprint/summary    compact activation summary
  POST /consulting/workflows/generate   recompute blueprint from the profile
  GET  /consulting/workflows            list composed workflows
  GET  /consulting/workflows/{key}      one composed workflow (any catalog svc)
  GET  /consulting/steps                the step library (reference)

main.py wires dependencies via init(store); the router never touches main.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from consulting import intelligence_engine as ie
from consulting import service_catalog as cat
from consulting import step_library as lib
from consulting import workflow_engine as wf

_ALL_SERVICES = {s for c in cat.SERVICE_CATALOG.values() for s in c}

router = APIRouter(prefix="/consulting", tags=["consulting"])
_store = None


def init(store) -> None:
    global _store
    _store = store


@router.get("/blueprint")
def get_blueprint():
    return ie.get_blueprint(_store)


@router.get("/blueprint/summary")
def get_summary():
    return ie.summary(_store)


@router.post("/workflows/generate")
def generate():
    bp = ie.generate(_store)
    return {"blueprint": bp, "event": "workflow.generated",
            "counts": bp["counts"]}


@router.get("/workflows")
def list_workflows():
    return {"workflows": ie.get_blueprint(_store)["workflows"]}


@router.get("/workflows/{key}")
def get_workflow(key: str):
    if key not in wf.SERVICE_WORKFLOW and key not in _ALL_SERVICES:
        raise HTTPException(status_code=404, detail=f"Unknown service: {key}")
    return wf.compose(key)


@router.get("/steps")
def steps():
    return {"steps": lib.STEP_LIBRARY, "gates": sorted(lib.all_gates())}
