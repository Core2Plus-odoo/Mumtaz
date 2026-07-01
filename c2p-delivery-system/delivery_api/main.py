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
from contextvars import ContextVar

# When set (by the Delivery Director self-correct loop), run_agent appends this
# critique to the next specialist call so it produces a stronger revision.
_qa_feedback: ContextVar[str | None] = ContextVar("_qa_feedback", default=None)

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import models as m
from models import Account, Communication, Engagement, Lead, Tenant, User
from prompts import PROMPTS, MAX_TOKENS
from store import EngagementStore
from knowledge import KnowledgeService
from sync import writeback
from odoo import get_client
import odoo as odoo_mod
import industry
import odoo_knowledge
import odoo_standard
import odoo_automation
import pm_knowledge
import finance_knowledge
import ba_knowledge
import doc_templates
import config_knowledge
import config_ops
import local_agents
import llm
import policy
import channels
import proposal_render
import deploy as deployer
import github as github_mod
import tenancy
import stripe_billing

from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

MODEL = llm.DEFAULT_MODEL  # the model is config, owned by llm.py

# Store is a proxy: the single default store normally; the per-tenant store when
# MULTITENANT is on (set by the middleware below). Call sites are unchanged.
store = tenancy.StoreProxy(EngagementStore())
control = tenancy.ControlStore()
ks = KnowledgeService(store)


# ── Encrypted Odoo connection (used by every agent) ──────────────────────
def _odoo_settings() -> dict:
    try:
        return store.get_setting("odoo_connection") or {}
    except Exception:
        return {}


def _odoo_conn_for(db):
    """Resolver for odoo.OdooClient: encrypted store first, then env. The API
    key is decrypted only here, in memory, at call time."""
    s = _odoo_settings()
    url = s.get("url") or os.environ.get("ODOO_URL")
    user = s.get("user") or os.environ.get("ODOO_USER")
    pw = tenancy.dec_secret(s["key_enc"]) if s.get("key_enc") else os.environ.get("ODOO_PASSWORD")
    if url and user and pw:
        return (url, user, pw)
    return None


odoo_mod.CONN_PROVIDER = _odoo_conn_for


def _github_settings() -> dict:
    try:
        return store.get_setting("github_connection") or {}
    except Exception:
        return {}


def _github_conn():
    """Resolver for github.push_module: encrypted store first, then env. The
    token is decrypted only here, at call time."""
    s = _github_settings()
    repo = s.get("repo") or os.environ.get("C2P_GH_REPO")
    token = (tenancy.dec_secret(s["token_enc"]) if s.get("token_enc")
             else os.environ.get("C2P_GH_TOKEN"))
    return {"repo": repo, "branch": s.get("branch") or os.environ.get("C2P_GH_BRANCH") or "main",
            "subdir": s.get("subdir") or os.environ.get("C2P_GH_SUBDIR") or "",
            "token": token}


github_mod.CONN_PROVIDER = _github_conn
app = FastAPI(title="C2P Agency OS API", version="1.2.0")

# The frontends are static HTML served by Nginx; allow them to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("C2P_CORS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _tenant_mw(request: Request, call_next):
    """MULTITENANT on → require a JWT on non-public routes and route the request
    to its tenant's store. Off → no-op (single-tenant, nginx basic-auth)."""
    path = request.url.path
    # Single-admin login mode (no multi-tenancy): require a valid admin JWT.
    if not tenancy.MULTITENANT and tenancy.ADMIN_AUTH:
        if path in tenancy.PUBLIC_PATHS:
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        claims = tenancy.read_jwt(auth[7:] if auth.startswith("Bearer ") else "")
        if not claims or claims.get("role") != "admin":
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)
    if not tenancy.MULTITENANT:
        return await call_next(request)
    if path in tenancy.PUBLIC_PATHS:
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    claims = tenancy.read_jwt(auth[7:] if auth.startswith("Bearer ") else "")
    if not claims:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    tenancy.set_current_store(tenancy.tenant_store(claims["tenant_id"]))
    try:
        tenancy.set_current_secrets(control.get_secrets(claims["tenant_id"]))
    except Exception:
        tenancy.set_current_secrets({})
    request.state.claims = claims
    try:
        return await call_next(request)
    finally:
        tenancy.reset_current_store()
        tenancy.reset_current_secrets()


# --------------------------------------------------------------------------- #
# Agent runner — every agent call routes through the llm abstraction, which
# logs the run as owned data (see llm.run_json + store.log_run).
# --------------------------------------------------------------------------- #
def run_agent(stage: str, user_content: str, web_search: bool = False,
              account_id: str | None = None, engagement_id: str | None = None) -> dict:
    fb = _qa_feedback.get()
    if fb:
        user_content = (
            user_content
            + "\n\n--- QUALITY REVISION (Delivery Director) ---\n"
            + "A prior attempt did not clear the house quality bar. Produce a "
            + "stronger version that fixes these gaps specifically:\n" + fb
        )
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


def _industry_for(eng: Engagement, override: str | None = None) -> str | None:
    """Resolve the engagement's industry from an override, the presales profile,
    or the linked account — so later stages still get the playbook."""
    if override:
        return override
    pre = eng.stages.get("presales") or {}
    ind = (pre.get("company_profile") or {}).get("industry")
    if ind:
        return ind
    if eng.account_id:
        acc = store.get_account(eng.account_id)
        if acc and acc.industry:
            return acc.industry
    return None


# --------------------------------------------------------------------------- #
# Engagement lifecycle
# --------------------------------------------------------------------------- #
@app.post("/engagements", response_model=Engagement)
def create_engagement(body: m.CreateEngagement):
    return store.create(body.company, body.odoo_db, account_id=body.account_id)


@app.get("/engagements/{eng_id}", response_model=Engagement)
def get_engagement(eng_id: str):
    return _engagement(eng_id)


@app.post("/engagements/{eng_id}/odoo-db", response_model=Engagement)
def link_engagement_db(eng_id: str, body: dict | None = None):
    """Link the engagement to an Odoo database so the agents act on that tenant.
    Defaults to the database from the saved Odoo Connection (one-click link)."""
    eng = _engagement(eng_id)
    db = (body or {}).get("db") or _odoo_settings().get("db") or os.environ.get("C2P_CRM_DB")
    if not db:
        raise HTTPException(status_code=400,
                            detail="No database to link — set the Odoo Connection first.")
    eng.odoo_db = db
    store.save(eng)
    return eng


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
        + industry.playbook_block(body.industry)
        + ks.context_block(eng.account_id, body.industry or eng.company)
    )
    try:
        out = run_agent("presales", content, account_id=eng.account_id, engagement_id=eng.id)
    except HTTPException:
        if LOCAL_INTELLIGENCE:
            out = local_agents.build_presales(eng.company, body.industry, body.country, body.notes)
            llm.log_local(store, "presales", out, eng.account_id, eng.id)
        else:
            raise
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
# Business Analyst — deep requirements gathering. Plans discovery (what to ask /
# collect) and compiles the structured requirements catalog the delivery teams
# build from. The PM stays the client-facing owner; the BA does the elicitation.
# --------------------------------------------------------------------------- #
def _ba_requirements_block(eng: Engagement) -> str:
    """The BA's requirements catalog, rendered for injection into a later stage."""
    ba = eng.stages.get("ba_requirements")
    if not ba:
        return ""
    return ("\n\nBUSINESS ANALYST REQUIREMENTS CATALOG (authoritative requirements "
            "baseline):\n" + json.dumps(ba, indent=2)[:6000])


@app.post("/engagements/{eng_id}/ba/discovery")
def ba_discovery(eng_id: str, body: dict | None = None):
    """The BA produces a structured discovery / elicitation plan and (optionally)
    pushes its client-facing questions into the Q&A RFI for the PM to ask."""
    eng = _engagement(eng_id)
    body = body or {}
    content = (
        f"Client: {eng.company}\nIndustry: {_industry_for(eng) or 'unknown'}\n\n"
        f"What is known so far:\n{_doc_source(eng)}\n\n"
        f"Extra direction: {body.get('instructions') or 'none'}\n\n"
        "Produce the discovery plan JSON."
        + industry.playbook_block(_industry_for(eng))
    )
    try:
        out = run_agent("ba_discovery", content, account_id=eng.account_id, engagement_id=eng.id)
    except HTTPException:
        # API down: the BA runs the discovery itself from the built-in framework.
        if LOCAL_INTELLIGENCE:
            out = ba_knowledge.build_discovery(eng.company, _industry_for(eng))
            llm.log_local(store, "ba_discovery", out, eng.account_id, eng.id)
        else:
            raise
    eng.stages["ba_discovery"] = out
    store.save(eng)
    pushed = 0
    if body.get("push_to_qa", True):
        items = []
        for pa in (out.get("process_areas") or []):
            for q in (pa.get("questions") or [])[:6]:
                items.append({"question": q, "theme": pa.get("area"),
                              "why_it_matters": pa.get("why"), "waiting_agent": "functional",
                              "blocks": "medium"})
        for q in (out.get("key_decisions_for_client") or []):
            items.append({"question": q, "theme": "Key decision",
                          "waiting_agent": "project", "blocks": "high"})
        pushed = _merge_questions_into_rfi(eng, items)
    return {"discovery": out, "questions_pushed": pushed}


@app.post("/engagements/{eng_id}/ba/requirements")
def ba_requirements(eng_id: str, body: dict | None = None):
    """The BA compiles the structured requirements catalog from everything known
    — discovery, client answers, documents, prior stages and the playbook."""
    eng = _engagement(eng_id)
    body = body or {}
    content = (
        f"Client: {eng.company}\nIndustry: {_industry_for(eng) or 'unknown'}\n\n"
        f"All gathered information:\n{_doc_source(eng)}\n\n"
        f"Discovery plan:\n{json.dumps(eng.stages.get('ba_discovery') or {}, indent=2)[:4000]}\n\n"
        f"Extra direction: {body.get('instructions') or 'none'}\n\n"
        "Compile the requirements catalog JSON."
        + industry.playbook_block(_industry_for(eng))
        + ks.context_block(eng.account_id, "requirements scope modules")
        + _client_answers_block(eng)
    )
    try:
        out = run_agent("ba", content, account_id=eng.account_id, engagement_id=eng.id)
    except HTTPException:
        if LOCAL_INTELLIGENCE:
            out = local_agents.build_catalog(eng)
            llm.log_local(store, "ba", out, eng.account_id, eng.id)
        else:
            raise
    eng.stages["ba_requirements"] = out
    store.save(eng)
    if eng.account_id:
        ks.write_entry(
            eng.account_id, "requirements_catalog",
            {"scope_areas": out.get("scope_areas"),
             "functional_requirements": out.get("functional_requirements")},
            title=f"Requirements catalog — {eng.company}", learned_by="ba")
    return out


