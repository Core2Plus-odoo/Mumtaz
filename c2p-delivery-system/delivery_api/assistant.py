"""A read-only business assistant over live Odoo and the delivery store.

The seventeen existing agents run as pipeline stages: presales → BA → proposal →
developer. None of them answers a question. This one does — "what is overdue and
who owns it", "which proposals have sat over a week", "did last night's agents
do anything" — grounded in real records rather than recall.

Read-only by construction, not by intention
-------------------------------------------
Every Odoo call goes through :func:`_read`, which refuses any method outside
:data:`READ_METHODS`. A tool added carelessly later cannot write to a
client-facing database, because the guard is in the path rather than in a
docstring asking nicely.

Two LLM calls, both with a local fallback
-----------------------------------------
1. **Plan** — pick one tool and its arguments for the question.
2. **Answer** — say what the returned rows mean.

With ``C2P_LLM_PROVIDER=none`` (or no key, or the provider down), a keyword
router picks the tool and a deterministic formatter writes the answer. The
figures are identical either way — they come from Odoo, not from the model. Only
the prose degrades.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta

import llm
import odoo as odoo_mod

_logger = logging.getLogger(__name__)

# The only Odoo methods this module may ever call. Anything that mutates a
# record — create, write, unlink, or an action_* button — is absent on purpose.
READ_METHODS = frozenset(
    {"search_read", "search_count", "read", "fields_get", "search"}
)

# Guards a careless question from pulling a whole database into a prompt.
MAX_ROWS = 50


class AssistantError(Exception):
    pass


def _db(store) -> str:
    """Which Odoo database to read. Stored connection first, environment second."""
    try:
        setting = store.get_setting("odoo_connection") or {}
    except Exception:
        setting = {}
    db = setting.get("db") or os.environ.get("ODOO_DB")
    if not db:
        raise AssistantError(
            "No Odoo database is configured. Set one under Settings → Odoo "
            "connection, or ODOO_DB in the environment."
        )
    return db


def _read(store, model: str, method: str, *args, **kw):
    """Every Odoo read the assistant makes goes through here."""
    if method not in READ_METHODS:
        # Not a ValueError to the user's face — this is a programming error in a
        # tool definition, and it should be loud in the log too.
        _logger.error("assistant: blocked non-read Odoo method %r on %s", method, model)
        raise AssistantError(
            "The assistant is read-only; %r is not a permitted method." % method
        )
    client = odoo_mod.get_client(_db(store))
    return client.execute(model, method, *args, **kw)


# ---------------------------------------------------------------------------
# Tools. Each returns a plain dict, and reports its own failure rather than
# raising, so one broken tool degrades the answer instead of the request.
# ---------------------------------------------------------------------------

def tool_pipeline_summary(store, **_):
    """Open opportunities by stage, with expected revenue."""
    rows = _read(
        store, "crm.lead", "search_read",
        [("type", "=", "opportunity"), ("active", "=", True),
         ("probability", "<", 100)],
        fields=["stage_id", "expected_revenue", "priority"], limit=2000,
    )
    by_stage = {}
    for row in rows:
        stage = (row.get("stage_id") or [0, "No stage"])[1]
        entry = by_stage.setdefault(stage, {"stage": stage, "count": 0, "revenue": 0.0})
        entry["count"] += 1
        entry["revenue"] += row.get("expected_revenue") or 0.0
    stages = sorted(by_stage.values(), key=lambda s: -s["revenue"])
    return {
        "open_opportunities": len(rows),
        "total_expected_revenue": round(sum(s["revenue"] for s in stages), 2),
        "by_stage": stages,
        "high_priority": sum(1 for r in rows if r.get("priority") in ("2", "3")),
    }


def tool_overdue_invoices(store, limit: int = 20, **_):
    """Posted customer invoices past their due date and not settled."""
    today = date.today().isoformat()
    rows = _read(
        store, "account.move", "search_read",
        [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
         ("payment_state", "in", ["not_paid", "partial"]),
         ("invoice_date_due", "<", today)],
        fields=["name", "partner_id", "invoice_date_due", "amount_residual",
                "currency_id", "invoice_user_id"],
        limit=min(int(limit or 20), MAX_ROWS),
        order="invoice_date_due asc",
    )
    for row in rows:
        due = row.get("invoice_date_due")
        row["days_overdue"] = (
            (date.today() - datetime.strptime(due, "%Y-%m-%d").date()).days
            if due else 0
        )
    return {
        "count": len(rows),
        "total_outstanding": round(sum(r.get("amount_residual") or 0 for r in rows), 2),
        "invoices": rows,
    }


def tool_search_leads(store, query: str = "", limit: int = 10, **_):
    """Find leads or opportunities by name, contact, company or email."""
    term = (query or "").strip()
    domain = [("active", "=", True)]
    if term:
        domain = ["&", ("active", "=", True),
                  "|", "|", "|",
                  ("name", "ilike", term), ("partner_name", "ilike", term),
                  ("contact_name", "ilike", term), ("email_from", "ilike", term)]
    rows = _read(
        store, "crm.lead", "search_read", domain,
        fields=["name", "partner_name", "contact_name", "email_from", "phone",
                "stage_id", "user_id", "priority", "expected_revenue",
                "date_last_stage_update"],
        limit=min(int(limit or 10), MAX_ROWS), order="write_date desc",
    )
    return {"count": len(rows), "leads": rows}


def tool_stale_proposals(store, days: int = 7, **_):
    """Opportunities parked in a proposal stage with nothing scheduled."""
    cutoff = (datetime.now() - timedelta(days=int(days or 7))).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    stages = _read(
        store, "crm.stage", "search_read",
        [("name", "in", ["Proposal Sent", "Proposal to be Send"])],
        fields=["name"], limit=20,
    )
    if not stages:
        return {"count": 0, "leads": [],
                "note": "No stage is named 'Proposal Sent' or 'Proposal to be "
                        "Send', so nothing could be selected."}
    rows = _read(
        store, "crm.lead", "search_read",
        [("active", "=", True), ("stage_id", "in", [s["id"] for s in stages]),
         ("date_last_stage_update", "<", cutoff), ("activity_ids", "=", False)],
        fields=["name", "partner_name", "stage_id", "user_id",
                "expected_revenue", "date_last_stage_update"],
        limit=MAX_ROWS, order="date_last_stage_update asc",
    )
    return {"count": len(rows), "days": int(days or 7), "leads": rows}


def tool_agent_health(store, **_):
    """Every scheduled action, and whether it has a body.

    Reads ir.cron, which a restricted Odoo user may not see — that returns a
    note rather than an error, because "I cannot see the crons" is a useful
    answer and a traceback is not.
    """
    try:
        rows = _read(
            store, "ir.cron", "search_read", [],
            fields=["name", "active", "lastcall", "nextcall", "code",
                    "interval_number", "interval_type"],
            limit=200, context={"active_test": False},
        )
    except Exception as exc:
        return {"error": "Could not read scheduled actions: %s" % exc,
                "hint": "The Odoo user the assistant connects as may lack "
                        "Settings access."}
    crons = []
    for row in rows:
        body = (row.pop("code", None) or "").strip()
        row["code_length"] = len(body)
        row["health"] = (
            "inactive" if not row.get("active")
            else "empty" if not body
            else "never_ran" if not row.get("lastcall")
            else "ok"
        )
        crons.append(row)
    empty = [c for c in crons if c["health"] == "empty"]
    return {
        "count": len(crons),
        "empty_code": [c["name"] for c in empty],
        "inactive": [c["name"] for c in crons if c["health"] == "inactive"],
        "crons": sorted(crons, key=lambda c: c["code_length"]),
    }


def tool_unassigned_leads(store, limit: int = 20, **_):
    """Open leads with no salesperson — nobody's problem."""
    rows = _read(
        store, "crm.lead", "search_read",
        [("active", "=", True), ("user_id", "=", False),
         ("probability", "<", 100)],
        fields=["name", "partner_name", "email_from", "create_date",
                "team_id", "expected_revenue"],
        limit=min(int(limit or 20), MAX_ROWS), order="create_date asc",
    )
    return {"count": len(rows), "leads": rows}


