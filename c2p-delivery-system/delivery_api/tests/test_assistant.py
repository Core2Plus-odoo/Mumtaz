"""Assistant tests — the read-only guard, the tools, and the no-LLM fallback.

Odoo is stubbed, so these need no server and no API key. The point of most of
them is that the figures come from the rows, never from a model: with the LLM
path disabled entirely, the answers must still be correct.
"""
import pytest

import assistant
import llm


class FakeOdooClient:
    """Records every call so a test can assert what was asked of Odoo."""

    def __init__(self, responses=None):
        self.calls = []
        self.responses = responses or {}

    def execute(self, model, method, *args, **kw):
        self.calls.append((model, method, args, kw))
        return self.responses.get((model, method), [])


@pytest.fixture
def fake_odoo(monkeypatch):
    client = FakeOdooClient()
    monkeypatch.setattr(assistant.odoo_mod, "get_client", lambda db: client)
    return client


@pytest.fixture
def no_llm(monkeypatch):
    """Force the local path: the planner and answerer both fail."""
    def boom(*a, **kw):
        raise RuntimeError("no provider configured")
    monkeypatch.setattr(llm, "run_json", boom)
    monkeypatch.setattr(assistant.llm, "run_json", boom)


class FakeStore:
    def __init__(self, db="Mumtaz_C2P"):
        self._db = db
        self.runs = []

    def get_setting(self, key):
        return {"db": self._db} if key == "odoo_connection" else {}

    def log_run(self, row):
        self.runs.append(row)


# ── the read-only guard ───────────────────────────────────────────────────
def test_write_methods_are_refused(fake_odoo):
    """The guard is in the path, so a careless tool cannot write."""
    for method in ("write", "create", "unlink", "action_post"):
        with pytest.raises(assistant.AssistantError):
            assistant._read(FakeStore(), "crm.lead", method, [])
    assert fake_odoo.calls == [], "nothing should have reached Odoo"


def test_read_methods_are_allowed(fake_odoo):
    assistant._read(FakeStore(), "crm.lead", "search_read", [], fields=["name"])
    assert fake_odoo.calls[0][1] == "search_read"


def test_missing_database_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("ODOO_DB", raising=False)

    class NoDb(FakeStore):
        def get_setting(self, key):
            return {}

    with pytest.raises(assistant.AssistantError) as exc:
        assistant._read(NoDb(), "crm.lead", "search_read", [])
    assert "No Odoo database is configured" in str(exc.value)


# ── tools ─────────────────────────────────────────────────────────────────
def test_pipeline_summary_aggregates_by_stage(fake_odoo):
    fake_odoo.responses[("crm.lead", "search_read")] = [
        {"stage_id": [1, "Qualified"], "expected_revenue": 10000, "priority": "3"},
        {"stage_id": [1, "Qualified"], "expected_revenue": 5000, "priority": "1"},
        {"stage_id": [2, "Proposal Sent"], "expected_revenue": 40000, "priority": "2"},
    ]
    out = assistant.tool_pipeline_summary(FakeStore())

    assert out["open_opportunities"] == 3
    assert out["total_expected_revenue"] == 55000
    assert out["high_priority"] == 2
    # Sorted by revenue, so the biggest stage leads.
    assert out["by_stage"][0]["stage"] == "Proposal Sent"
    assert out["by_stage"][1]["count"] == 2


def test_pipeline_summary_handles_a_lead_with_no_stage(fake_odoo):
    fake_odoo.responses[("crm.lead", "search_read")] = [
        {"stage_id": False, "expected_revenue": 100, "priority": "0"},
    ]
    out = assistant.tool_pipeline_summary(FakeStore())
    assert out["by_stage"][0]["stage"] == "No stage"


def test_overdue_invoices_computes_days_overdue(fake_odoo):
    from datetime import date, timedelta
    due = (date.today() - timedelta(days=12)).isoformat()
    fake_odoo.responses[("account.move", "search_read")] = [
        {"name": "INV/001", "invoice_date_due": due, "amount_residual": 5000.0,
         "partner_id": [1, "Acme"], "currency_id": [1, "AED"],
         "invoice_user_id": [2, "Rep"]},
    ]
    out = assistant.tool_overdue_invoices(FakeStore())

    assert out["count"] == 1
    assert out["invoices"][0]["days_overdue"] == 12
    assert out["total_outstanding"] == 5000.0