# --------------------------------------------------------------------------- #
# Stage 2 — Proposal (consumes presales)
# --------------------------------------------------------------------------- #
@app.post("/engagements/{eng_id}/proposal")
def proposal(eng_id: str, body: m.ProposalIn):
    eng = _engagement(eng_id)
    # Ground pricing in the local PM estimate (compute it if we have requirements).
    if not eng.stages.get("estimate"):
        reqs = _estimate_requirements(eng)
        if reqs:
            eng.stages["estimate"] = pm_knowledge.estimate(reqs)
            store.save(eng)
    content = (
        f"Company: {eng.company}\n\n"
        f"Presales / discovery output:\n{_prior(eng, 'presales')}\n\n"
        f"Extra direction: {body.instructions or 'none'}\n\n"
        "Produce the scoped proposal JSON."
        + industry.playbook_block(_industry_for(eng))
        + ks.context_block(eng.account_id, "proposal scope modules")
        + _ba_requirements_block(eng)
        + _estimate_block(eng)
        + _client_answers_block(eng)
    )
    try:
        out = run_agent("proposal", content, account_id=eng.account_id, engagement_id=eng.id)
    except HTTPException:
        if LOCAL_INTELLIGENCE:
            out = local_agents.build_proposal(eng)
            llm.log_local(store, "proposal", out, eng.account_id, eng.id)
        else:
            raise
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
        + industry.playbook_block(_industry_for(eng))
        + _ba_requirements_block(eng)
        + _client_answers_block(eng)
    )
    if not eng.stages.get("estimate"):                 # ground the plan in the estimate
        reqs = _estimate_requirements(eng)
        if reqs:
            eng.stages["estimate"] = pm_knowledge.estimate(reqs)
            store.save(eng)
    try:
        out = run_agent("project", content, account_id=eng.account_id, engagement_id=eng.id)
    except HTTPException:
        # API down: the PM builds the implementation plan from the methodology.
        if LOCAL_INTELLIGENCE:
            out = pm_knowledge.build_project_plan(eng)
            llm.log_local(store, "project", out, eng.account_id, eng.id)
        else:
            raise
    eng.stages["project"] = out
    return _commit(eng, "project", out)


# --------------------------------------------------------------------------- #
# Stage 4 — Functional (per requirement; grounded by Odoo if a db is set)
# --------------------------------------------------------------------------- #
def _deferred_functional(requirement: str, reason: str = "") -> dict:
    """A flagged placeholder used when a requirement can't be auto-classified and
    the model is unavailable — keeps the pipeline flowing instead of hard-failing."""
    return {
        "requirement_summary": (requirement or "")[:240],
        "verdict": "configurable",
        "verdict_rationale": "Deferred — not matched by built-in knowledge and the "
                             "model was unavailable. Provisional; needs a consultant "
                             "or an LLM pass to confirm.",
        "standard_capability": {"available": True, "modules": [],
                                "description": "To be confirmed."},
        "gap_analysis": "Pending analysis.",
        "solution_options": [],
        "technical_design": None,
        "risks": ["Provisional — confirm classification before committing scope."],
        "gcc_considerations": "",
        "recommended_path": "Re-run this requirement when the model is available, "
                            "or have a consultant classify it.",
        "handoff_to_dev": False,
        "source": "deferred", "deferred": True,
    }


@app.post("/engagements/{eng_id}/functional")
def functional(eng_id: str, body: m.FunctionalIn):
    eng = _engagement(eng_id)
    modules = _maybe_modules(eng, body.installed_modules)

    # Built-in Odoo intelligence first: clear-cut requirements are classified
    # from curated knowledge with NO API call. Only novel/ambiguous ones, or a
    # low-confidence match, fall through to the model.
    local = odoo_knowledge.classify(
        body.requirement, body.industry or _industry_for(eng), modules)
    out = None
    if LOCAL_INTELLIGENCE and local["result"] and local["confidence"] >= LOCAL_CONFIDENCE:
        out = local["result"]
        llm.log_local(store, "functional", out, eng.account_id, eng.id)
    else:
        content = (
            f"Requirement:\n{body.requirement}\n\nContext:\n"
            f"- Odoo version: {body.odoo_version}\n- Country/region: {body.country}\n"
            f"- Industry: {body.industry or 'Not specified'}\n"
            f"- Installed modules: {modules}\n\nAnalyse and return the JSON."
            + industry.playbook_block(body.industry or _industry_for(eng))
            + ks.context_block(eng.account_id, body.requirement)
            + _ba_requirements_block(eng)
            + _client_answers_block(eng)
        )
        try:
            out = run_agent("functional", content,
                            account_id=eng.account_id, engagement_id=eng.id)
        except HTTPException as exc:
            # API unavailable (no credits / rate limit): fall back to built-in
            # knowledge so the agency keeps working. Use the best local match if
            # there is one; otherwise defer the requirement (flagged) rather than
            # hard-failing — so Autopilot/PM-delivery never halt on one item.
            if not LOCAL_INTELLIGENCE:
                raise
            if local["result"]:
                out = {**local["result"], "source": "knowledge-base-fallback"}
            else:
                out = _deferred_functional(body.requirement, str(exc.detail))
    # Standard-first: attach the standard Odoo apps/features that plausibly cover
    # this requirement, so the record proves a standard path before any custom.
    try:
        cov = odoo_standard.covered_by(body.requirement)
        if cov:
            out["standard_first_apps"] = cov
        # Native no-code automation design + standard-flow connection map.
        auto = odoo_automation.suggest(body.requirement)
        if auto.get("automation_design") and not out.get("automation_design"):
            out["automation_design"] = auto["automation_design"]
        if auto.get("connection_map") and not out.get("connection_map"):
            out["connection_map"] = auto["connection_map"]
        # complete the architect structure for locally-classified results
        if not out.get("configuration") and out.get("recommended_path"):
            out["configuration"] = [out["recommended_path"]]
        if out.get("verdict") == "custom" and not out.get("custom"):
            mods = (out.get("standard_capability") or {}).get("modules") or []
            base = (mods[0].get("name") if mods else None) or "the closest standard model"
            out["custom"] = {"needed": True, "inherits": base,
                             "connection": "Extend via _inherit; reuse standard states, "
                                           "chatter, activities and sequences — connected to "
                                           "the standard flow."}
    except Exception:
        pass
    # Chartered-accountant enrichment: attach IFRS/tax/compliance treatment for
    # any finance requirement — built-in knowledge, no API call.
    try:
        fin = finance_knowledge.advise(body.requirement, _country_code(body.country))
        if fin:
            out["finance"] = fin
    except Exception:
        pass
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
        + _client_answers_block(eng)
    )
    out = run_agent("developer", content)
    eng.stages["developer"] = out
    return _commit(eng, "developer", out)


# --------------------------------------------------------------------------- #
# Odoo bridge (introspection + sync to system of record)
# --------------------------------------------------------------------------- #
@app.get("/odoo/connection")
def get_odoo_connection():
    """The Odoo connection the agents use. The API key is NEVER returned —
    only whether one is stored and whether encryption is active."""
    s = _odoo_settings()
    return {
        "url": s.get("url") or os.environ.get("ODOO_URL", ""),
        "user": s.get("user") or os.environ.get("ODOO_USER", ""),
        "db": s.get("db") or os.environ.get("C2P_CRM_DB", ""),
        "has_key": bool(s.get("key_enc")) or bool(os.environ.get("ODOO_PASSWORD")),
        "encrypted": tenancy.encryption_active(),
    }


@app.post("/odoo/connection")
def set_odoo_connection(body: dict):
    """Save the Odoo connection. The API key is encrypted at rest (Fernet when
    C2P_SECRET_KEY is set)."""
    s = _odoo_settings()
    for k in ("url", "user", "db"):
        if body.get(k) is not None:
            s[k] = body.get(k)
    if body.get("api_key"):
        s["key_enc"] = tenancy.enc_secret(body["api_key"])
    store.save_setting("odoo_connection", s)
    try:
        get_client.cache_clear()           # rebuild clients with the new creds
    except Exception:
        pass
    return {"ok": True, "has_key": bool(s.get("key_enc")), "encrypted": tenancy.encryption_active()}


def _friendly_odoo_error(exc: Exception, db: str | None = None) -> str:
    """Turn a raw XML-RPC fault / socket error into a short, actionable message."""
    msg = str(exc)
    low = msg.lower()
    if "does not exist" in low and "database" in low:
        return (f"Database “{db}” does not exist on this Odoo server. On Odoo.sh the "
                "database name matches your instance subdomain and changes on every "
                "rebuild — copy the current name from the Odoo.sh branch (or the host "
                "in your instance URL) and try again.")
    if "access denied" in low or "authenticate" in low or "invalid" in low and "login" in low:
        return ("The server and database were reached, but the bot user or API key was "
                "rejected. Check the Bot user email and the API key / password.")
    if any(k in low for k in ("name or service not known", "failed to resolve",
                              "connection refused", "timed out", "no route to host",
                              "ssl", "certificate")):
        return ("Could not reach the Odoo server at that URL. Check the Odoo URL "
                "(include https://) and that the instance is online.")
    if "list index out of range" in low or "missing" in low:
        return f"Odoo rejected the request: {msg[:200]}"
    return f"Odoo error: {msg[:300]}"


@app.post("/odoo/connection/test")
def test_odoo_connection(body: dict | None = None):
    s = _odoo_settings()
    db = (body or {}).get("db") or s.get("db") or os.environ.get("C2P_CRM_DB")
    if not db:
        raise HTTPException(status_code=400, detail="No database set")
    try:
        mods = get_client(db).installed_modules()
        return {"ok": True, "db": db, "modules": len(mods)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_friendly_odoo_error(exc, db))


@app.post("/odoo/connection/detect-db")
def detect_odoo_db(body: dict | None = None):
    """Work out the right database name for the configured/entered URL: ask the
    server's db list when allowed, derive it from the URL host (Odoo.sh: the DB
    equals the instance subdomain), and verify each candidate with the saved
    credentials so we can point the operator at the one that actually connects."""
    from urllib.parse import urlparse
    s = _odoo_settings()
    body = body or {}
    url = body.get("url") or s.get("url") or os.environ.get("ODOO_URL")
    if not url:
        raise HTTPException(status_code=400, detail="Set the Odoo URL first")
    user = body.get("user") or s.get("user") or os.environ.get("ODOO_USER")
    key = None
    if s.get("key_enc"):
        try:
            key = tenancy.dec_secret(s["key_enc"])
        except Exception:
            key = None
    key = key or os.environ.get("ODOO_PASSWORD")

    candidates: list[str] = []
    listed = False
    try:
        dbs = odoo_mod.list_databases(url)
        if dbs:
            listed = True
            candidates.extend(dbs)
    except Exception:
        pass
    host = urlparse(url if "://" in url else "https://" + url).hostname or ""
    label = host.split(".")[0] if host else ""
    if label and label not in candidates:
        candidates.append(label)
    seen: set[str] = set()
    candidates = [c for c in candidates if not (c in seen or seen.add(c))]

    results = []
    best = None
    for db in candidates[:10]:
        status = "unverified"
        if user and key:
            try:
                odoo_mod.OdooClient(db, url=url, user=user, password=key).uid
                status = "connected"
                best = best or db
            except PermissionError:
                status = "exists_bad_creds"   # right DB, wrong user/key
                best = best or db
            except Exception as exc:
                status = ("not_found" if "does not exist" in str(exc).lower() else "error")
        results.append({"db": db, "status": status})
    return {"listed": listed, "candidates": results,
            "best": best or (candidates[0] if candidates else None)}


# --------------------------------------------------------------------------- #
# GitHub addons repo — where the Developer agent pushes generated modules
# (Odoo.sh then builds them). Token encrypted at rest, never returned.
# --------------------------------------------------------------------------- #
@app.get("/github/connection")
def get_github_connection():
    s = _github_settings()
    return {"repo": s.get("repo") or "", "branch": s.get("branch") or "main",
            "subdir": s.get("subdir") or "",
            "has_token": bool(s.get("token_enc")),
            "encrypted": tenancy.encryption_active(),
            "configured": github_mod.configured()}