TOOLS = {
    "pipeline_summary": {
        "fn": tool_pipeline_summary,
        "args": {},
        "description": "Open opportunities by stage with expected revenue. Use "
                       "for 'how is the pipeline', 'what is in play', totals.",
    },
    "overdue_invoices": {
        "fn": tool_overdue_invoices,
        "args": {"limit": "int, default 20"},
        "description": "Posted customer invoices past due and unpaid, oldest "
                       "first, with days overdue and amount outstanding.",
    },
    "search_leads": {
        "fn": tool_search_leads,
        "args": {"query": "str, name/company/contact/email", "limit": "int"},
        "description": "Find specific leads or opportunities by any name or "
                       "address. Use when the question names a company or person.",
    },
    "stale_proposals": {
        "fn": tool_stale_proposals,
        "args": {"days": "int, default 7"},
        "description": "Opportunities sitting in a proposal stage with no next "
                       "action scheduled.",
    },
    "agent_health": {
        "fn": tool_agent_health,
        "args": {},
        "description": "Every scheduled action and whether it has a body. Use "
                       "for 'did the agents run', 'is anything broken'.",
    },
    "unassigned_leads": {
        "fn": tool_unassigned_leads,
        "args": {"limit": "int, default 20"},
        "description": "Open leads with no salesperson assigned.",
    },
}

