"""C2P delivery-api — the backbone of the delivery system.

One FastAPI service that:
  - holds the engagement (the deal that threads all five stages),
  - serves the five stage agents (presales -> proposal -> project ->
    functional -> developer) via the Claude API, each consuming the prior
    stage's output,
  - bridges to Odoo over XML-RPC so the pipeline is grounded in, and writes
    back to, the tenant's real CRM / Sales / Project records.

Run:
    export ANTHROPIC_API_KEY=sk-...
    export ODOO_URL=... ODOO_USER=... ODOO_PASSWORD=...
    uvicorn main:app --reload --port 8800
"""

from __future__ import annotations

import json
import os
from typing import Any

from anthropic import Anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import models as m
from models import Engagement
from prompts import PROMPTS, MAX_TOKENS
from store import EngagementStore
from sync import writeback
from odoo import get_client

MODEL = os.getenv("C2P_MODEL", "claude-sonnet-4-6")  # set to your current model id

client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
store = EngagementStore()
app = FastAPI(title="C2P delivery-api", version="1.0.0")

# The frontends are static HTML served by Nginx; allow them to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("C2P_CORS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Agent runner
# --------------------------------------------------------------------------- #
def _extract_json(text: str) -> dict:
    """Pull the JSON object out of the model's reply, tolerating code fences or
    stray prose by slicing between the first '{' and the last '}'."""
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("no JSON object in response")
    return json.loads(text[a:b + 1])


def run_agent(stage: str, user_content: str) -> dict:
    """Call the Claude API with the stage's system prompt and return parsed JSON."""
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS.get(stage, 2048),
            system=PROMPTS[stage],
            messages=[{"role": "user", "content": user_content}],
        )
    except Exception as exc:  # network / API errors
        raise HTTPException(status_code=502, detail=f"Model call failed: {exc}")

    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    try:
        return _extract_json(raw)
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=502,
            detail="Agent returned non-JSON output. Narrow the scope and retry.",
        )


def _engagement(eng_id: str) -> Engagement:
    eng = store.get(eng_id)
    if not eng:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return eng


def _commit(eng: Engagement, stage: str, out: dict) -> dict:
    """Persist the engagement, push the stage to Odoo (best-effort), and persist
    again so any record ids created during write-back are saved."""
    store.save(eng)
    writeback(eng, stage, out)
    store.save(eng)
    return out


def _prior(eng: Engagement, stage: str) -> str:
    """Serialise an earlier stage's output to feed into the next stage."""
    data = eng.stages.get(stage)
    return json.dumps(data, indent=2) if data else "(not yet completed)"


def _maybe_modules(eng: Engagement, override: str | None) -> str:
    if override:
        return override
    if eng.odoo_db:
        try:
            return ", ".join(get_client(eng.odoo_db).installed_modules())
        except Exception:
            return "Not specified"
    return "Not specified"


# --------------------------------------------------------------------------- #
# Engagement lifecycle
# --------------------------------------------------------------------------- #
@app.post("/engagements", response_model=Engagement)
def create_engagement(body: m.CreateEngagement):
    return store.create(body.company, body.odoo_db)


@app.get("/engagements/{eng_id}", response_model=Engagement)
def get_engagement(eng_id: str):
    return _engagement(eng_id)


@app.get("/engagements")
def list_engagements():
    return store.list()


# --------------------------------------------------------------------------- #
# Stage 1 — Presales
# --------------------------------------------------------------------------- #
@app.post("/engagements/{eng_id}/presales")
def presales(eng_id: str, body: m.PresalesIn):
    eng = _engagement(eng_id)
    content = (
        f"Company: {eng.company}\nCountry: {body.country}\n"
        f"Industry: {body.industry or 'Unknown'}\n\n"
        f"Discovery notes:\n{body.notes}\n\nQualify and return the JSON."
    )
    out = run_agent("presales", content)
    eng.stages["presales"] = out
    return _commit(eng, "presales", out)


# --------------------------------------------------------------------------- #
# Stage 2 — Proposal (consumes presales)
# --------------------------------------------------------------------------- #
@app.post("/engagements/{eng_id}/proposal")
def proposal(eng_id: str, body: m.ProposalIn):
    eng = _engagement(eng_id)
    content = (
        f"Company: {eng.company}\n\n"
        f"Presales / discovery output:\n{_prior(eng, 'presales')}\n\n"
        f"Extra direction: {body.instructions or 'none'}\n\n"
        "Produce the scoped proposal JSON."
    )
    out = run_agent("proposal", content)
    eng.stages["proposal"] = out
    return _commit(eng, "proposal", out)