@app.post("/github/connection")
def set_github_connection(body: dict):
    s = _github_settings()
    for k in ("repo", "branch", "subdir"):
        if body.get(k) is not None:
            s[k] = body.get(k)
    if body.get("token"):
        s["token_enc"] = tenancy.enc_secret(body["token"])
    store.save_setting("github_connection", s)
    return {"ok": True, "has_token": bool(s.get("token_enc")),
            "encrypted": tenancy.encryption_active()}


@app.post("/github/connection/test")
def test_github_connection(body: dict | None = None):
    try:
        return github_mod.test_connection()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/odoo/{db}/modules")
def odoo_modules(db: str):
    try:
        return {"db": db, "installed": get_client(db).installed_modules()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_friendly_odoo_error(exc, db))


@app.get("/odoo/{db}/fields/{model}")
def odoo_fields(db: str, model: str):
    try:
        return {"db": db, "model": model, "fields": get_client(db).fields_of(model)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_friendly_odoo_error(exc, db))


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
        raise HTTPException(status_code=502, detail=_friendly_odoo_error(exc))
    eng.crm_lead_id = lead_id
    store.save(eng)
    return {"crm_lead_id": lead_id}


# --------------------------------------------------------------------------- #
# Leads CRM — top of funnel (prospector results / inbound / manual → convert)
# --------------------------------------------------------------------------- #
def _lead(lead_id: str) -> Lead:
    lead = store.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@app.post("/leads", response_model=Lead)
def create_lead(body: m.LeadIn):
    return store.add_lead(Lead(**body.model_dump()))


@app.get("/leads")
def list_leads(status: str | None = None, limit: int = 200):
    return [l.model_dump() for l in store.list_leads(status, limit=limit)]


@app.get("/leads/{lead_id}", response_model=Lead)
def get_lead(lead_id: str):
    return _lead(lead_id)


@app.post("/leads/{lead_id}/update", response_model=Lead)
def update_lead(lead_id: str, body: m.LeadUpdateIn):
    lead = _lead(lead_id)
    if body.status:
        lead.status = body.status
    if body.notes is not None:
        lead.notes = body.notes
    return store.update_lead(lead)


@app.post("/leads/bulk")
def bulk_leads(body: m.LeadsBulkIn):
    """Save a batch of Prospector results as leads."""
    created = 0
    for p in body.prospects:
        fit = p.get("fit_score")
        store.add_lead(Lead(
            name=p.get("name") or p.get("company") or "Unknown",
            industry=p.get("industry"), country=p.get("country"),
            source="prospector", fit_score=int(fit) if fit not in (None, "") else None,
            signals=p.get("signals") or [], email=p.get("contact_hint")))
        created += 1
    return {"created": created}


@app.post("/leads/{lead_id}/convert")
def convert_lead(lead_id: str, body: dict | None = None):
    """Convert a lead into an Account (the start of an engagement relationship)."""
    lead = _lead(lead_id)
    body = body or {}
    acc = Account(name=lead.name, industry=lead.industry, country=lead.country,
                  odoo_db=body.get("odoo_db"))
    store.create_account(acc)
    lead.account_id = acc.id
    lead.status = "converted"
    store.update_lead(lead)
    return {"account": acc.model_dump(), "lead_id": lead.id}


@app.post("/leads/{lead_id}/sync")
def sync_lead_to_odoo(lead_id: str, body: dict | None = None):
    """Push the lead into Odoo CRM (crm.lead). DB from body.odoo_db or C2P_CRM_DB."""
    lead = _lead(lead_id)
    db = (body or {}).get("odoo_db") or os.environ.get("C2P_CRM_DB")
    if not db:
        raise HTTPException(status_code=400,
                            detail="No Odoo DB (set body.odoo_db or C2P_CRM_DB)")
    try:
        vals = {}
        if lead.email:
            vals["email_from"] = lead.email
        if lead.contact_name:
            vals["contact_name"] = lead.contact_name
        lid = get_client(db).create_lead(name=lead.name, partner_name=lead.name,
                                         description=lead.notes or "", **vals)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_friendly_odoo_error(exc))
    lead.crm_lead_id = lid
    store.update_lead(lead)
    return {"crm_lead_id": lid}


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
def prospect(body: m.ProspectIn, request: Request):
    """ICP in → ranked prospect list out. Web-search grounded when available."""
    _require_edition(request, "prospect")
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


@app.post("/infra/recommend")
def infra_recommend(body: m.InfraIn):
    """System Administrator agent: choose the Odoo hosting/deployment topology
    (Odoo Online / Odoo.sh / self-hosted VPS / on-prem; Community vs Enterprise)."""
    acc = _account(body.account_id) if body.account_id else None
    content = (
        "Client infrastructure inputs:\n"
        f"- Company: {body.company or (acc.name if acc else 'Unknown')}\n"
        f"- Odoo users: {body.users if body.users is not None else 'unknown'}\n"
        f"- Budget band: {body.budget_band or 'unknown'}\n"
        f"- Data residency / compliance: {body.data_residency or body.compliance or 'not specified'}\n"
        f"- In-house IT capability: {body.in_house_it}\n"
        f"- Customisation depth: {body.customization or 'unknown'}\n"
        f"- Integrations: {body.integrations or 'none stated'}\n"
        f"- Uptime need: {body.uptime_need or 'standard'}\n"
        f"- Notes: {body.notes or '-'}\n\n"
        "Recommend the platform and edition. Return the JSON."
        + ks.context_block(body.account_id, "infrastructure hosting deployment platform")
    )
    out = run_agent("sysadmin", content, account_id=body.account_id)
    if body.account_id:
        ks.write_entry(
            body.account_id, "infra_recommendation", out,
            title=f"Infrastructure recommendation — {out.get('recommended_platform', 'n/a')}",
            learned_by="sysadmin",
        )
    return out


# --------------------------------------------------------------------------- #
# Phase 3 — Branded proposals
# --------------------------------------------------------------------------- #
@app.get("/engagements/{eng_id}/proposal/preview")
def proposal_preview(eng_id: str):
    """Render the proposal JSON into the branded proposal HTML (for in-browser
    preview / print-to-PDF). Behind the console login gate."""
    eng = _engagement(eng_id)
    prop = eng.stages.get("proposal")
    if not prop:
        raise HTTPException(status_code=400, detail="Run the proposal stage first")
    html = proposal_render.render_html(
        prop, eng.company, proposal_render.brand(store), date_str=_now_iso()[:10])
    return Response(content=html, media_type="text/html")


@app.get("/engagements/{eng_id}/proposal/pdf")
def proposal_pdf(eng_id: str):
    eng = _engagement(eng_id)
    prop = eng.stages.get("proposal")
    if not prop:
        raise HTTPException(status_code=400, detail="Run the proposal stage first")
    html = proposal_render.render_html(
        prop, eng.company, proposal_render.brand(store), date_str=_now_iso()[:10])
    return _pdf_response(html, f"proposal-{eng.company}.pdf".replace(" ", "_"))


@app.post("/engagements/{eng_id}/proposal/send")
def proposal_send(eng_id: str, body: dict | None = None):
    """Issue the branded proposal to the client — GATED. Creates an approval;
    on approve it attaches the PDF to the Odoo quotation and optionally emails."""
    eng = _engagement(eng_id)
    if not eng.stages.get("proposal"):
        raise HTTPException(status_code=400, detail="Run the proposal stage first")
    body = body or {}
    payload = {"engagement_id": eng.id, "company": eng.company,
               "email": bool(body.get("email")), "to": body.get("to")}
    appr = policy.gate(store, "proposal_send", payload, requester_agent="proposal",
                       account_id=eng.account_id, engagement_id=eng.id)
    if appr is None:                       # policy set to auto → run now
        return {"approval": None, "result": _execute_proposal_send(payload, eng.account_id)}
    return {"approval": appr.model_dump()}


# --------------------------------------------------------------------------- #
# Phase 4 — Gated deploy of a generated module
# --------------------------------------------------------------------------- #
@app.post("/engagements/{eng_id}/deploy")
def deploy_module(eng_id: str, body: dict | None = None):
    """Deploy the developer stage's module to the account's addons repo — GATED.
    On approve it writes the module (staged, or git-pushed when configured)."""
    eng = _engagement(eng_id)
    dev = eng.stages.get("developer")
    if not dev or not dev.get("files"):
        raise HTTPException(status_code=400,
                            detail="Run the developer stage first (Custom verdict).")
    payload = {"engagement_id": eng.id, "module": dev.get("module_technical_name"),
               "files_count": len(dev.get("files") or [])}
    appr = policy.gate(store, "code_deploy", payload, requester_agent="developer",
                       account_id=eng.account_id, engagement_id=eng.id)
    if appr is None:
        return {"approval": None, "result": _execute_deploy(payload, eng.account_id)}
    return {"approval": appr.model_dump()}


# --------------------------------------------------------------------------- #
# Implementation in Odoo — config-apply (gated) + PM dispatch
# --------------------------------------------------------------------------- #
@app.post("/engagements/{eng_id}/config")
def config_apply(eng_id: str, body: dict | None = None):
    """Generate an Odoo config recipe from the requirements and apply it — GATED.
    Configures the client's live Odoo (master data, tax, stages, …) via the API."""
    eng = _engagement(eng_id)
    if not eng.odoo_db:
        raise HTTPException(status_code=400, detail="Link an Odoo DB to this engagement first")
    body = body or {}
    modules = _maybe_modules(eng, None)
    fns = [f.get("requirement_summary") for f in (eng.stages.get("functional") or [])]
    cands = [c.get("requirement") for c in ((eng.stages.get("presales") or {}).get("candidate_requirements") or [])]
    reqs = body.get("requirement") or json.dumps(fns or cands or ["Baseline GCC setup"], indent=2)
    content = (
        f"Engagement: {eng.company}\nOdoo version: {body.get('odoo_version', 'v17')}\n"
        f"Installed modules: {modules}\nRequirements to configure:\n{reqs}\n\n"
        "Produce the Odoo configuration recipe JSON."
        + industry.playbook_block(_industry_for(eng))
        + ks.context_block(eng.account_id, "configuration")
    )
    try:
        out = run_agent("config", content, account_id=eng.account_id, engagement_id=eng.id)
    except HTTPException:
        if LOCAL_INTELLIGENCE:
            out = config_knowledge.build_plan(eng, modules)
            llm.log_local(store, "config", out, eng.account_id, eng.id)
        else:
            raise
    # The consultant actually DOES the work: generate real, safe, idempotent Odoo
    # operations deterministically from the requirements (CRM stages, sources,
    # teams, categories) and merge with any the config agent produced.
    local_ops = config_ops.build_operations(eng) if LOCAL_INTELLIGENCE else []
    ops = (out.get("operations") or []) + local_ops
    out["operations"] = ops
    eng.stages["config"] = out
    store.save(eng)
    if not ops:
        return {"recipe": out, "approval": None,
                "result": {"mode": "plan", "applied": 0,
                           "note": "Configuration plan generated (no executable operations found)."}}
    payload = {"engagement_id": eng.id, "operations": ops, "summary": out.get("summary")}
    # Execute immediately when asked (apply=true) — the consultant does the needful.
    if body.get("apply"):
        res = _execute_config_apply(payload, eng.account_id)
        out["last_apply"] = res
        eng.stages["config"] = out
        store.save(eng)
        return {"recipe": out, "approval": None, "result": res}
    # Otherwise route through the approval gate (auto-runs if policy allows).
    appr = policy.gate(store, "config_apply", payload, requester_agent="config",
                       account_id=eng.account_id, engagement_id=eng.id)
    if appr is None:
        return {"recipe": out, "approval": None,
                "result": _execute_config_apply(payload, eng.account_id)}
    return {"recipe": out, "approval": appr.model_dump(), "ops_count": len(ops)}


