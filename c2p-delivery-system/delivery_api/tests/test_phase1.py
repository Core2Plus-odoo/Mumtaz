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


# ── Phase 4: gated deploy ─────────────────────────────────────────────────
def test_deploy_module_staged_and_traversal_safe():
    import deploy as dep
    out = {"module_technical_name": "c2p_quote_approval", "files": [
        {"path": "__manifest__.py", "content": "{}"},
        {"path": "models/m.py", "content": "# x"},
        {"path": "../evil.py", "content": "x"}]}  # escape attempt
    r = dep.deploy_module(out)
    assert r["mode"] == "staged" and r["files"] == 2 and r["pushed"] is False
    assert "../evil.py" in r["skipped"]


def test_deploy_is_gated(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    os.environ["C2P_STORE"] = str(tmp_path / "ep4.db")
    import importlib
    import main as main_mod
    importlib.reload(main_mod)
    c = TestClient(main_mod.app)

    eng = c.post("/engagements", json={"company": "Acme"}).json()
    e = main_mod.store.get(eng["id"])
    e.stages["developer"] = {"module_technical_name": "c2p_demo",
                             "files": [{"path": "__manifest__.py", "content": "{}"}]}
    main_mod.store.save(e)

    r = c.post(f"/engagements/{eng['id']}/deploy", json={}).json()
    assert r["approval"] and r["approval"]["action_type"] == "code_deploy"
    dec = c.post(f"/approvals/{r['approval']['id']}/decide",
                 json={"decision": "approved"}).json()
    assert dec["status"] == "approved" and dec["result"]["module"] == "c2p_demo"


# ── Implementation: config-apply (gated) ──────────────────────────────────
def test_config_apply_is_gated(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    os.environ["C2P_STORE"] = str(tmp_path / "cfg.db")
    import importlib
    import main as main_mod
    importlib.reload(main_mod)

    # Stub the config agent + the Odoo client so no real Odoo is touched.
    monkeypatch.setattr(main_mod, "run_agent", lambda *a, **k: {
        "summary": "Baseline UAE setup",
        "operations": [{"label": "VAT 5%", "model": "account.tax", "method": "create",
                        "values": {"name": "VAT 5%", "amount": 5.0}}],
        "manual_steps": [], "risks": []})

    class _FakeOdoo:
        def execute(self, model, method, *a, **k):
            return 101 if method == "create" else True
        def message_post(self, *a, **k):
            return True
    monkeypatch.setattr(main_mod, "get_client", lambda db: _FakeOdoo())

    c = TestClient(main_mod.app)
    eng = c.post("/engagements", json={"company": "Acme", "odoo_db": "Acme_DB"}).json()

    r = c.post(f"/engagements/{eng['id']}/config", json={}).json()
    assert r["approval"] and r["approval"]["action_type"] == "config_apply"
    assert len(r["recipe"]["operations"]) == 1

    dec = c.post(f"/approvals/{r['approval']['id']}/decide",
                 json={"decision": "approved"}).json()
    assert dec["status"] == "approved"
    assert dec["result"]["applied"] == 1 and dec["result"]["results"][0]["id"] == 101


# ── Phase 5: communications (triage + sensitivity gating) ─────────────────
def test_comms_inbound_routes_and_gates(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    os.environ["C2P_STORE"] = str(tmp_path / "ep5.db")
    import importlib
    import main as main_mod
    importlib.reload(main_mod)

    # Routine status question → auto; scope/pricing → approval. Stub by intent.
    def fake(stage, content, **k):
        sensitive = "price" in content.lower() or "scope" in content.lower()
        return {"intent": "pricing" if sensitive else "status_request",
                "sensitivity": "approval" if sensitive else "auto",
                "matched_company": "Acme",
                "summary": "stub", "internal_note": "",
                "suggested_reply": {"subject": "Re", "body": "Thanks — here's an update."}}
    monkeypatch.setattr(main_mod, "run_agent", fake)

    c = TestClient(main_mod.app)
    c.post("/accounts", json={"name": "Acme"})  # so matched_company routes

    routine = c.post("/comms/inbound", json={"from_party": "x@acme.com",
              "subject": "status?", "body": "Any update on go-live timing?"}).json()
    assert routine.get("sent") and routine["account_id"]  # auto-sent + routed to Acme

    sensitive = c.post("/comms/inbound", json={"from_party": "x@acme.com",
              "subject": "pricing", "body": "Can you change the scope and price?"}).json()
    assert sensitive["approval"] and sensitive["approval"]["action_type"] == "client_comms_sensitive"

    assert len(c.get("/comms").json()) >= 3  # 2 inbound + at least 1 outbound logged


# ── Phase 6: cockpit metrics + supervisor briefing ────────────────────────
def test_metrics_and_supervisor(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    os.environ["C2P_STORE"] = str(tmp_path / "ep6.db")
    import importlib
    import main as main_mod
    importlib.reload(main_mod)
    c = TestClient(main_mod.app)

    eng = c.post("/engagements", json={"company": "Acme"}).json()
    e = main_mod.store.get(eng["id"])
    e.stages["proposal"] = {"commercial": {"estimate_aed": 150000}}
    e.stages["project"] = {"project_name": "Acme rollout"}
    main_mod.store.save(e)

    mx = c.get("/metrics").json()
    assert mx["pipeline_value_aed"] == 150000 and mx["engagements"] == 1
    assert mx["with_proposal"] == 1 and mx["win_rate"] == 100
    assert mx["by_stage"]["proposal"] == 1 and mx["by_stage"]["project"] == 1

    monkeypatch.setattr(main_mod, "run_agent", lambda *a, **k: {
        "headline": "1 proposal awaiting send", "priorities": [], "risks": []})
    br = c.post("/supervisor/brief").json()
    assert br["briefing"]["headline"] and br["metrics"]["pipeline_value_aed"] == 150000


# ── Leads CRM ─────────────────────────────────────────────────────────────
def test_leads_crud_bulk_and_convert(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    os.environ["C2P_STORE"] = str(tmp_path / "leads.db")
    import importlib
    import main as main_mod
    importlib.reload(main_mod)
    c = TestClient(main_mod.app)

    # bulk from prospector-shaped data
    c.post("/leads/bulk", json={"prospects": [
        {"name": "Acme Mfg", "industry": "Manufacturing", "fit_score": 88, "signals": ["growth"]},
        {"name": "Beta Trading", "industry": "Distribution", "fit_score": 71}]})
    leads = c.get("/leads").json()
    assert len(leads) == 2 and leads[0]["source"] == "prospector"

    lid = leads[0]["id"]
    c.post(f"/leads/{lid}/update", json={"status": "qualified", "notes": "warm"})
    assert c.get(f"/leads/{lid}").json()["status"] == "qualified"

    conv = c.post(f"/leads/{lid}/convert", json={}).json()
    assert conv["account"]["name"] == "Acme Mfg"
    assert c.get(f"/leads/{lid}").json()["status"] == "converted"
    assert any(a["name"] == "Acme Mfg" for a in c.get("/accounts").json())


# ── Phase 7: multi-tenant control plane ───────────────────────────────────
def test_password_and_jwt(monkeypatch):
    import tenancy as tn
    h = tn.hash_password("s3cret")
    assert tn.verify_password("s3cret", h) and not tn.verify_password("nope", h)
    monkeypatch.setattr(tn, "JWT_SECRET", "testsecret")
    tok = tn.make_jwt({"tenant_id": "t1", "email": "a@b.com"})
    cl = tn.read_jwt(tok)
    assert cl["tenant_id"] == "t1" and cl["email"] == "a@b.com"
    assert tn.read_jwt("garbage") is None


def test_control_store_and_per_tenant_isolation(tmp_path, monkeypatch):
    import tenancy as tn
    from models import Account, Tenant, User
    ctrl = tn.ControlStore(path=str(tmp_path / "control.db"))
    t = Tenant(name="Acme Agency", slug="acme")
    ctrl.create_tenant(t)
    ctrl.create_user(User(tenant_id=t.id, email="o@acme.com"), tn.hash_password("pw"))
    assert ctrl.get_tenant_by_slug("acme").id == t.id
    rec = ctrl.get_user_by_email("o@acme.com")
    assert rec and tn.verify_password("pw", rec[1])
    ctrl.update_tenant(t, secrets={"anthropic_key": "sk-xyz"})
    assert ctrl.get_secrets(t.id)["anthropic_key"] == "sk-xyz"   # enc/dec round-trip

    monkeypatch.setattr(tn, "TENANT_DIR", str(tmp_path / "tenants"))
    tn._tenant_stores.clear()
    s1, s2 = tn.tenant_store("ten_1"), tn.tenant_store("ten_2")
    s1.create_account(Account(name="A1"))
    assert len(s1.list_accounts()) == 1 and len(s2.list_accounts()) == 0  # isolated


def test_store_proxy_routes(tmp_path):
    import tenancy as tn
    from store import EngagementStore
    from models import Account
    proxy = tn.StoreProxy(EngagementStore(path=str(tmp_path / "def.db")))
    proxy.create_account(Account(name="Default Co"))
    assert len(proxy.list_accounts()) == 1
    other = EngagementStore(path=str(tmp_path / "other.db"))
    tn.set_current_store(other)
    try:
        assert len(proxy.list_accounts()) == 0          # routes to current tenant
        proxy.create_account(Account(name="Tenant Co"))
        assert len(proxy.list_accounts()) == 1
    finally:
        tn.reset_current_store()
    assert len(proxy.list_accounts()) == 1              # back to default


def test_multitenant_signup_login_isolation(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    import tenancy as tn
    from store import EngagementStore
    import main as main_mod

    monkeypatch.setattr(tn, "MULTITENANT", True)
    monkeypatch.setattr(tn, "JWT_SECRET", "tsecret")
    monkeypatch.setattr(tn, "TENANT_DIR", str(tmp_path / "tenants"))
    tn._tenant_stores.clear()
    monkeypatch.setattr(main_mod, "control", tn.ControlStore(path=str(tmp_path / "control.db")))
    proxy = tn.StoreProxy(EngagementStore(path=str(tmp_path / "default.db")))
    monkeypatch.setattr(main_mod, "store", proxy)
    main_mod.ks.store = proxy

    c = TestClient(main_mod.app)
    assert c.get("/health").json()["multitenant"] is True
    assert c.get("/leads").status_code == 401                      # gated

    s = c.post("/auth/signup", json={"company": "Acme Agency", "email": "o@acme.com",
                                     "password": "pw", "edition": "agency"}).json()
    H = {"Authorization": "Bearer " + s["token"]}
    c.post("/leads", json={"name": "Lead A"}, headers=H)
    assert len(c.get("/leads", headers=H).json()) == 1

    s2 = c.post("/auth/signup", json={"company": "Beta Agency", "email": "o@beta.com",
                                      "password": "pw"}).json()
    H2 = {"Authorization": "Bearer " + s2["token"]}
    assert len(c.get("/leads", headers=H2).json()) == 0            # tenant-isolated

    assert c.post("/auth/login", json={"email": "o@acme.com", "password": "pw"}).status_code == 200
    assert c.get("/auth/me", headers=H).json()["user"]["email"] == "o@acme.com"
