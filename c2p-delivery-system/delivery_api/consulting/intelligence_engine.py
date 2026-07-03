"""Consulting OS Layer 3 — the INTELLIGENCE ENGINE.

Turns a consultant profile into an actionable blueprint: the workflows they
run (via workflow_engine), the union of agents those workflows activate, and
the document templates they produce. The blueprint is persisted per tenant in
app_settings so the runner and console can read it without recomputing, and is
regenerated whenever the profile changes. No LLM — this is deterministic
composition over the static catalog + step library.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import consultant_profile as cp
from . import workflow_engine as wf

_KEY = "consulting_blueprint"

# Human labels for the agent keys the workflows reference (run_agent tasks and
# "kb:" knowledge hooks). Used for the activation summary shown in the console.
AGENT_LABELS = {
    "presales": "Presales / Qualification",
    "ba_discovery": "Business Analyst — Discovery",
    "ba": "Business Analyst — Requirements",
    "proposal": "Proposal Writer",
    "project": "Project Planner",
    "functional": "Functional Consultant",
    "developer": "Developer",
    "config": "Configuration Architect",
    "docwriter": "Document Writer",
    "director": "Delivery Director (QA)",
    "research": "Research Analyst",
    "kb:pm_knowledge": "PM Estimator (knowledge)",
    "kb:pm_status": "PM Status Reporter (knowledge)",
    "kb:finance_knowledge": "Finance / CA Brain (knowledge)",
}


def _agent_set(workflows: list) -> list[dict]:
    """Union of agents across the workflows, with labels and where they run."""
    order, used_in = [], {}
    for w in workflows:
        for a in w.get("agents", []):
            if a not in used_in:
                used_in[a] = []
                order.append(a)
            if w["key"] not in used_in[a]:
                used_in[a].append(w["key"])
    return [{"key": a, "label": AGENT_LABELS.get(a, a), "workflows": used_in[a]}
            for a in order]


def build_blueprint(profile: dict) -> dict:
    """Compose the full blueprint from a profile (pure, no persistence)."""
    services = profile.get("services") or []
    workflows = wf.generate(services)
    agents = _agent_set(workflows)
    documents = []
    for w in workflows:
        for d in w.get("documents", []):
            if d not in documents:
                documents.append(d)
    gates = sorted({g for w in workflows for g in w.get("gates", [])})
    return {
        "workflows": workflows,
        "agents": agents,
        "documents": documents,
        "gates": gates,
        "counts": {"workflows": len(workflows), "agents": len(agents),
                   "documents": len(documents), "steps": sum(w["step_count"] for w in workflows)},
        "generated_at": None,
    }


def generate(store) -> dict:
    """Build the blueprint from the tenant's saved profile and persist it."""
    profile = cp.get_profile(store)
    bp = build_blueprint(profile)
    bp["generated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        store.save_setting(_KEY, bp)
    except Exception:
        pass
    return bp


def get_blueprint(store) -> dict:
    """Return the persisted blueprint, generating it once if none exists."""
    try:
        bp = store.get_setting(_KEY)
    except Exception:
        bp = None
    if not bp:
        return generate(store)
    return bp


def summary(store) -> dict:
    """Compact activation summary for the console / wizard completion screen."""
    bp = get_blueprint(store)
    return {
        "workflows": [{"key": w["key"], "label": w["label"],
                       "steps": w["step_count"], "builtin": w["builtin"]}
                      for w in bp["workflows"]],
        "agents": [a["label"] for a in bp["agents"]],
        "documents": bp["documents"],
        "gates": bp["gates"],
        "counts": bp["counts"],
        "generated_at": bp.get("generated_at"),
    }