@app.post("/engagements/{eng_id}/dispatch")
def dispatch(eng_id: str):
    """The Delivery Lead/PM allocates each requirement to the right capability
    (config / functional / developer / manual) with autonomy + priority."""
    eng = _engagement(eng_id)
    state = {
        "company": eng.company,
        "odoo_db": eng.odoo_db,
        "candidate_requirements": (eng.stages.get("presales") or {}).get("candidate_requirements") or [],
        "functional": [{"requirement": f.get("requirement_summary"), "verdict": f.get("verdict")}
                       for f in (eng.stages.get("functional") or [])],
        "has_proposal": bool(eng.stages.get("proposal")),
        "has_project": bool(eng.stages.get("project")),
    }
    content = (f"Engagement state:\n{json.dumps(state, indent=2)}\n\n"
               "As the Delivery Lead, allocate the work and return the JSON.")
    return run_agent("dispatch", content, account_id=eng.account_id, engagement_id=eng.id)


@app.post("/engagements/{eng_id}/pm")
def project_manager(eng_id: str):
    """The Project Manager owns the whole project — assembles full scope (stages,
    requirements, plan, approvals, Odoo tasks) and reports status + next actions."""
    eng = _engagement(eng_id)
    pending = [a for a in store.list_approvals(None, limit=300)
               if a.engagement_id == eng.id and a.status == "pending"]
    open_tasks = None
    if eng.odoo_db and eng.project_id:
        try:
            open_tasks = get_client(eng.odoo_db).execute(
                "project.task", "search_count", [("project_id", "=", eng.project_id)])
        except Exception:
            open_tasks = None
    prop = eng.stages.get("proposal") or {}
    scope = {
        "company": eng.company, "odoo_db": eng.odoo_db,
        "stages_done": [s for s in m.STAGES
                        if (eng.stages.get(s) if not isinstance(eng.stages.get(s), list)
                            else eng.stages.get(s))],
        "candidate_requirements": (eng.stages.get("presales") or {}).get("candidate_requirements") or [],
        "functional": [{"req": f.get("requirement_summary"), "verdict": f.get("verdict")}
                       for f in (eng.stages.get("functional") or [])],
        "proposal": {"value_aed": (prop.get("commercial") or {}).get("estimate_aed"),
                     "phases": [p.get("name") for p in (prop.get("phases") or [])]},
        "project_plan": [{"phase": p.get("name"), "weeks": p.get("weeks")}
                         for p in ((eng.stages.get("project") or {}).get("phases") or [])],
        "developer_module": (eng.stages.get("developer") or {}).get("module_technical_name"),
        "pending_approvals": [{"action": a.action_type, "requester": a.requester_agent}
                              for a in pending],
        "odoo_open_tasks": open_tasks,
    }
    content = (f"Full project scope:\n{json.dumps(scope, indent=2)}\n\n"
               "As the Project Manager, assess status and produce the management report JSON."
               + ks.context_block(eng.account_id, "project status"))
    try:
        out = run_agent("pm", content, account_id=eng.account_id, engagement_id=eng.id)
    except HTTPException:
        # API down: the PM assesses status itself from the engagement state.
        if LOCAL_INTELLIGENCE:
            out = pm_knowledge.build_status(
                eng, m.STAGES,
                pending_labels=[f"{a.action_type} awaiting approval" for a in pending],
                approval_types={a.action_type for a in
                                store.list_approvals(None, limit=300)
                                if a.engagement_id == eng.id})
            llm.log_local(store, "pm", out, eng.account_id, eng.id)
        else:
            raise
    return {"report": out, "scope": scope}


# --------------------------------------------------------------------------- #
# PM delivery orchestrator — the Project Manager takes the requirements,
# organises them into a delivery plan, and drives Functional + Technical to
# complete each one (with Director QA on every step).
# --------------------------------------------------------------------------- #
def _country_code(country: str | None) -> str:
    """Map a free-text country to a finance regime code (defaults to UAE)."""
    c = (country or "").lower()
    table = {"SA": ["saudi", "ksa", "k.s.a"], "AE": ["uae", "emirates", "u.a.e", "dubai", "abu dhabi"],
             "BH": ["bahrain"], "OM": ["oman"], "QA": ["qatar"], "KW": ["kuwait"],
             "PK": ["pakistan"]}
    for code, names in table.items():
        if any(n in c for n in names):
            return code
    return "AE"


def _estimate_requirements(eng: Engagement) -> list[dict]:
    """Best requirement list for sizing: BA catalog → functional → presales."""
    ba = (eng.stages.get("ba_requirements") or {}).get("functional_requirements") or []
    if ba:
        return [{"odoo_fit": r.get("odoo_fit"), "area": r.get("area")} for r in ba]
    fns = eng.stages.get("functional") or []
    if fns:
        out = []
        for f in fns:
            mods = ((f.get("standard_capability") or {}).get("modules") or [{}])
            out.append({"verdict": f.get("verdict"),
                        "area": (mods[0].get("name") if mods else None)})
        return out
    cands = (eng.stages.get("presales") or {}).get("candidate_requirements") or []
    return [{} for _ in cands]


def _estimate_block(eng: Engagement) -> str:
    est = eng.stages.get("estimate")
    if not est:
        return ""
    keep = {k: est[k] for k in ("total_man_days", "duration_weeks", "pricing",
                                "custom_builds") if k in est}
    return ("\n\nLOCAL EFFORT ESTIMATE (computed by the PM knowledge engine — use "
            "these grounded figures, do not invent different ones):\n"
            + json.dumps(keep, indent=2))


@app.post("/engagements/{eng_id}/estimate")
def estimate_engagement(eng_id: str):
    """Deterministic effort/timeline/price estimate from the requirements — no API."""
    eng = _engagement(eng_id)
    reqs = _estimate_requirements(eng)
    if not reqs:
        raise HTTPException(status_code=400,
                            detail="No requirements to estimate yet — run the "
                                   "Business Analyst (or Presales) first.")
    est = pm_knowledge.estimate(reqs)
    eng.stages["estimate"] = est
    store.save(eng)
    return est


def _delivery_packages(eng: Engagement) -> list[dict]:
    """Build work packages from the BA requirements catalog (preferred) or the
    presales candidate requirements."""
    pkgs: list[dict] = []
    ba = (eng.stages.get("ba_requirements") or {}).get("functional_requirements") or []
    if ba:
        for r in ba:
            fit = r.get("odoo_fit")
            pkgs.append({
                "id": r.get("id") or f"WP-{len(pkgs) + 1}",
                "requirement": r.get("requirement"), "area": r.get("area"),
                "priority": r.get("priority"), "odoo_fit": fit,
                "assigned_to": "technical" if fit in ("custom", "studio") else "functional",
                "status": "pending"})
    else:
        for c in (eng.stages.get("presales") or {}).get("candidate_requirements") or []:
            req = c.get("requirement") if isinstance(c, dict) else c
            if req:
                pkgs.append({"id": f"WP-{len(pkgs) + 1}", "requirement": req,
                             "assigned_to": "functional", "status": "pending"})
    return pkgs


def _deliver_progress(plan: dict) -> dict:
    pkgs = plan.get("packages") or []
    done = len([p for p in pkgs if p.get("status") == "done"])
    return {"done": done, "total": len(pkgs), "build": plan.get("build")}


@app.post("/engagements/{eng_id}/pm/deliver/plan")
def pm_deliver_plan(eng_id: str):
    """The PM organises every requirement into a sequenced delivery plan."""
    eng = _engagement(eng_id)
    pkgs = _delivery_packages(eng)
    if not pkgs:
        raise HTTPException(status_code=400,
                            detail="No requirements yet — run the Business Analyst "
                                   "(or at least Presales) first.")
    organization = None
    try:
        state = {"company": eng.company,
                 "requirements": [{"id": p["id"], "requirement": p["requirement"],
                                   "area": p.get("area"), "odoo_fit": p.get("odoo_fit")}
                                  for p in pkgs]}
        organization = run_agent(
            "dispatch",
            f"Engagement state:\n{json.dumps(state, indent=2)}\n\n"
            "As the Delivery Lead/PM, organise these requirements into a sequenced "
            "delivery plan (who does what, in what order) and return the JSON.",
            account_id=eng.account_id, engagement_id=eng.id)
    except Exception:
        organization = None
    customs = len([p for p in pkgs if p.get("odoo_fit") in ("custom", "studio")])
    summary = (f"{len(pkgs)} requirements organised — {len(pkgs) - customs} via "
               f"Functional/config, {customs} need a Technical build.")
    plan = {"summary": summary, "packages": pkgs, "organization": organization,
            "build": {"needed": None, "status": "pending"}, "created_at": _now_iso()}
    eng.stages["delivery_plan"] = plan
    store.save(eng)
    return plan


@app.post("/engagements/{eng_id}/pm/deliver/step")
def pm_deliver_step(eng_id: str):
    """Execute the next item of the delivery plan: Functional analysis for the
    next pending requirement, then a Technical build once all customs are known.
    The console loops this until done. Director QA runs on every step."""
    eng = _engagement(eng_id)
    plan = eng.stages.get("delivery_plan")
    if not plan:
        raise HTTPException(status_code=400, detail="Organise the delivery plan first")
    pkgs = plan.get("packages") or []

    nxt = next((p for p in pkgs if p.get("status") == "pending"), None)
    if nxt:
        try:
            out, reviews = _run_with_qa("functional", eng_id, nxt["requirement"])
        except HTTPException as exc:
            eng = _engagement(eng_id)
            plan = eng.stages.get("delivery_plan") or plan
            for p in plan.get("packages") or []:
                if p.get("id") == nxt["id"]:
                    p["status"] = "error"
                    p["error"] = str(exc.detail)
            store.save(eng)
            return {"status": "error", "ran": "functional", "package": nxt["id"],
                    "error": str(exc.detail), "progress": _deliver_progress(plan)}
        verdict = (out or {}).get("verdict")
        local = str((out or {}).get("source", "")).startswith("knowledge-base")
        last = reviews[-1] if reviews else None
        eng = _engagement(eng_id)                       # functional appended + saved
        plan = eng.stages.get("delivery_plan") or plan
        for p in plan.get("packages") or []:
            if p.get("id") == nxt["id"]:
                p["status"] = "done"
                p["functional_verdict"] = verdict
        store.save(eng)
        return {"status": "running", "ran": "functional", "package": nxt["id"],
                "requirement": nxt["requirement"], "verdict": verdict, "local": local,
                "review": ({"score": last.get("score"), "verdict": last.get("verdict"),
                            "revisions": max(0, len(reviews) - 1)} if last else None),
                "progress": _deliver_progress(plan)}

    # all functional done — build once if anything came back custom
    customs = [p for p in pkgs if p.get("functional_verdict") == "custom"]
    plan["build"]["needed"] = bool(customs)
    if customs and not eng.stages.get("developer"):
        try:
            _out, reviews = _run_with_qa("developer", eng_id, None)
        except HTTPException as exc:
            return {"status": "error", "ran": "developer",
                    "error": str(exc.detail), "progress": _deliver_progress(plan)}
        last = reviews[-1] if reviews else None
        eng = _engagement(eng_id)
        plan = eng.stages.get("delivery_plan") or plan
        plan["build"] = {"needed": True, "status": "done"}
        store.save(eng)
        return {"status": "running", "ran": "developer",
                "review": ({"score": last.get("score"), "verdict": last.get("verdict"),
                            "revisions": max(0, len(reviews) - 1)} if last else None),
                "progress": _deliver_progress(plan)}

    plan["build"]["status"] = "done"
    store.save(eng)
    return {"status": "done", "progress": _deliver_progress(plan)}


