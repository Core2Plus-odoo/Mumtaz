"""Phase 1 acceptance tests — accounts, client knowledge, the model-abstraction
layer (owned run log), and the knowledge loop. These mock the LLM, so they need
no API key or network. Run: `pip install -r requirements-dev.txt && pytest`.
"""
import os
import tempfile

import pytest

from models import Account, Approval, Engagement, KnowledgeEntry
from store import EngagementStore
from knowledge import KnowledgeService
import industry
import policy
import channels
import llm


# ── Phase 2: approval layer + autonomy policy + channels ──────────────────
def test_autonomy_policy_gates_sends(store):
    # Internal reasoning runs auto (no approval object).
    assert policy.gate(store, "research", {}, "research") is None
    assert policy.gate(store, "presales", {}, "presales") is None
    # Client-facing send is gated → a pending approval is created.
    appr = policy.gate(store, "outreach_send", {"to": "x"}, "outreach", account_id="acc1")
    assert appr is not None and appr.status == "pending"
    assert store.count_approvals("pending") == 1


def test_autonomy_override_via_settings(store):
    store.save_setting("autonomy", {"research": "approval"})
    appr = policy.gate(store, "research", {}, "research")
    assert appr is not None and appr.action_type == "research"


def test_approval_decide_round_trip(store):
    appr = policy.gate(store, "outreach_send",
                       {"channel": "email", "to": "ceo@acme.com",
                        "message": {"subject": "Hi", "body": "Hello"}},
                       "outreach", account_id="acc1")
    got = store.get_approval(appr.id)
    assert got.status == "pending"
    # Approve + execute path mirrors the endpoint logic.
    got.payload["message"]["body"] = "Edited hello"   # human correction captured
    got.status = "edited"
    store.update_approval(got)
    assert store.get_approval(appr.id).payload["message"]["body"] == "Edited hello"
    assert store.count_approvals("pending") == 0


def test_channels_dry_run_by_default():
    r = channels.send("email", "a@b.com", "Subject", "Body")
    assert r["mode"] == "dry-run" and r["sent"] is False
    assert channels.send("whatsapp", "+9715", "", "hi")["channel"] == "whatsapp"


# ── Industry playbook library ─────────────────────────────────────────────
def test_industry_matching():
    assert industry.match_industry("furniture manufacturer / cabinet maker") == "manufacturing"
    assert industry.match_industry("wholesale distribution") == "trading_distribution"
    assert industry.match_industry("chain of restaurants") == "food_beverage"
    assert industry.match_industry("MEP contracting") == "construction_contracting"
    assert industry.match_industry("") is None
    assert industry.match_industry("something unrelated zzz") is None


def test_industry_playbook_block_has_modules():
    block = industry.playbook_block("manufacturing")
    assert "INDUSTRY PLAYBOOK" in block and "mrp" in block
    assert industry.playbook_block(None) == ""
    assert len(industry.list_industries()) >= 10


@pytest.fixture()
def store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        yield EngagementStore(path=path)
    finally:
        os.remove(path)


# ── Accounts + knowledge store ────────────────────────────────────────────
def test_account_crud_and_partner_link(store):
    acc = store.create_account(Account(name="Gulf Closets", partner_id=42,
                                       industry="Manufacturing", country="UAE"))
    assert store.get_account(acc.id).name == "Gulf Closets"
    assert store.get_account_by_partner(42).id == acc.id
    assert any(a["id"] == acc.id for a in store.list_accounts())


def test_knowledge_add_list_and_keyword_search(store):
    acc = store.create_account(Account(name="Acme"))
    store.add_knowledge(KnowledgeEntry(account_id=acc.id, kind="requirement",
                                       title="Approval rule",
                                       content="Approval before any quotation above AED 50k"))
    store.add_knowledge(KnowledgeEntry(account_id=acc.id, kind="stakeholder",
                                       title="CFO", content="Finance lead drives the decision"))
    assert len(store.list_knowledge(acc.id)) == 2
    assert len(store.list_knowledge(acc.id, kind="requirement")) == 1
    hits = store.search_knowledge(acc.id, "quotation approval")
    assert hits and hits[0].kind == "requirement"
    # A term that matches nothing returns nothing.
    assert store.search_knowledge(acc.id, "zzznomatch") == []


def test_engagement_account_link_round_trips(store):
    acc = store.create_account(Account(name="Linked Co"))
    eng = store.create("Linked Co", odoo_db="DB1", account_id=acc.id)
    assert store.get(eng.id).account_id == acc.id
    listed = {e["id"]: e for e in store.list()}
    assert listed[eng.id]["account_id"] == acc.id


# ── Knowledge service (read-slice → context → write-back) ──────────────────
def test_knowledge_service_loop(store):
    ks = KnowledgeService(store)
    acc = store.create_account(Account(name="Loop Co"))
    assert ks.context_block(acc.id) == ""           # nothing known yet
    ks.write_entry(acc.id, "risk", "Legacy QuickBooks migration unclear",
                   title="Migration risk", learned_by="presales")
    block = ks.context_block(acc.id, "migration")
    assert "Migration risk" in block and "WHAT C2P ALREADY KNOWS" in block
    assert ks.read_slice(None) == []                 # no account → empty


# ── Model-abstraction layer logs every run as owned data ───────────────────
def test_run_json_parses_and_logs(store, monkeypatch):
    monkeypatch.setattr(llm, "_complete", lambda *a, **k: {
        "text": 'Here you go: {"recommendation": "pursue", "icp_fit": {"score": 80}}',
        "model": "test-model", "input_tokens": 11, "output_tokens": 22,
    })
    out = llm.run_json("presales", "sys", "user", store=store,
                       account_id="acc_x", engagement_id="eng_y")
    assert out["recommendation"] == "pursue"
    runs = store.list_runs()
    assert runs and runs[0]["task"] == "presales"
    assert runs[0]["model"] == "test-model" and runs[0]["error"] is None


