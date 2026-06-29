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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import models as m
from models import Account, Engagement
from prompts import PROMPTS, MAX_TOKENS
from store import EngagementStore
from knowledge import KnowledgeService
from sync import writeback
from odoo import get_client
import llm

MODEL = llm.DEFAULT_MODEL  # the model is config, owned by llm.py

store = EngagementStore()
ks = KnowledgeService(store)
app = FastAPI(title="C2P Agency OS API", version="1.1.0")

# The frontends are static HTML served by Nginx; allow them to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("C2P_CORS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Agent runner — every agent call routes through the llm abstraction, which
# logs the run as owned data (see llm.run_json + store.log_run).
# --------------------------------------------------------------------------- #
def run_agent(stage: str, user_content: str, web_search: bool = False,
              account_id: str | None = None, engagement_id: str | None = None) -> dict:
    try:
        return llm.run_json(
            stage, PROMPTS[stage], user_content,
            max_tokens=MAX_TOKENS.get(stage, 2048), web_search=web_search,
            store=store, account_id=account_id, engagement_id=engagement_id,
        )
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=502,
            detail="Agent returned non-JSON output. Narrow the scope and retry.",
        )
    except Exception as exc:  # network / provider errors
        raise HTTPException(status_code=502, detail=f"Model call failed: {exc}")


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
    return store.create(body.company, body.odoo_db, account_id=body.account_id)


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
        + ks.context_block(eng.account_id, body.industry or eng.company)
    )
    out = run_agent("presales", content, account_id=eng.account_id, engagement_id=eng.id)
    eng.stages["presales"] = out
    result = _commit(eng, "presales", out)
    # Compound the account's knowledge with what qualification learned.
    if eng.account_id:
        ks.write_entry(
            eng.account_id, "qualification",
            {"recommendation": out.get("recommendation"),
             "icp_fit": out.get("icp_fit"),
             "candidate_requirements": out.get("candidate_requirements"),
             "modules_in_scope": out.get("modules_in_scope")},
            title=f"Presales qualification — {eng.company}", learned_by="presales",
        )
    return result


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
        + ks.context_block(eng.account_id, body.requirement)
    )
    out = run_agent("functional", content, account_id=eng.account_id, engagement_id=eng.id)
    # Keep a list of analysed requirements rather than overwriting.
    eng.stages.setdefault("functional", []).append(out)
    result = _commit(eng, "functional", out)
    if eng.account_id:
        ks.write_entry(
            eng.account_id, "requirement",
            {"requirement": out.get("requirement_summary"),
             "verdict": out.get("verdict"),
             "recommended_path": out.get("recommended_path")},
            title=f"Requirement — {(out.get('requirement_summary') or '')[:60]}",
            learned_by="functional",
        )
    return result


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


# --------------------------------------------------------------------------- #
# Phase 1 — Accounts + client knowledge + top-of-funnel agents
# --------------------------------------------------------------------------- #
def _account(account_id: str) -> Account:
    acc = store.get_account(account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    return acc


@app.post("/accounts", response_model=Account)
def create_account(body: m.CreateAccount):
    if body.partner_id:
        existing = store.get_account_by_partner(body.partner_id)
        if existing:
            return existing
    acc = Account(name=body.name, odoo_db=body.odoo_db, partner_id=body.partner_id,
                  industry=body.industry, country=body.country)
    return store.create_account(acc)


@app.get("/accounts")
def list_accounts():
    return store.list_accounts()


@app.get("/accounts/{account_id}", response_model=Account)
def get_account(account_id: str):
    return _account(account_id)


@app.get("/accounts/{account_id}/knowledge")
def get_knowledge(account_id: str, kind: str | None = None,
                  q: str | None = None, limit: int = 100):
    _account(account_id)
    entries = (store.search_knowledge(account_id, q, limit=limit)
               if q else store.list_knowledge(account_id, kind=kind, limit=limit))
    return [e.model_dump() for e in entries]


@app.post("/accounts/{account_id}/knowledge")
def add_knowledge(account_id: str, body: m.KnowledgeIn):
    _account(account_id)
    entry = ks.write_entry(account_id, body.kind, body.content, title=body.title,
                           learned_by=body.learned_by, tags=body.tags)
    return entry.model_dump()


@app.post("/prospect")
def prospect(body: m.ProspectIn):
    """ICP in → ranked prospect list out. Web-search grounded when available."""
    icp = body.icp or (
        f"Industry: {body.industry or 'manufacturing / distribution / retail'}; "
        f"Country: {body.country}; Size: {body.size_band or '20-500 employees'}; "
        f"Signals: {body.signals or 'ERP modernisation, growth, multi-entity, compliance'}"
    )
    content = (
        f"Ideal Customer Profile:\n{icp}\n\n"
        f"Exclude: {', '.join(body.exclude) or 'none'}\n"
        f"Return up to {body.max_results} ranked prospects as JSON."
    )
    return run_agent("prospect", content, web_search=True)


@app.post("/accounts/{account_id}/research")
def research(account_id: str, body: m.ResearchIn):
    """Deep-research a company and write the dossier into its knowledge base."""
    acc = _account(account_id)
    company = body.company or acc.name
    web = llm.WEB_SEARCH_ENABLED if body.web_search is None else body.web_search
    content = (
        f"Company to research: {company}\nCountry: {acc.country or 'UAE/GCC'}\n"
        f"Industry: {acc.industry or 'unknown'}\nFocus: {body.focus or 'full dossier'}\n\n"
        "Build the dossier JSON."
    )
    out = run_agent("research", content, web_search=web, account_id=account_id)
    ks.write_entry(account_id, "research_dossier", out,
                   title=f"Research dossier — {company}", learned_by="research",
                   tags=["research"])
    profile = out.get("company_profile") or {}
    if profile:
        store.update_account_profile(account_id, {**acc.profile, **profile})
    return out


@app.get("/runs")
def list_runs(limit: int = 50):
    """Owned dataset: recent agent runs (labels, models, tokens, latency)."""
    return store.list_runs(limit=limit)


@app.get("/branding")
def get_branding():
    """Return the operator's saved branding (logo, colours, contact). Empty
    dict means the console falls back to its built-in C2P defaults."""
    return store.get_setting("branding")


@app.post("/branding")
def save_branding(body: dict):
    """Persist branding from the admin panel. Behind the console's login gate;
    stores logo data-URIs, colours and company details in SQLite."""
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object")
    store.save_setting("branding", body)
    return {"ok": True}


@app.get("/health")
def health():
    return {"ok": True, "model": MODEL, "stages": m.STAGES,
            "agents": list(PROMPTS.keys()), "web_search": llm.WEB_SEARCH_ENABLED}