@app.get("/engagements/{eng_id}/pm/deliver")
def pm_deliver_get(eng_id: str):
    eng = _engagement(eng_id)
    return eng.stages.get("delivery_plan") or {"packages": [], "summary": None}


# --------------------------------------------------------------------------- #
# Project execution — live Odoo task board (human actions, not gated)
# --------------------------------------------------------------------------- #
@app.get("/engagements/{eng_id}/tasks")
def list_tasks(eng_id: str):
    """The engagement's Odoo project tasks + stages, for the execution board."""
    eng = _engagement(eng_id)
    if not eng.odoo_db:
        return {"linked": False, "project_id": None, "tasks": [], "stages": []}
    try:
        c = get_client(eng.odoo_db)
        stages = c.execute("project.task.type", "search_read", [],
                           fields=["name", "fold"], limit=50)
        tasks = []
        if eng.project_id:
            tasks = c.execute("project.task", "search_read",
                              [("project_id", "=", eng.project_id)],
                              fields=["name", "stage_id", "kanban_state", "date_deadline"],
                              limit=300)
        return {"linked": True, "project_id": eng.project_id, "tasks": tasks, "stages": stages}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_friendly_odoo_error(exc))


@app.post("/engagements/{eng_id}/tasks")
def create_task(eng_id: str, body: dict):
    eng = _engagement(eng_id)
    if not eng.odoo_db or not eng.project_id:
        raise HTTPException(status_code=400, detail="No linked Odoo project (run Project first)")
    name = (body or {}).get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    try:
        tid = get_client(eng.odoo_db).create_task(eng.project_id, name)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_friendly_odoo_error(exc))
    return {"task_id": tid}


@app.post("/engagements/{eng_id}/tasks/{task_id}")
def update_task(eng_id: str, task_id: int, body: dict):
    """Move a task's stage or set its kanban state (done/blocked/normal)."""
    eng = _engagement(eng_id)
    if not eng.odoo_db:
        raise HTTPException(status_code=400, detail="No Odoo DB linked")
    vals = {}
    if "stage_id" in body:
        vals["stage_id"] = body["stage_id"]
    if "kanban_state" in body:
        vals["kanban_state"] = body["kanban_state"]
    if not vals:
        raise HTTPException(status_code=400, detail="nothing to update")
    try:
        get_client(eng.odoo_db).execute("project.task", "write", [task_id], vals)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_friendly_odoo_error(exc))
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Delivery Director — the QA brain. Scores every specialist's output against the
# house bar and drives an auto-revision loop so weak stages get re-run.
# --------------------------------------------------------------------------- #
QA_BAR = int(os.getenv("C2P_QA_BAR", "75"))
QA_MAX_REVISIONS = int(os.getenv("C2P_QA_MAX_REVISIONS", "1"))
# Built-in Odoo intelligence: resolve clear requirements locally (no API call).
LOCAL_INTELLIGENCE = os.getenv("C2P_LOCAL_INTELLIGENCE", "1") == "1"
LOCAL_CONFIDENCE = float(os.getenv("C2P_LOCAL_CONFIDENCE", "0.8"))
# Set C2P_QA_ENABLED=0 to skip the Director review pass — roughly halves model
# calls (no review, no auto-revision), useful on a tight token/credit budget.
QA_ENABLED = os.getenv("C2P_QA_ENABLED", "1") == "1"


def _review_output(stage: str, out: dict, eng: Engagement) -> dict | None:
    """Run the Delivery Director over a specialist's output; returns the review."""
    if not QA_ENABLED:
        return None
    content = (
        f"Specialist stage under review: {stage}\n"
        f"Client: {eng.company}\nIndustry: {_industry_for(eng) or 'unknown'}\n"
        f"Quality bar to clear: {QA_BAR}/100\n\n"
        f"Output to review (JSON):\n{json.dumps(out, indent=2)[:12000]}\n\n"
        "Review it and return the JSON."
    )
    try:
        return run_agent("director", content, account_id=eng.account_id, engagement_id=eng.id)
    except HTTPException:
        return None


def _store_review(eng: Engagement, stage: str, review: dict) -> None:
    eng.stages.setdefault("_reviews", {}).setdefault(stage, []).append(
        {"score": review.get("score"), "verdict": review.get("verdict"),
         "gaps": review.get("gaps"), "at": _now_iso()})


def _validate_module_files(files) -> list[str]:
    """Structural pre-flight on a generated Odoo module: a manifest exists,
    Python compiles, XML is well-formed. Returns human-readable errors (empty=ok)."""
    import ast
    import xml.etree.ElementTree as ET
    errs: list[str] = []
    files = files or []
    if not any((f.get("path") or "").endswith("__manifest__.py") for f in files):
        errs.append("Module is missing an __manifest__.py file.")
    for f in files:
        path = f.get("path") or ""
        content = f.get("content") or ""
        lang = (f.get("language") or "").lower()
        if path.endswith(".py") or lang == "py":
            try:
                ast.parse(content)
            except SyntaxError as e:
                errs.append(f"Python syntax error in {path}: {e.msg} (line {e.lineno}).")
        elif path.endswith(".xml") or lang == "xml":
            try:
                ET.fromstring(content)
            except Exception as e:  # noqa: BLE001
                errs.append(f"XML is not well-formed in {path}: {e}.")
    return errs[:8]


def _stage_output(eng: Engagement, kind: str):
    if kind == "functional":
        lst = eng.stages.get("functional") or []
        return lst[-1] if lst else None
    return eng.stages.get(kind)


def _run_specialist(kind: str, eng_id: str, arg: str | None) -> None:
    if kind == "proposal":
        proposal(eng_id, m.ProposalIn())
    elif kind == "project":
        project(eng_id, m.ProjectIn())
    elif kind == "functional":
        functional(eng_id, m.FunctionalIn(requirement=arg or "Requirement",
                                          industry=_industry_for(_engagement(eng_id))))
    elif kind == "developer":
        developer(eng_id, m.DeveloperIn())


def _run_with_qa(kind: str, eng_id: str, arg: str | None):
    """Run a specialist, have the Director score it (+ structural validation for
    developer modules), and auto-revise up to the cap if it misses the bar.
    Returns (final_output, reviews)."""
    reviews: list[dict] = []
    out = None
    feedback = ""
    for attempt in range(QA_MAX_REVISIONS + 1):
        if attempt == 0:
            _run_specialist(kind, eng_id, arg)
        else:
            if kind == "functional":            # replace, don't append, on revise
                e = _engagement(eng_id)
                lst = e.stages.get("functional") or []
                if lst:
                    lst.pop()
                    store.save(e)
            tok = _qa_feedback.set(feedback)
            try:
                _run_specialist(kind, eng_id, arg)
            finally:
                _qa_feedback.reset(tok)
        eng = _engagement(eng_id)
        out = _stage_output(eng, kind)
        if not out:
            break
        struct = _validate_module_files(out.get("files")) if kind == "developer" else []
        review = _review_output(kind, out, eng)
        if not review:
            break
        if struct:                              # build errors force a revision
            review["verdict"] = "revise"
            review["score"] = min(review.get("score") or 0, 55)
            review["gaps"] = (review.get("gaps") or []) + struct
            review["feedback"] = ((review.get("feedback") or "")
                                  + "\nFix these build/validation errors:\n- "
                                  + "\n- ".join(struct))
        reviews.append(review)
        _store_review(eng, kind, review)
        store.save(eng)
        if (review.get("verdict") == "revise" and (review.get("score") or 0) < QA_BAR
                and attempt < QA_MAX_REVISIONS):
            feedback = review.get("feedback") or ""
            continue
        break
    return out, reviews


# --------------------------------------------------------------------------- #
# Deliverable documents — Functional / PM / Technical author real, branded
# documents (BRD, FRS, Gap-Fit, Charter, Status Report, Tech Design, SOW).
# --------------------------------------------------------------------------- #
DOC_TYPES = {
    "brd": "Business Requirements Document",
    "frs": "Functional Specification Document (FRS)",
    "gapfit": "Gap-Fit Analysis",
    "charter": "Project Charter",
    "status": "Project Status Report",
    "techdesign": "Technical Design Document",
    "sow": "Statement of Work",
}


def _doc_source(eng: Engagement) -> str:
    parts = []
    for s in ("presales", "ba_requirements", "proposal", "project"):
        if eng.stages.get(s):
            parts.append(f"### {s} output\n{json.dumps(eng.stages[s], indent=2)}")
    fns = eng.stages.get("functional") or []
    if fns:
        parts.append(f"### functional analyses\n{json.dumps(fns, indent=2)}")
    dev = eng.stages.get("developer")
    if dev:
        d = {k: v for k, v in dev.items() if k != "files"}   # summary, not full code
        parts.append(f"### developer module summary\n{json.dumps(d, indent=2)}")
    answered = [q for q in ((eng.stages.get("clarifications") or {}).get("questions") or [])
                if q.get("status") == "answered"]
    if answered:
        parts.append("### client answers\n" + json.dumps(
            [{"q": q.get("question"), "a": q.get("answer")} for q in answered], indent=2))
    return "\n\n".join(parts)[:16000] or "(no stage outputs yet)"


@app.post("/engagements/{eng_id}/document/{doc_key}")
def author_document(eng_id: str, doc_key: str, body: dict | None = None):
    """An agent authors a formal client deliverable from the engagement's stage
    outputs, then the Director QA-scores it. Stored on the engagement."""
    eng = _engagement(eng_id)
    name = DOC_TYPES.get(doc_key)
    if not name:
        raise HTTPException(status_code=400, detail="Unknown document type")
    body = body or {}
    content = (
        f"Author this document: {name}\n"
        f"Client: {eng.company}\nIndustry: {_industry_for(eng) or 'unknown'}\n"
        f"Extra direction: {body.get('instructions') or 'none'}\n\n"
        f"Source material (engagement stage outputs):\n{_doc_source(eng)}\n\n"
        "Write the full document JSON."
        + industry.playbook_block(_industry_for(eng))
    )
    try:
        out = run_agent("docwriter", content, account_id=eng.account_id, engagement_id=eng.id)
    except HTTPException:
        # API unavailable: assemble the document from structured data — no API,
        # so a full Autopilot run still completes (templated prose, not LLM prose).
        if LOCAL_INTELLIGENCE:
            out = doc_templates.build(doc_key, eng)
        else:
            raise
    out["doc_key"] = doc_key
    out.setdefault("doc_type", name)
    review = _review_output(f"document:{doc_key}", out, eng)
    if review:
        out["_qa"] = {"score": review.get("score"), "verdict": review.get("verdict")}
    eng.stages.setdefault("documents", {})[doc_key] = out
    store.save(eng)
    return out


@app.get("/engagements/{eng_id}/documents")
def list_documents(eng_id: str):
    eng = _engagement(eng_id)
    authored = eng.stages.get("documents") or {}
    return {"catalog": [
        {"key": k, "name": v, "authored": k in authored,
         "qa": (authored.get(k) or {}).get("_qa")}
        for k, v in DOC_TYPES.items()]}