# --------------------------------------------------------------------------- #
# Stage 3 — Project (consumes proposal)
# --------------------------------------------------------------------------- #
@app.post("/engagements/{eng_id}/project")
def project(eng_id: str, body: m.ProjectIn):
    eng = _engagement(eng_id)
    content = (
        f"Company: {eng.company}\n\n"
        f"Approved proposal output:\n{_prior(eng, 'proposal')}\n\n"
        f"Extra direction: {body.instructions or 'none'}\n\n"
        "Produce the implementation plan JSON."
    )
    out = run_agent("project", content)
    eng.stages["project"] = out
    return _commit(eng, "project", out)


# --------------------------------------------------------------------------- #
# Stage 4 — Functional (per requirement; grounded by Odoo if a db is set)
# --------------------------------------------------------------------------- #
@app.post("/engagements/{eng_id}/functional")
def functional(eng_id: str, body: m.FunctionalIn):
    eng = _engagement(eng_id)
    modules = _maybe_modules(eng, body.installed_modules)
    content = (
        f"Requirement:\n{body.requirement}\n\nContext:\n"
        f"- Odoo version: {body.odoo_version}\n- Country/region: {body.country}\n"
        f"- Industry: {body.industry or 'Not specified'}\n"
        f"- Installed modules: {modules}\n\nAnalyse and return the JSON."
    )
    out = run_agent("functional", content)
    # Keep a list of analysed requirements rather than overwriting.
    eng.stages.setdefault("functional", []).append(out)
    return _commit(eng, "functional", out)


# --------------------------------------------------------------------------- #
# Stage 5 — Developer (consumes a functional spec)
# --------------------------------------------------------------------------- #
@app.post("/engagements/{eng_id}/developer")
def developer(eng_id: str, body: m.DeveloperIn):
    eng = _engagement(eng_id)
    spec = body.spec
    if not spec:
        fns = eng.stages.get("functional") or []
        custom = [f for f in fns if f.get("verdict") == "custom"]
        if not custom:
            raise HTTPException(
                status_code=400,
                detail="No spec provided and no Custom-verdict functional analysis to build from.",
            )
        spec = json.dumps(custom[-1], indent=2)

    content = (
        f"Build an Odoo v{body.target_version} module from this spec.\n\n"
        f"Target version: v{body.target_version}\n"
        f"Preferred technical name: {body.module_name or '(you choose)'}\n"
        f"Category: {body.category or '(infer)'}\n"
        f"Include unit tests: {'yes' if body.include_tests else 'no'}\n\n"
        f"Spec:\n{spec}\n\nReturn the module JSON."
    )
    out = run_agent("developer", content)
    eng.stages["developer"] = out
    return _commit(eng, "developer", out)


# --------------------------------------------------------------------------- #
# Odoo bridge (introspection + sync to system of record)
# --------------------------------------------------------------------------- #
@app.get("/odoo/{db}/modules")
def odoo_modules(db: str):
    try:
        return {"db": db, "installed": get_client(db).installed_modules()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Odoo error: {exc}")


@app.get("/odoo/{db}/fields/{model}")
def odoo_fields(db: str, model: str):
    try:
        return {"db": db, "model": model, "fields": get_client(db).fields_of(model)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Odoo error: {exc}")


@app.post("/engagements/{eng_id}/sync/lead")
def sync_lead(eng_id: str):
    """Create the CRM lead from the presales output, making Odoo the record."""
    eng = _engagement(eng_id)
    if not eng.odoo_db:
        raise HTTPException(status_code=400, detail="Engagement has no odoo_db set")
    pre = eng.stages.get("presales")
    if not pre:
        raise HTTPException(status_code=400, detail="Run presales first")
    try:
        lead_id = get_client(eng.odoo_db).create_lead(
            name=f"{eng.company} — {pre.get('recommendation', 'opportunity')}",
            partner_name=eng.company,
            description=json.dumps(pre.get("discovery", {}), indent=2),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Odoo error: {exc}")
    eng.crm_lead_id = lead_id
    store.save(eng)
    return {"crm_lead_id": lead_id}


@app.get("/health")
def health():
    return {"ok": True, "model": MODEL, "stages": m.STAGES}