def test_agent_health_flags_an_empty_body(fake_odoo):
    fake_odoo.responses[("ir.cron", "search_read")] = [
        {"name": "Silently empty", "active": True, "lastcall": "2026-08-10",
         "nextcall": "2026-08-11", "code": "   "},
        {"name": "Working", "active": True, "lastcall": "2026-08-10",
         "nextcall": "2026-08-11", "code": "model.do_something()"},
        {"name": "Switched off", "active": False, "lastcall": False,
         "nextcall": "2026-08-11", "code": "model.x()"},
    ]
    out = assistant.tool_agent_health(FakeStore())

    assert out["empty_code"] == ["Silently empty"]
    assert out["inactive"] == ["Switched off"]
    # The code body itself is never returned — only its length.
    assert all("code" not in cron for cron in out["crons"])


def test_agent_health_degrades_when_the_user_cannot_read_crons(monkeypatch):
    def denied(*a, **kw):
        raise Exception("Access Denied")
    monkeypatch.setattr(assistant, "_read", denied)

    out = assistant.tool_agent_health(FakeStore())

    assert "Could not read scheduled actions" in out["error"]
    assert "Settings access" in out["hint"]


def test_stale_proposals_says_so_when_no_stage_matches(fake_odoo):
    fake_odoo.responses[("crm.stage", "search_read")] = []
    out = assistant.tool_stale_proposals(FakeStore())
    assert out["count"] == 0
    assert "No stage is named" in out["note"]


def test_row_limits_are_capped(fake_odoo):
    """A careless question cannot pull the whole database into a prompt."""
    assistant.tool_overdue_invoices(FakeStore(), limit=100000)
    _, _, _, kw = fake_odoo.calls[0]
    assert kw["limit"] == assistant.MAX_ROWS


def test_odoo_is_called_the_way_execute_kw_expects(fake_odoo):
    """The domain is ONE positional; options are keywords.

    OdooClient.execute forwards *args as execute_kw's positional list and **kw
    as its options dict. Passing the options positionally instead — as this
    module first did — sends Odoo a second positional argument it cannot use.
    """
    assistant.tool_pipeline_summary(FakeStore())
    model, method, args, kw = fake_odoo.calls[0]

    assert model == "crm.lead" and method == "search_read"
    assert len(args) == 1, "the domain must be the only positional argument"
    assert isinstance(args[0], list) and isinstance(args[0][0], tuple)
    assert "fields" in kw and "limit" in kw


# ── the local, no-model path ──────────────────────────────────────────────
@pytest.mark.parametrize("question,expected", [
    ("what is overdue?", "overdue_invoices"),
    ("any unpaid invoices", "overdue_invoices"),
    ("which proposals are stuck", "stale_proposals"),
    ("did the agents run last night", "agent_health"),
    ("show me unassigned leads", "unassigned_leads"),
    ("how is the pipeline", "pipeline_summary"),
    ("Acme Trading LLC", "search_leads"),
])
def test_local_router_picks_a_sensible_tool(question, expected):
    assert assistant._route_locally(question) == expected


def test_ask_works_with_no_model_at_all(fake_odoo, no_llm):
    from datetime import date, timedelta
    due = (date.today() - timedelta(days=30)).isoformat()
    fake_odoo.responses[("account.move", "search_read")] = [
        {"name": "INV/007", "invoice_date_due": due, "amount_residual": 9000.0,
         "partner_id": [1, "Acme"], "currency_id": [1, "AED"],
         "invoice_user_id": [2, "Rep"]},
    ]
    store = FakeStore()

    out = assistant.ask(store, "what is overdue?")

    assert out["tool"] == "overdue_invoices"
    assert out["llm"] is False, "this is the offline path"
    # The figures come from the rows either way — only the prose degrades.
    assert "INV/007" in out["answer"]
    assert "30 days overdue" in out["answer"]
    assert out["data"]["total_outstanding"] == 9000.0
    assert store.runs and store.runs[0]["task"] == "assistant"


def test_ask_reports_nothing_overdue_plainly(fake_odoo, no_llm):
    fake_odoo.responses[("account.move", "search_read")] = []
    out = assistant.ask(FakeStore(), "anything overdue?")
    assert out["answer"] == "Nothing overdue."


def test_ask_rejects_an_empty_question():
    with pytest.raises(assistant.AssistantError):
        assistant.ask(FakeStore(), "   ")


def test_a_failing_tool_becomes_an_answer_not_a_traceback(monkeypatch, no_llm):
    def boom(*a, **kw):
        raise Exception("XML-RPC connection refused")
    monkeypatch.setitem(assistant.TOOLS["pipeline_summary"], "fn", boom)

    out = assistant.ask(FakeStore(), "how is the pipeline")

    assert "Could not read that from Odoo" in out["answer"]


def test_tools_catalog_describes_every_tool():
    catalog = assistant.tools_catalog()
    assert {t["name"] for t in catalog} == set(assistant.TOOLS)
    assert all(t["description"] for t in catalog)