def _pdf_response(html: str, filename: str) -> Response:
    """Return a real PDF when WeasyPrint is available; otherwise return the
    branded HTML that auto-opens the browser print dialog (Save as PDF). Either
    way the operator gets a PDF — by default, no extra clicks."""
    pdf = proposal_render.to_pdf(html)
    if pdf:
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{filename}"'})
    inj = html.replace(
        "</body>",
        "<script>window.addEventListener('load',function(){setTimeout(function(){"
        "window.print();},350);});</script></body>")
    return Response(content=inj, media_type="text/html")


def _doc_html(eng: Engagement, doc_key: str) -> str:
    doc = (eng.stages.get("documents") or {}).get(doc_key)
    if not doc:
        raise HTTPException(status_code=400, detail="Author this document first")
    return proposal_render.render_document_html(
        doc, eng.company, proposal_render.brand(store), date_str=_now_iso()[:10])


@app.get("/engagements/{eng_id}/document/{doc_key}/preview")
def document_preview(eng_id: str, doc_key: str):
    return Response(content=_doc_html(_engagement(eng_id), doc_key), media_type="text/html")


@app.get("/engagements/{eng_id}/document/{doc_key}/pdf")
def document_pdf(eng_id: str, doc_key: str):
    eng = _engagement(eng_id)
    fname = f"{doc_key}-{eng.company}.pdf".replace(" ", "_")
    return _pdf_response(_doc_html(eng, doc_key), fname)


# --------------------------------------------------------------------------- #
# Client Q&A loop — agents raise open questions; the PM compiles them into one
# client-ready RFI; the client's answers flow back to the agents.
# --------------------------------------------------------------------------- #
def _client_answers_block(eng: Engagement) -> str:
    """Answered clarifications, rendered for injection into a specialist's prompt
    so the agent works from the client's confirmed answers, not assumptions."""
    qs = (eng.stages.get("clarifications") or {}).get("questions") or []
    answered = [q for q in qs if q.get("status") == "answered" and q.get("answer")]
    if not answered:
        return ""
    lines = "\n".join(
        f"- Q: {q.get('question')}\n  Client answer: {q.get('answer')}" for q in answered)
    return ("\n\nCLIENT-CONFIRMED ANSWERS (authoritative — these supersede any "
            "assumption):\n" + lines)


def _merge_questions_into_rfi(eng: Engagement, items: list[dict]) -> int:
    """Add new open questions to the engagement's RFI, deduplicated by text.
    Returns how many were actually added. Caller persists the engagement."""
    rec = eng.stages.get("clarifications") or {"summary": None, "questions": []}
    qs = rec.get("questions") or []
    seen = {(q.get("question") or "").strip().lower()[:80] for q in qs}
    added = 0
    for it in items:
        q = (it.get("question") or "").strip()
        key = q.lower()[:80]
        if not q or key in seen:
            continue
        qs.append({**it, "question": q, "status": "open", "answer": None})
        seen.add(key)
        added += 1
    for i, q in enumerate(qs, 1):
        q["id"] = f"q{i}"
    rec["questions"] = qs
    eng.stages["clarifications"] = rec
    store.save(eng)
    return added


@app.post("/engagements/{eng_id}/clarifications/compile")
def compile_clarifications(eng_id: str):
    """The PM scans every stage's output and compiles a single, deduplicated,
    client-ready RFI — preserving any questions the client already answered."""
    eng = _engagement(eng_id)
    existing = eng.stages.get("clarifications") or {}
    answered = [q for q in (existing.get("questions") or []) if q.get("status") == "answered"]
    prior = "\n".join(f"- {q.get('question')} => {q.get('answer')}" for q in answered) or "(none yet)"
    content = (
        f"Client: {eng.company}\nIndustry: {_industry_for(eng) or 'unknown'}\n\n"
        f"Engagement stage outputs:\n{_doc_source(eng)}\n\n"
        f"Questions the client has ALREADY answered (never ask these again):\n{prior}\n\n"
        "Compile the consolidated client RFI JSON."
    )
    try:
        out = run_agent("clarifier", content, account_id=eng.account_id, engagement_id=eng.id)
    except HTTPException:
        # API down: gather open items from the stages ourselves — no model.
        if not LOCAL_INTELLIGENCE:
            raise
        items = []
        for q in (eng.stages.get("ba_requirements") or {}).get("open_questions") or []:
            items.append({"question": q, "theme": "Requirements", "waiting_agent": "functional",
                          "blocks": "medium"})
        for q in (eng.stages.get("ba_discovery") or {}).get("key_decisions_for_client") or []:
            items.append({"question": q, "theme": "Key decision", "waiting_agent": "project",
                          "blocks": "high"})
        out = {"summary": f"{len(items)} open item(s) gathered from the analysis for client input.",
               "questions": items}
    qs: list[dict] = []
    seen: set[str] = set()
    for q in answered:                               # keep answered items
        qs.append(q)
        seen.add((q.get("question") or "").strip().lower()[:80])
    for q in (out.get("questions") or []):           # add new open items
        key = (q.get("question") or "").strip().lower()[:80]
        if key and key not in seen:
            q["status"] = "open"
            q["answer"] = None
            qs.append(q)
            seen.add(key)
    for i, q in enumerate(qs, 1):                    # stable sequential ids
        q["id"] = f"q{i}"
    rec = {"summary": out.get("summary"), "questions": qs, "compiled_at": _now_iso()}
    eng.stages["clarifications"] = rec
    store.save(eng)
    return rec


@app.get("/engagements/{eng_id}/clarifications")
def get_clarifications(eng_id: str):
    eng = _engagement(eng_id)
    return eng.stages.get("clarifications") or {"summary": None, "questions": []}


@app.post("/engagements/{eng_id}/clarifications/answer")
def answer_clarification(eng_id: str, body: dict):
    """Record the client's (or PM's) answer to one RFI question and feed it back
    into the account knowledge so every agent works from it."""
    eng = _engagement(eng_id)
    rec = eng.stages.get("clarifications") or {"questions": []}
    qid = (body or {}).get("id")
    ans = (body or {}).get("answer")
    if not qid or ans is None:
        raise HTTPException(status_code=400, detail="id and answer are required")
    hit = None
    for q in rec.get("questions") or []:
        if q.get("id") == qid:
            q["status"] = "answered"
            q["answer"] = ans
            q["answered_at"] = _now_iso()
            hit = q
    if not hit:
        raise HTTPException(status_code=404, detail="Question not found")
    eng.stages["clarifications"] = rec
    store.save(eng)
    if eng.account_id:
        ks.write_entry(
            eng.account_id, "client_answer",
            {"question": hit.get("question"), "answer": ans},
            title=f"Client answer — {(hit.get('question') or '')[:50]}", learned_by="pm")
    return rec


# --------------------------------------------------------------------------- #
# Autopilot — the super-agent that runs the whole engagement, one step at a
# time, chaining the specialists and pausing at approval gates.
# --------------------------------------------------------------------------- #
def _eng_approvals(eng_id: str, action_type: str | None = None):
    return [a for a in store.list_approvals(None, limit=500)
            if a.engagement_id == eng_id
            and (action_type is None or a.action_type == action_type)]


def _autopilot_decide(eng: Engagement):
    """Decide the single next step from the engagement state, or None if done."""
    st = eng.stages
    if not st.get("presales"):
        return ("presales", None)
    # The Business Analyst gathers requirements before scoping/pricing — but only
    # if we haven't already proposed. For an engagement that already has a
    # proposal, BA discovery is moot; don't dead-end Autopilot on it.
    if not st.get("proposal"):
        if not st.get("ba_discovery"):
            return ("ba_discovery", None)
        if not st.get("ba_requirements"):
            return ("ba_requirements", None)
        return ("proposal", None)
    if not st.get("project"):
        return ("project", None)
    # Functional analysis works the BA's requirement catalog when present,
    # else the presales candidate requirements.
    ba_reqs = [r.get("requirement")
               for r in (st.get("ba_requirements") or {}).get("functional_requirements") or []]
    cands = ba_reqs or [c.get("requirement")
                        for c in (st.get("presales") or {}).get("candidate_requirements") or []]
    analysed = " || ".join((f.get("requirement_summary") or "")
                           for f in (st.get("functional") or [])).lower()
    for req in cands:
        if req and req.lower()[:40] not in analysed:
            return ("functional", req)
    customs = [f for f in (st.get("functional") or []) if f.get("verdict") == "custom"]
    if customs and not st.get("developer"):
        return ("developer", None)
    # The agency authors its own deliverable documents once the inputs exist.
    docs = st.get("documents") or {}
    doc_plan = []
    if st.get("proposal"):
        doc_plan.append("brd")
    if st.get("functional"):
        doc_plan.append("frs")
    if st.get("project"):
        doc_plan.append("charter")
    if st.get("developer"):
        doc_plan.append("techdesign")
    for dk in doc_plan:
        if dk not in docs:
            return ("document", dk)
    if eng.odoo_db and not st.get("config") and not _eng_approvals(eng.id, "config_apply"):
        return ("config", None)
    if st.get("developer") and not _eng_approvals(eng.id, "code_deploy"):
        return ("deploy", None)
    return None


@app.post("/engagements/{eng_id}/autopilot/step")
def autopilot_step(eng_id: str):
    """Run the next pipeline step. The console calls this in a loop until the
    status is done / blocked (approval) / needs_input / error."""
    eng = _engagement(eng_id)
    dec = _autopilot_decide(eng)
    if not dec:
        return {"status": "done", "ran": None}
    kind, arg = dec
    if kind == "presales":
        return {"status": "needs_input", "ran": "presales"}
    try:
        if kind == "ba_discovery":
            r = ba_discovery(eng_id, {})
            return {"status": "running", "ran": "ba_discovery",
                    "questions_pushed": r.get("questions_pushed", 0)}
        elif kind == "ba_requirements":
            ba_requirements(eng_id, {})
            return {"status": "running", "ran": "ba_requirements"}
        elif kind in ("proposal", "project", "functional", "developer"):
            _out, reviews = _run_with_qa(kind, eng_id, arg)
            last = reviews[-1] if reviews else None
            return {"status": "running", "ran": kind,
                    "review": ({"score": last.get("score"),
                                "verdict": last.get("verdict"),
                                "revisions": max(0, len(reviews) - 1)} if last else None)}
        elif kind == "document":
            doc = author_document(eng_id, arg, {})
            return {"status": "running", "ran": "document", "doc": arg,
                    "doc_name": DOC_TYPES.get(arg, arg),
                    "review": doc.get("_qa")}
        elif kind == "config":
            r = config_apply(eng_id, {})
            if r.get("approval"):
                return {"status": "blocked", "ran": "config", "approval": r["approval"]}
            return {"status": "running", "ran": "config"}
        elif kind == "deploy":
            r = deploy_module(eng_id, {})
            if r.get("approval"):
                return {"status": "blocked", "ran": "deploy", "approval": r["approval"]}
            return {"status": "running", "ran": "deploy"}
    except HTTPException as exc:
        return {"status": "error", "ran": kind, "error": str(exc.detail)}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "ran": kind, "error": str(exc)}
    return {"status": "running", "ran": kind}