# Keyword router for the local path. Ordered — first match wins, so the more
# specific phrases come before the general ones.
_ROUTES = (
    (("overdue", "unpaid", "owing", "receivable", "chase", "debtor"), "overdue_invoices"),
    (("proposal", "quote", "quotation"), "stale_proposals"),
    (("cron", "agent", "scheduled", "ran", "broken", "health"), "agent_health"),
    (("unassigned", "unowned", "no owner", "nobody"), "unassigned_leads"),
    (("pipeline", "forecast", "revenue", "stage", "how are we"), "pipeline_summary"),
)


def _route_locally(question: str) -> str:
    lowered = (question or "").lower()
    for keywords, tool in _ROUTES:
        if any(keyword in lowered for keyword in keywords):
            return tool
    # A question naming something specific is usually about one record.
    return "search_leads" if lowered.strip() else "pipeline_summary"


def _plan(question: str) -> tuple[str, dict, bool]:
    """Choose a tool. Returns (tool, args, used_llm)."""
    catalog = "\n".join(
        "- %s(%s): %s" % (name, ", ".join(spec["args"]) or "no arguments",
                          spec["description"])
        for name, spec in TOOLS.items()
    )
    system = (
        "You route a question to exactly one read-only tool over a live Odoo "
        "CRM. Available tools:\n" + catalog + "\n\n"
        "Return JSON: {\"tool\": \"<name>\", \"args\": {...}}. Use only the "
        "listed tool names. Prefer the most specific tool. If the question "
        "names a company or person, use search_leads with that as the query."
    )
    try:
        out = llm.run_json("assistant_plan", system, question, max_tokens=300)
        tool = (out or {}).get("tool")
        if tool in TOOLS:
            args = (out or {}).get("args") or {}
            return tool, (args if isinstance(args, dict) else {}), True
        _logger.info("assistant: planner returned unusable tool %r", tool)
    except Exception as exc:
        _logger.info("assistant: planner unavailable (%s), routing locally", exc)
    return _route_locally(question), _local_args(question), False


def _local_args(question: str) -> dict:
    """Best-effort arguments without a model: the question is the search term."""
    return {"query": (question or "").strip()}


