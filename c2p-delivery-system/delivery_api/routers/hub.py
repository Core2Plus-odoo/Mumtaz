"""Knowledge Hub router — browse all built-in, no-API knowledge.

Surfaces `hub.py`: the sales playbook, pitch scripts, delivery workflows,
finance/PM/BA/consulting frameworks, Odoo standards and industry playbooks —
everything the system reasons from locally, made browsable for the console.

Endpoints:
  GET /hub                     section index
  GET /hub/export              the entire hub in one payload (offline cache)
  GET /hub/pitch/{industry}    ready pitch angle for an industry
  GET /hub/section/{key}       one section in full
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

import hub as _hub
import pitch_library as _pl

router = APIRouter(prefix="/hub", tags=["hub"])


@router.get("")
def index():
    return _hub.catalog()


@router.get("/export")
def export():
    return _hub.everything()


@router.get("/pitch/{industry}")
def pitch(industry: str):
    return {"industry": industry, "pitch": _pl.pitch_for(industry),
            "roi": _pl.roi_track(industry),
            "questions": _pl.questions_for("pain")}


@router.get("/section/{key}")
def section(key: str):
    data = _hub.section(key)
    if not data:
        raise HTTPException(status_code=404, detail=f"Unknown hub section: {key}")
    return data