# --------------------------------------------------------------------------- #
# Phase 2 — Outreach (SDR) + the approval layer
# --------------------------------------------------------------------------- #
@app.post("/accounts/{account_id}/outreach")
def outreach(account_id: str, body: m.OutreachIn, request: Request):
    """Draft a personalised outreach sequence (auto). Actually SENDING the first
    touch is gated — this also creates a pending Approval for the send."""
    _require_edition(request, "outreach")
    acc = _account(account_id)
    content = (
        f"Prospect company: {acc.name}\nCountry: {acc.country or 'UAE/GCC'}\n"
        f"Industry: {acc.industry or 'unknown'}\nChannel: {body.channel}\n"
        f"Contact: {body.contact_name or 'the right decision-maker'}\n"
        f"Angle: {body.angle or 'open a conversation about an Odoo outcome'}\n\n"
        "Write the outreach sequence JSON."
        + industry.playbook_block(acc.industry)
        + ks.context_block(account_id, body.angle or acc.industry or acc.name)
    )
    out = run_agent("outreach", content, account_id=account_id)
    ks.write_entry(account_id, "communication", out,
                   title=f"Outreach draft ({body.channel})", learned_by="outreach",
                   tags=["outreach", "draft"])
    approval = None
    if body.auto_queue_send:
        first = (out.get("sequence") or [{}])[0]
        approval = policy.gate(
            store, "outreach_send",
            {"channel": body.channel, "to": body.contact_name or acc.name,
             "account_id": account_id, "company": acc.name, "message": first},
            requester_agent="outreach", account_id=account_id,
        )
    return {"draft": out, "approval": approval.model_dump() if approval else None}


def _execute_proposal_send(payload: dict, account_id: str | None = None) -> dict:
    """Render the branded proposal, attach it to the Odoo quotation, optionally
    email the client, and log it. Shared by the gated-approve path and the
    (rare) auto path."""
    eng = store.get(payload.get("engagement_id"))
    prop = (eng.stages.get("proposal") if eng else None) or {}
    b = proposal_render.brand(store)
    company = eng.company if eng else payload.get("company", "")
    html = proposal_render.render_html(
        prop, company, b, date_str=_now_iso()[:10])
    pdf = proposal_render.to_pdf(html)
    result = {"rendered": True, "pdf": bool(pdf)}
    if eng and eng.odoo_db:
        try:
            c = get_client(eng.odoo_db)
            so_id = eng.sale_order_id
            if not so_id and eng.crm_lead_id:
                pid = c.partner_of_lead(eng.crm_lead_id)
                if pid:
                    so_id = c.create_quotation(pid, note=prop.get("solution_summary", ""))
                    eng.sale_order_id = so_id
                    store.save(eng)
            if so_id:
                if pdf:
                    c.attach_bytes("sale.order", so_id, f"Proposal - {company}.pdf",
                                   pdf, "application/pdf")
                else:
                    c.attach_bytes("sale.order", so_id, f"Proposal - {company}.html",
                                   html.encode("utf-8"), "text/html")
                c.message_post("sale.order", so_id, "C2P proposal issued to the client.")
                result["sale_order_id"] = so_id
        except Exception as exc:  # noqa: BLE001
            result["odoo_error"] = str(exc)
    if payload.get("email") and payload.get("to"):
        result["email"] = channels.send(
            "email", payload["to"], f"Proposal — {b['name']}",
            "Please find our Odoo solution proposal attached.")
    aid = account_id or (eng.account_id if eng else None)
    if aid:
        ks.write_entry(aid, "deliverable",
                       {"type": "proposal", "company": company,
                        "sale_order_id": result.get("sale_order_id")},
                       title="Proposal issued", learned_by="owner",
                       tags=["proposal", "sent"])
    return result


def _execute_deploy(payload: dict, account_id: str | None = None) -> dict:
    """Write the generated module to the account's addons repo (staged by
    default; live git push when configured). Logs the deploy."""
    eng = store.get(payload.get("engagement_id"))
    dev = (eng.stages.get("developer") if eng else None) or {}
    name = deployer._slug(dev.get("module_technical_name") or "module")
    if github_mod.configured():                 # push straight to the GitHub repo
        try:
            res = github_mod.push_module(
                name, dev.get("files") or [],
                message=f"Deploy module {name} ({payload.get('engagement_id')})")
            res["mode"] = "github"
        except Exception as exc:  # noqa: BLE001 - surface, don't crash
            res = {"module": name, "mode": "github", "pushed": False,
                   "error": str(exc)}
    else:                                        # staged on disk / env git push
        res = deployer.deploy_module(dev)
    aid = account_id or (eng.account_id if eng else None)
    if aid:
        ks.write_entry(aid, "deliverable",
                       {"type": "module_deploy", "module": res.get("module"),
                        "mode": res.get("mode"), "pushed": res.get("pushed")},
                       title=f"Module deployed — {res.get('module')}",
                       learned_by="developer", tags=["deploy"])
    try:
        if eng and eng.odoo_db and eng.crm_lead_id:
            get_client(eng.odoo_db).message_post(
                "crm.lead", eng.crm_lead_id,
                f"C2P module '{res.get('module')}' deployed ({res.get('mode')}).")
    except Exception:
        pass
    return res


def _execute_config_apply(payload: dict, account_id: str | None = None) -> dict:
    """Apply the config recipe to the engagement's Odoo via the API (create/write
    only — safe, gated). Returns per-operation results."""
    eng = store.get(payload.get("engagement_id"))
    db = eng.odoo_db if eng else None
    if not db:
        return {"error": "engagement has no odoo_db linked"}
    c = get_client(db)
    results = []
    for op in payload.get("operations") or []:
        label, model = op.get("label"), op.get("model")
        method = (op.get("method") or "create").lower()
        vals = op.get("values") or {}
        try:
            if not model:
                raise ValueError("missing model")
            if method == "create":
                rid = c.execute(model, "create", vals)
                results.append({"label": label, "model": model, "id": rid, "ok": True})
            elif method == "ensure":
                # idempotent: create only if no record matches the domain
                ids = c.execute(model, "search", op.get("domain") or [])
                if ids:
                    results.append({"label": label, "model": model, "ids": ids,
                                    "ok": True, "skipped": "already exists"})
                else:
                    rid = c.execute(model, "create", vals)
                    results.append({"label": label, "model": model, "id": rid, "ok": True})
            elif method == "write":
                ids = c.execute(model, "search", op.get("domain") or [])
                if ids:
                    c.execute(model, "write", ids, vals)
                    results.append({"label": label, "model": model, "ids": ids, "ok": True})
                else:
                    results.append({"label": label, "model": model, "ok": False,
                                    "error": "no records matched domain"})
            else:
                results.append({"label": label, "ok": False,
                                "error": f"method '{method}' not allowed"})
        except Exception as exc:  # noqa: BLE001
            results.append({"label": label, "model": model, "ok": False, "error": str(exc)})
    applied = sum(1 for r in results if r.get("ok"))
    try:
        if eng and eng.crm_lead_id:
            c.message_post("crm.lead", eng.crm_lead_id,
                           f"C2P applied {applied}/{len(results)} Odoo config operations.")
    except Exception:
        pass
    aid = account_id or (eng.account_id if eng else None)
    if aid:
        ks.write_entry(aid, "deliverable", {"type": "config_apply", "results": results},
                       title="Odoo config applied", learned_by="config", tags=["config"])
    return {"applied": applied, "total": len(results), "results": results}


def _execute_action(appr) -> dict:
    """Run a gated action once a human approves it. Returns a result dict."""
    action, payload = appr.action_type, appr.payload or {}
    if action == "proposal_send":
        return _execute_proposal_send(payload, account_id=appr.account_id)
    if action == "code_deploy":
        return _execute_deploy(payload, account_id=appr.account_id)
    if action == "config_apply":
        return _execute_config_apply(payload, account_id=appr.account_id)
    if action == "client_comms_sensitive":
        msg = payload.get("message") or {}
        res = channels.send(payload.get("channel", "email"), payload.get("to", ""),
                            msg.get("subject", "C2P Consultants"), msg.get("body", ""))
        if appr.account_id:
            ks.write_entry(appr.account_id, "communication",
                           {"direction": "outbound", "to": payload.get("to"),
                            "message": msg, "send_result": res},
                           title="Reply sent (approved)", learned_by="owner",
                           tags=["outbound", "sent"])
        return res
    if action == "outreach_send":
        msg = payload.get("message") or {}
        res = channels.send(payload.get("channel", "email"), payload.get("to", ""),
                            msg.get("subject", "C2P Consultants"), msg.get("body", ""))
        if appr.account_id:
            ks.write_entry(appr.account_id, "communication",
                           {"channel": payload.get("channel"), "to": payload.get("to"),
                            "message": msg, "send_result": res},
                           title="Outreach sent", learned_by="owner",
                           tags=["outreach", "sent"])
        # Best-effort chatter log if we have an Odoo lead for the account.
        try:
            acc = store.get_account(appr.account_id) if appr.account_id else None
            if acc and acc.odoo_db and acc.partner_id:
                get_client(acc.odoo_db).message_post(
                    "res.partner", acc.partner_id,
                    f"C2P outreach ({payload.get('channel')}): {msg.get('subject','')}")
        except Exception:
            pass
        return res
    return {"note": "no executor registered", "action": action}


@app.get("/approvals")
def list_approvals(status: str | None = "pending", limit: int = 100):
    return [a.model_dump() for a in store.list_approvals(status, limit=limit)]


@app.get("/approvals/count")
def approvals_count():
    return {"pending": store.count_approvals("pending")}


@app.post("/approvals/{approval_id}/decide")
def decide_approval(approval_id: str, body: m.ApprovalDecisionIn):
    appr = store.get_approval(approval_id)
    if not appr:
        raise HTTPException(status_code=404, detail="Approval not found")
    if appr.status != "pending":
        raise HTTPException(status_code=400, detail=f"Already {appr.status}")
    if body.decision not in ("approved", "rejected", "edited"):
        raise HTTPException(status_code=400, detail="decision must be approved|rejected|edited")

    # Capture the human's edit as owned correction data.
    if body.decision == "edited" and body.edited_payload is not None:
        appr.payload = body.edited_payload

    result = None
    if body.decision in ("approved", "edited"):
        result = _execute_action(appr)

    appr.status = body.decision
    appr.decided_by = body.decided_by
    appr.decided_at = _now_iso()
    appr.reason = body.reason
    appr.result = result
    store.update_approval(appr)
    return appr.model_dump()


# --------------------------------------------------------------------------- #
# Phase 5 — Communications (inbound triage + sensitivity-gated outbound)
# --------------------------------------------------------------------------- #
@app.post("/comms/inbound")
def comms_inbound(body: m.CommsInboundIn, request: Request):
    """Triage an inbound message to the right account, draft a reply, and either
    send it (auto, routine) or queue it for approval (scope/money/commitment)."""
    _require_edition(request, "comms")
    acc = store.get_account(body.account_id) if body.account_id else None
    ctx = ks.context_block(acc.id, body.subject or body.body[:80]) if acc else ""
    content = (
        f"Inbound {body.channel} message:\nFrom: {body.from_party}\n"
        f"Subject: {body.subject}\n\n{body.body}\n\nTriage and draft a reply. Return the JSON."
        + ctx
    )
    out = run_agent("comms", content, account_id=acc.id if acc else None)

    if not acc and out.get("matched_company"):
        acc = store.find_account_by_name(out["matched_company"])
    aid = acc.id if acc else None

    store.add_comm(Communication(
        account_id=aid, direction="inbound", channel=body.channel,
        from_party=body.from_party, subject=body.subject, body=body.body, status="received"))
    if aid:
        ks.write_entry(aid, "communication",
                       {"direction": "inbound", "from": body.from_party,
                        "subject": body.subject, "intent": out.get("intent")},
                       title=f"Inbound: {body.subject or out.get('intent', 'message')}",
                       learned_by="comms", tags=["inbound"])

    reply = out.get("suggested_reply") or {}
    sensitivity = (out.get("sensitivity") or "auto").lower()
    result = {"triage": out, "account_id": aid}

    if sensitivity == "approval":
        appr = policy.gate(
            store, "client_comms_sensitive",
            {"channel": body.channel, "to": body.from_party, "account_id": aid,
             "message": reply, "in_reply_to": body.subject},
            requester_agent="comms", account_id=aid)
        store.add_comm(Communication(
            account_id=aid, direction="outbound", channel=body.channel,
            to_party=body.from_party, subject=reply.get("subject", ""),
            body=reply.get("body", ""), status="drafted", sensitivity="approval",
            approval_id=appr.id if appr else None))
        result["approval"] = appr.model_dump() if appr else None
    else:
        send = channels.send(body.channel, body.from_party,
                             reply.get("subject", "C2P Consultants"), reply.get("body", ""))
        store.add_comm(Communication(
            account_id=aid, direction="outbound", channel=body.channel,
            to_party=body.from_party, subject=reply.get("subject", ""),
            body=reply.get("body", ""), status="sent", sensitivity="auto"))
        if aid:
            ks.write_entry(aid, "communication",
                           {"direction": "outbound", "to": body.from_party,
                            "subject": reply.get("subject"), "auto": True, "send_result": send},
                           title="Auto reply sent", learned_by="comms", tags=["outbound"])
        result["sent"] = send
    return result