def test_run_json_logs_errors_too(store, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("provider down")
    monkeypatch.setattr(llm, "_complete", boom)
    with pytest.raises(RuntimeError):
        llm.run_json("research", "sys", "user", store=store)
    runs = store.list_runs()
    assert runs and runs[0]["task"] == "research" and "provider down" in (runs[0]["error"] or "")


def test_model_routing_via_env(monkeypatch):
    monkeypatch.setenv("C2P_MODEL_DEVELOPER", "big-code-model")
    assert llm.model_for("developer") == "big-code-model"
    assert llm.model_for("presales") == llm.DEFAULT_MODEL


# ── Endpoint wiring (only if FastAPI is available) ─────────────────────────
def test_endpoints_account_research_knowledge(monkeypatch, tmp_path):
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    os.environ["C2P_STORE"] = str(tmp_path / "ep.db")
    import importlib
    import main as main_mod
    importlib.reload(main_mod)

    # Stub the agent so no model/network is touched.
    def fake_run_agent(stage, content, web_search=False, account_id=None, engagement_id=None):
        if stage == "research":
            return {"company_profile": {"name": "Stub Co", "industry": "Mfg"},
                    "pains": ["no shop-floor visibility"], "sources": ["stub"]}
        if stage == "prospect":
            return {"prospects": [{"name": "P1", "fit_score": 90}], "search_notes": "stub"}
        return {}
    monkeypatch.setattr(main_mod, "run_agent", fake_run_agent)

    c = TestClient(main_mod.app)
    acc = c.post("/accounts", json={"name": "Stub Co", "industry": "Mfg",
                                    "country": "UAE"}).json()
    assert acc["id"].startswith("acc_")

    r = c.post(f"/accounts/{acc['id']}/research", json={}).json()
    assert r["company_profile"]["name"] == "Stub Co"

    kn = c.get(f"/accounts/{acc['id']}/knowledge").json()
    assert any(e["kind"] == "research_dossier" for e in kn)

    pr = c.post("/prospect", json={"industry": "Manufacturing", "max_results": 3}).json()
    assert pr["prospects"][0]["fit_score"] == 90

    assert c.get("/health").json()["agents"][:2] == ["prospect", "research"]


def test_endpoints_outreach_and_approval_flow(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    os.environ["C2P_STORE"] = str(tmp_path / "ep2.db")
    import importlib
    import main as main_mod
    importlib.reload(main_mod)

    monkeypatch.setattr(main_mod, "run_agent", lambda *a, **k: {
        "channel": "email",
        "sequence": [{"step": 1, "when": "day 0", "subject": "Quick idea for Acme",
                      "body": "Hi — short note about an Odoo outcome.", "purpose": "open"}],
        "personalisation_notes": "stub",
    })

    c = TestClient(main_mod.app)
    acc = c.post("/accounts", json={"name": "Acme", "industry": "Manufacturing"}).json()

    # Drafting is auto; the send is gated → an approval appears.
    res = c.post(f"/accounts/{acc['id']}/outreach", json={"channel": "email"}).json()
    assert res["draft"]["sequence"][0]["subject"].startswith("Quick idea")
    assert res["approval"] and res["approval"]["status"] == "pending"
    apr_id = res["approval"]["id"]

    assert c.get("/approvals/count").json()["pending"] == 1
    queue = c.get("/approvals").json()
    assert any(a["id"] == apr_id for a in queue)

    # Approve → executes the send (dry-run) and clears the queue.
    decided = c.post(f"/approvals/{apr_id}/decide",
                     json={"decision": "approved", "decided_by": "owner"}).json()
    assert decided["status"] == "approved"
    assert decided["result"]["channel"] == "email"
    assert c.get("/approvals/count").json()["pending"] == 0

    # Deciding again is rejected.
    again = c.post(f"/approvals/{apr_id}/decide", json={"decision": "approved"})
    assert again.status_code == 400


# ── Phase 3: branded proposals ────────────────────────────────────────────
def test_proposal_render_in_brand():
    import proposal_render as pr

    class _S:
        def get_setting(self, k):
            return {}

    b = pr.brand(_S())
    html = pr.render_html(
        {"solution_summary": "Deploy Odoo MRP.",
         "commercial": {"estimate_aed": 184000, "pricing_model": "Fixed"}},
        "Acme Manufacturing", b, date_str="2026-06-29")
    assert "AED 184,000" in html and "Acme Manufacturing" in html and "C2P" in html


def test_proposal_send_is_gated(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    os.environ["C2P_STORE"] = str(tmp_path / "ep3.db")
    import importlib
    import main as main_mod
    importlib.reload(main_mod)
    c = TestClient(main_mod.app)

    eng = c.post("/engagements", json={"company": "Acme"}).json()
    e = main_mod.store.get(eng["id"])
    e.stages["proposal"] = {"solution_summary": "x", "commercial": {"estimate_aed": 1000}}
    main_mod.store.save(e)

    pv = c.get(f"/engagements/{eng['id']}/proposal/preview")
    assert pv.status_code == 200 and "Acme" in pv.text

    r = c.post(f"/engagements/{eng['id']}/proposal/send", json={}).json()
    assert r["approval"] and r["approval"]["action_type"] == "proposal_send"
    apr = r["approval"]["id"]
    dec = c.post(f"/approvals/{apr}/decide", json={"decision": "approved"}).json()
    assert dec["status"] == "approved" and dec["result"]["rendered"] is True