def _describe_locally(tool: str, data: dict) -> str:
    """Deterministic prose for the no-LLM path. Plain, and never invented."""
    if data.get("error"):
        return data["error"]
    if tool == "pipeline_summary":
        lines = ["%s open opportunities, %s expected in total."
                 % (data["open_opportunities"], data["total_expected_revenue"])]
        for stage in data["by_stage"][:8]:
            lines.append("  %s — %s opportunities, %s"
                         % (stage["stage"], stage["count"], round(stage["revenue"], 2)))
        lines.append("%s are high priority." % data["high_priority"])
        return "\n".join(lines)
    if tool == "overdue_invoices":
        if not data["count"]:
            return "Nothing overdue."
        lines = ["%s overdue invoices, %s outstanding."
                 % (data["count"], data["total_outstanding"])]
        for inv in data["invoices"][:10]:
            lines.append("  %s — %s days overdue, %s (%s)"
                         % (inv.get("name"), inv.get("days_overdue"),
                            inv.get("amount_residual"),
                            (inv.get("partner_id") or [0, "?"])[1]))
        return "\n".join(lines)
    if tool == "stale_proposals":
        if data.get("note"):
            return data["note"]
        if not data["count"]:
            return "No proposals have been sitting more than %s days." % data["days"]
        lines = ["%s proposals with no next action:" % data["count"]]
        for lead in data["leads"][:10]:
            lines.append("  %s — %s, last moved %s"
                         % (lead.get("name"), (lead.get("stage_id") or [0, "?"])[1],
                            lead.get("date_last_stage_update")))
        return "\n".join(lines)
    if tool == "agent_health":
        parts = ["%s scheduled actions." % data["count"]]
        if data["empty_code"]:
            parts.append("EMPTY BODY: " + ", ".join(data["empty_code"]))
        if data["inactive"]:
            parts.append("Inactive: " + ", ".join(data["inactive"][:10]))
        return "\n".join(parts)
    if tool == "unassigned_leads":
        if not data["count"]:
            return "Every open lead has an owner."
        lines = ["%s leads with no salesperson:" % data["count"]]
        for lead in data["leads"][:10]:
            lines.append("  %s (%s), created %s"
                         % (lead.get("name"), lead.get("partner_name") or "—",
                            lead.get("create_date")))
        return "\n".join(lines)
    if tool == "search_leads":
        if not data["count"]:
            return "Nothing matched."
        lines = ["%s matches:" % data["count"]]
        for lead in data["leads"][:10]:
            lines.append("  %s — %s, %s"
                         % (lead.get("name"), (lead.get("stage_id") or [0, "?"])[1],
                            (lead.get("user_id") or [0, "unassigned"])[1]))
        return "\n".join(lines)
    return "No summary available for %s." % tool


def _answer(question: str, tool: str, data: dict) -> tuple[str, bool]:
    """Turn rows into prose. Returns (answer, used_llm)."""
    system = (
        "You answer a question about a consultancy's own CRM using ONLY the "
        "JSON provided. Never invent a figure, a name or a date that is not in "
        "it. If the data does not answer the question, say so plainly. Be "
        "direct and short — this is an operator checking their own business, "
        "not a report. Return JSON: {\"answer\": \"...\"}."
    )
    user = "Question: %s\n\nTool: %s\n\nData:\n%s" % (question, tool, data)
    try:
        out = llm.run_json("assistant_answer", system, user, max_tokens=900)
        answer = (out or {}).get("answer")
        if answer:
            return str(answer), True
    except Exception as exc:
        _logger.info("assistant: answerer unavailable (%s), formatting locally", exc)
    return _describe_locally(tool, data), False


def ask(store, question: str) -> dict:
    """Answer one question. Read-only, always returns the data behind the answer."""
    question = (question or "").strip()
    if not question:
        raise AssistantError("Ask something.")

    tool, args, planned_by_llm = _plan(question)
    spec = TOOLS[tool]
    try:
        data = spec["fn"](store, **args)
    except AssistantError:
        raise
    except TypeError:
        # The planner offered arguments this tool does not take.
        data = spec["fn"](store)
    except Exception as exc:
        _logger.warning("assistant: tool %s failed: %s", tool, exc)
        data = {"error": "Could not read that from Odoo: %s" % exc}

    answer, answered_by_llm = _answer(question, tool, data)
    used_llm = planned_by_llm or answered_by_llm
    if not used_llm:
        llm.log_local(store, "assistant", {"tool": tool, "path": "local"})
    return {
        "question": question,
        "tool": tool,
        "args": args,
        "answer": answer,
        "data": data,
        # So the console can say "this came from a model" or "this is the
        # offline path" rather than leaving the reader to guess.
        "llm": used_llm,
    }


def tools_catalog() -> list[dict]:
    """What the assistant can look at — for the console's empty state."""
    return [
        {"name": name, "description": spec["description"],
         "args": list(spec["args"])}
        for name, spec in TOOLS.items()
    ]