@app.get("/comms")
def list_comms(account_id: str | None = None, limit: int = 100):
    return [c.model_dump() for c in store.list_comms(account_id, limit=limit)]


@app.get("/industries")
def industries():
    """The industry playbook library agents use to ground scope and modules."""
    return industry.list_industries()


@app.get("/industries/{key}")
def industry_detail(key: str):
    p = industry.get(key)
    if not p:
        raise HTTPException(status_code=404, detail="Industry not found")
    return p


# --------------------------------------------------------------------------- #
# Phase 6 — Supervisor + Agency Cockpit metrics
# --------------------------------------------------------------------------- #
def _compute_metrics() -> dict:
    engs = [e for e in (store.get(x["id"]) for x in store.list()) if e]
    by_stage = {s: 0 for s in m.STAGES}
    pipeline = 0.0
    with_proposal = won_or_planned = 0
    for e in engs:
        for s in m.STAGES:
            v = e.stages.get(s)
            if (isinstance(v, list) and v) or (not isinstance(v, list) and v):
                by_stage[s] += 1
        prop = e.stages.get("proposal")
        if prop:
            with_proposal += 1
            try:
                pipeline += float((prop.get("commercial") or {}).get("estimate_aed") or 0)
            except Exception:
                pass
        if e.stages.get("project"):
            won_or_planned += 1
    return {
        "accounts": len(store.list_accounts()),
        "engagements": len(engs),
        "pipeline_value_aed": round(pipeline),
        "by_stage": by_stage,
        "with_proposal": with_proposal,
        "won_or_planned": won_or_planned,
        "win_rate": round(won_or_planned / with_proposal * 100) if with_proposal else 0,
        "pending_approvals": store.count_approvals("pending"),
        "communications": len(store.list_comms(limit=1000)),
        "agent_runs": len(store.list_runs(limit=1000)),
    }


@app.get("/metrics")
def metrics():
    """Agency metrics for the cockpit (pipeline value, by-stage, win rate, …)."""
    return _compute_metrics()


@app.post("/supervisor/brief")
def supervisor_brief(request: Request):
    """Daily 'what needs you today' briefing from the agency snapshot."""
    _require_edition(request, "supervisor")
    mx = _compute_metrics()
    approvals = store.list_approvals("pending", limit=20)
    comms = store.list_comms(limit=10)
    snap = json.dumps({
        "metrics": mx,
        "pending_approvals": [{"action": a.action_type, "requester": a.requester_agent,
                               "to": (a.payload or {}).get("to")} for a in approvals],
        "recent_comms": [{"direction": c.direction, "subject": c.subject,
                          "status": c.status} for c in comms],
    }, indent=2)
    out = run_agent("supervisor", f"Agency snapshot:\n{snap}\n\nProduce today's owner briefing JSON.")
    return {"briefing": out, "metrics": mx}


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


# --------------------------------------------------------------------------- #
# Phase 7 — Multi-tenant: auth, per-tenant config, Stripe billing (gated on
# MULTITENANT=1; when off these still load but signup/login refuse).
# --------------------------------------------------------------------------- #
def _claims(request: Request):
    return getattr(request.state, "claims", None)


_FEATURE_EDITION = {"prospect": "growth", "outreach": "growth",
                    "proposal_send": "growth", "comms": "agency",
                    "supervisor": "agency"}


def _require_edition(request: Request, feature: str):
    if not tenancy.MULTITENANT:
        return
    cl = _claims(request)
    t = control.get_tenant(cl["tenant_id"]) if cl else None
    need = _FEATURE_EDITION.get(feature, "delivery")
    have = t.edition if t else "delivery"
    if tenancy.EDITION_RANK.get(have, 1) < tenancy.EDITION_RANK.get(need, 1):
        raise HTTPException(status_code=402, detail=f"Requires the {need.title()} edition")


@app.post("/auth/signup")
def auth_signup(body: m.SignupIn):
    if not tenancy.MULTITENANT:
        raise HTTPException(status_code=400, detail="Multi-tenant mode is off")
    if control.get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    slug = base = tenancy.slugify(body.company)
    i = 1
    while control.get_tenant_by_slug(slug):
        i += 1
        slug = f"{base}-{i}"
    edition = body.edition if body.edition in tenancy.EDITION_RANK else "delivery"
    t = Tenant(name=body.company, slug=slug, edition=edition)
    if stripe_billing.configured():
        try:
            t.stripe_customer_id = stripe_billing.create_customer(body.company, body.email).get("id")
        except Exception:
            pass
    control.create_tenant(t)
    u = User(tenant_id=t.id, email=body.email, role="owner")
    control.create_user(u, tenancy.hash_password(body.password))
    token = tenancy.make_jwt({"tenant_id": t.id, "user_id": u.id,
                              "email": u.email, "role": u.role})
    return {"token": token, "tenant": t.model_dump()}


@app.post("/auth/login")
def auth_login(body: m.LoginIn):
    if not tenancy.MULTITENANT:
        raise HTTPException(status_code=400, detail="Multi-tenant mode is off")
    rec = control.get_user_by_email(body.email)
    if not rec or not tenancy.verify_password(body.password, rec[1]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    u = rec[0]
    t = control.get_tenant(u.tenant_id)
    token = tenancy.make_jwt({"tenant_id": u.tenant_id, "user_id": u.id,
                              "email": u.email, "role": u.role})
    return {"token": token, "tenant": t.model_dump() if t else None}


@app.get("/auth/me")
def auth_me(request: Request):
    cl = _claims(request)
    if not cl:
        raise HTTPException(status_code=401, detail="Unauthorized")
    t = control.get_tenant(cl["tenant_id"])
    return {"user": {"email": cl.get("email"), "role": cl.get("role")},
            "tenant": t.model_dump() if t else None}


@app.post("/auth/admin/login")
def admin_login(body: dict):
    """Single-admin login → returns a JWT the console sends as a Bearer token."""
    if not tenancy.ADMIN_AUTH:
        raise HTTPException(status_code=400, detail="Admin login is not enabled")
    if not tenancy.JWT_SECRET:
        raise HTTPException(status_code=500, detail="C2P_JWT_SECRET is not set on the server")
    user = (body or {}).get("user") or (body or {}).get("email") or ""
    pw = (body or {}).get("password") or ""
    if not tenancy.verify_admin(user, pw):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = tenancy.make_jwt({"role": "admin", "user": user})
    return {"token": token, "user": user}


@app.get("/auth/admin/me")
def admin_me(request: Request):
    """Reached only with a valid admin token (middleware enforces it) when admin
    auth is on — so a 200 here means the session is valid."""
    auth = request.headers.get("Authorization", "")
    claims = tenancy.read_jwt(auth[7:] if auth.startswith("Bearer ") else "")
    if not claims or claims.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"user": claims.get("user"), "role": "admin"}


@app.get("/tenant")
def get_tenant(request: Request):
    cl = _claims(request)
    if not cl:
        raise HTTPException(status_code=401, detail="Unauthorized")
    t = control.get_tenant(cl["tenant_id"])
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    usage = {"engagements": len(store.list()),
             "agent_runs": len(store.list_runs(limit=100000)),
             "pending_approvals": store.count_approvals("pending"),
             "leads": len(store.list_leads(limit=100000))}
    return {"tenant": t.model_dump(), "usage": usage}


@app.put("/tenant/config")
def put_tenant_config(request: Request, body: m.TenantConfigIn):
    cl = _claims(request)
    if not cl:
        raise HTTPException(status_code=401, detail="Unauthorized")
    t = control.get_tenant(cl["tenant_id"])
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if body.config:
        t.config = {**t.config, **body.config}
    control.update_tenant(t, secrets=body.secrets or None)
    return {"ok": True, "tenant": t.model_dump()}


@app.post("/billing/checkout")
def billing_checkout(request: Request, body: m.CheckoutIn):
    cl = _claims(request)
    if not cl:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not stripe_billing.configured():
        raise HTTPException(status_code=400, detail="Stripe not configured")
    price = stripe_billing.price_for(body.edition)
    if not price:
        raise HTTPException(status_code=400, detail=f"No Stripe price for {body.edition}")
    t = control.get_tenant(cl["tenant_id"])
    if not t.stripe_customer_id:
        t.stripe_customer_id = stripe_billing.create_customer(t.name, cl.get("email", "")).get("id")
        control.update_tenant(t)
    sess = stripe_billing.create_checkout_session(
        t.stripe_customer_id, price,
        body.success_url or "https://delivery.mumtaz.digital/?billing=success",
        body.cancel_url or "https://delivery.mumtaz.digital/?billing=cancel")
    return {"checkout_url": sess.get("url")}


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    raw = await request.body()
    event = stripe_billing.verify_webhook(raw, request.headers.get("Stripe-Signature", ""))
    if event is None:
        return JSONResponse({"detail": "invalid signature"}, status_code=400)
    etype = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}
    cust = obj.get("customer")
    if cust:
        t = control.get_tenant_by_customer(cust)
        if t:
            if etype in ("checkout.session.completed", "customer.subscription.created",
                         "customer.subscription.updated"):
                t.status = "active"
                sub = obj.get("subscription") or (obj.get("id") if etype != "checkout.session.completed" else None)
                if sub:
                    t.stripe_subscription_id = sub
                control.update_tenant(t)
            elif etype == "customer.subscription.deleted":
                t.status = "suspended"
                control.update_tenant(t)
            elif etype == "invoice.payment_failed":
                t.status = "past_due"
                control.update_tenant(t)
    return {"ok": True}


@app.get("/health")
def health():
    return {"ok": True, "model": MODEL, "stages": m.STAGES,
            "agents": list(PROMPTS.keys()), "web_search": llm.WEB_SEARCH_ENABLED,
            "multitenant": tenancy.MULTITENANT, "admin_auth": tenancy.ADMIN_AUTH,
            "stripe": stripe_billing.configured()}


@app.get("/odoo/standard-reference")
def odoo_standard_reference():
    """The full Odoo standard-functionality catalog the agents configure from."""
    return {"apps": odoo_standard.full_reference()}


@app.get("/config")
def public_config():
    """Public bootstrap flags the console reads before login."""
    return {"admin_auth": tenancy.ADMIN_AUTH, "multitenant": tenancy.MULTITENANT}
