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
import llm
import policy
import channels
import proposal_render
import deploy as deployer
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
    if not tenancy.MULTITENANT:
        return await call_next(request)
    path = request.url.path
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
        + industry.playbook_block(_industry_for(eng))
        + ks.context_block(eng.account_id, "proposal scope modules")
    )
    out = run_agent("proposal", content, account_id=eng.account_id, engagement_id=eng.id)
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
    )
    out = run_agent("project", content, account_id=eng.account_id, engagement_id=eng.id)
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
        + industry.playbook_block(body.industry or _industry_for(eng))
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
        raise HTTPException(status_code=502, detail=f"Odoo error: {exc}")


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
        raise HTTPException(status_code=502, detail=f"Odoo error: {exc}")
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
    out = run_agent("config", content, account_id=eng.account_id, engagement_id=eng.id)
    payload = {"engagement_id": eng.id, "operations": out.get("operations") or [],
               "summary": out.get("summary")}
    appr = policy.gate(store, "config_apply", payload, requester_agent="config",
                       account_id=eng.account_id, engagement_id=eng.id)
    if appr is None:
        return {"recipe": out, "approval": None,
                "result": _execute_config_apply(payload, eng.account_id)}
    return {"recipe": out, "approval": appr.model_dump()}


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
    out = run_agent("pm", content, account_id=eng.account_id, engagement_id=eng.id)
    return {"report": out, "scope": scope}


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
        raise HTTPException(status_code=502, detail=f"Odoo error: {exc}")


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
        raise HTTPException(status_code=502, detail=f"Odoo error: {exc}")
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
        raise HTTPException(status_code=502, detail=f"Odoo error: {exc}")
    return {"ok": True}


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
            "multitenant": tenancy.MULTITENANT, "stripe": stripe_billing.configured()}
