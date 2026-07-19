"""Knowledge Hub — one browsable index over ALL built-in, no-API knowledge.

Every knowledge pack in the system (sales, pitch scripts, delivery workflows,
finance/tax, PM method, BA discovery, consulting frameworks, Odoo standards and
industry playbooks) is surfaced here as structured, browsable content. This is
the "hub" a consultant opens to find a script, a workflow, an objection response
or a framework without asking the model — everything is deterministic Python
data. `catalog()` lists the sections; `section(key)` returns one in full.

Each accessor is defensive: a missing or broken module degrades to an empty
section rather than breaking the hub.
"""
from __future__ import annotations


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default if default is not None else {}


# ── Section builders ────────────────────────────────────────────────────────
def _sales() -> dict:
    import sales_knowledge as sk
    return {
        "icp": sk.ICP,
        "qualification": [{"lens": q[0], "guidance": q[1]} for q in sk.QUALIFICATION],
        "discovery_call": sk.DISCOVERY_CALL,
        "objections": [{"objection": k, "response": v} for k, v in sk.OBJECTIONS.items()],
        "competitors": [{"competitor": k, "positioning": v} for k, v in sk.COMPETITORS.items()],
        "pricing": sk.PRICING,
        "outreach": sk.OUTREACH,
        "win_themes": sk.WIN_THEMES,
    }


def _pitch() -> dict:
    import pitch_library as pl
    return {
        "positioning": pl.POSITIONING,
        "value_pillars": [{"pillar": p[0], "detail": p[1]} for p in pl.VALUE_PILLARS],
        "proof_points": pl.PROOF_POINTS,
        "cold_emails": [{"kind": k, **v} for k, v in pl.COLD_EMAILS.items()],
        "linkedin": pl.LINKEDIN,
        "call_opener": pl.CALL_OPENER,
        "discovery_questions": pl.DISCOVERY_QUESTIONS,
        "demo_flow": pl.DEMO_FLOW,
        "followups": pl.followup_sequence(),
        "roi_tracks": [{"topic": k, "track": v} for k, v in pl.ROI_TRACKS.items()],
        "industry_pitch": [{"industry": k, **v} for k, v in pl.INDUSTRY_PITCH.items()],
        "closing": pl.CLOSING,
        "negotiation": pl.NEGOTIATION,
    }


def _workflows() -> dict:
    from consulting import workflow_engine as we, service_catalog as cat
    labels = {s: l for c in cat.SERVICE_CATALOG.values() for s, l in c.items()}
    out = []
    for key in we.SERVICE_WORKFLOW:
        wf = we.compose(key)
        out.append({
            "key": key,
            "label": labels.get(key, wf.get("label", key)),
            "step_count": wf.get("step_count", 0),
            "steps": [{"key": s.get("key"), "label": s.get("label"),
                       "gate": s.get("gate"), "done_when": s.get("done_when")}
                      for s in wf.get("steps", [])],
            "gates": wf.get("gates", []),
            "documents": wf.get("documents", []),
        })
    return {"workflows": out, "count": len(out)}


def _finance() -> dict:
    import finance_knowledge as fk
    return {
        "digest": _safe(fk.digest, ""),
        "indirect_tax": getattr(fk, "TAX_REGIMES", {}),
        "corporate_tax": getattr(fk, "CORPORATE_TAX", {}),
        "compliance": getattr(fk, "COMPLIANCE", []),
        "ifrs": [{"standard": e["std"], "topic": e["keys"][0],
                  "treatment": e["treatment"], "odoo": e["odoo"]}
                 for e in getattr(fk, "IFRS", [])],
        "processes": [{"topic": p["keys"][0], "odoo": p["odoo"], "fit": p["fit"]}
                      for p in getattr(fk, "PROCESSES", [])],
    }


def _pm() -> dict:
    import pm_knowledge as pk
    return {"digest": _safe(pk.digest, ""),
            "methodology": _safe(pk.methodology, "")}


def _ba() -> dict:
    import ba_knowledge as bak
    return {"digest": _safe(bak.digest, "")}


def _consulting() -> dict:
    import consulting_knowledge as con
    return {"digest": _safe(con.digest, ""),
            "frameworks": getattr(con, "FRAMEWORKS", []),
            "sop_sections": getattr(con, "SOP_SECTIONS", []),
            "kpi_trees": getattr(con, "KPI_TREES", {})}


def _tech() -> dict:
    import tech_knowledge as tk
    return {"digest": _safe(tk.digest, "")}


def _odoo() -> dict:
    import odoo_standard as os_
    return {
        "apps": _safe(os_.full_reference, []),
        "also": getattr(os_, "ALSO", {}),
        "app_count": len(getattr(os_, "STANDARD", {})),
    }


def _industry() -> dict:
    try:
        import industry as ind
        verticals = _safe(ind.list_industries, [])
        return {"verticals": verticals, "count": len(verticals)}
    except Exception:
        return {"verticals": [], "count": 0}


# ── Section registry ────────────────────────────────────────────────────────
_SECTIONS = {
    "sales": ("Sales & Marketing Playbook",
              "ICP, qualification, objection handling, competitor positioning, "
              "pricing and outreach.", _sales),
    "pitch": ("Sales Pitch Library",
              "Ready-to-use elevator pitches, cold emails, discovery questions, "
              "demo flow, follow-ups, ROI tracks and closing scripts.", _pitch),
    "workflows": ("Delivery Workflows",
                  "Composable, step-by-step delivery playbooks per service.", _workflows),
    "finance": ("Finance & Tax", "GCC/PK tax regimes, IFRS treatments and process maps.", _finance),
    "pm": ("Delivery Methodology", "Estimation, 7-phase method, risk and governance.", _pm),
    "ba": ("Business Analysis", "Per-area discovery frameworks: questions, data, pains, KPIs.", _ba),
    "consulting": ("Consulting Frameworks", "Strategy frameworks, SOP structure and KPI trees.", _consulting),
    "tech": ("Odoo Development Standards", "Module anatomy, ORM/security/performance rules.", _tech),
    "odoo": ("Odoo App Reference", "Per-app standard features, settings and the "
             "customisations that are really config / Studio.", _odoo),
    "industry": ("Industry Playbooks", "Per-vertical functional and go-to-market playbooks.", _industry),
}


def catalog() -> dict:
    """Section index with a live content count where cheap to compute."""
    sections = []
    for key, (title, summary, _fn) in _SECTIONS.items():
        sections.append({"key": key, "title": title, "summary": summary})
    return {"sections": sections, "count": len(sections)}


def section(key: str) -> dict:
    """Full content for one hub section (empty dict if unknown)."""
    entry = _SECTIONS.get(key)
    if not entry:
        return {}
    title, summary, fn = entry
    return {"key": key, "title": title, "summary": summary,
            "content": _safe(fn, {})}


def everything() -> dict:
    """The whole hub in one payload (for export / offline caching)."""
    return {"sections": [{"key": k, "title": t, "summary": s, "content": _safe(fn, {})}
                         for k, (t, s, fn) in _SECTIONS.items()]}
