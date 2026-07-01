"""Built-in document templating — assemble client deliverables from structured
engagement data with NO API call.

When the model is available the docwriter agent produces the most polished prose;
but every deliverable can also be assembled deterministically from what the
pipeline already holds (the BA requirements catalog, the PM estimate, the
functional analyses, the proposal). This makes document generation work offline
and removes the last hard API dependency from a full Autopilot run.

`build(doc_key, eng)` returns the same shape the docwriter agent returns, so the
branded renderer is identical.
"""
from __future__ import annotations

from typing import Any

import pm_knowledge

DOC_TITLES = {
    "brd": "Business Requirements Document",
    "frs": "Functional Specification Document",
    "gapfit": "Gap-Fit Analysis",
    "charter": "Project Charter",
    "status": "Project Status Report",
    "techdesign": "Technical Design Document",
    "sow": "Statement of Work",
}

_VERDICT_LABEL = {"standard": "Standard configuration", "configurable": "Configurable (no code)",
                  "studio": "Odoo Studio", "custom": "Custom development"}


def _aed(n) -> str:
    try:
        return "AED " + f"{float(n):,.0f}"
    except Exception:
        return f"AED {n}"


def _table(headers: list, rows: list) -> str:
    h = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(str(c) for c in r) + " |" for r in rows)
    return f"{h}\n{sep}\n{body}" if rows else "_None recorded._"


def _ba(eng) -> dict:
    return eng.stages.get("ba_requirements") or {}


def _frs_rows(eng) -> list:
    reqs = _ba(eng).get("functional_requirements") or []
    rows = []
    for r in reqs:
        rows.append([r.get("id", ""), (r.get("requirement", "") or "")[:90],
                     r.get("area", ""), r.get("priority", ""),
                     _VERDICT_LABEL.get(r.get("odoo_fit", ""), r.get("odoo_fit", "")),
                     r.get("module_hint", "")])
    return rows


def _sections_brd(eng) -> list:
    ba = _ba(eng)
    reqs = ba.get("functional_requirements") or []
    by_area: dict[str, list] = {}
    for r in reqs:
        by_area.setdefault(r.get("area") or "General", []).append(r)
    scope = "\n".join(f"- **{a}** — {len(v)} requirement(s)" for a, v in by_area.items()) or "_TBD_"
    reqtbl = _table(["ID", "Requirement", "Area", "Priority"],
                    [[r.get("id", ""), (r.get("requirement", "") or "")[:100],
                      r.get("area", ""), r.get("priority", "")] for r in reqs])
    procs = ba.get("process_maps") or []
    proc_md = "\n\n".join(f"**{p.get('process','')}**\n\n- Current: {p.get('current_state','—')}\n"
                          f"- Future: {p.get('future_state','—')}" for p in procs) or "_To be mapped._"
    return [
        {"heading": "Business Context", "body_markdown":
            f"{eng.company} is implementing Odoo to unify operations. This document "
            f"captures the agreed business requirements gathered during discovery.\n\n"
            f"### Scope areas\n{scope}"},
        {"heading": "Requirements", "body_markdown":
            f"{len(reqs)} requirements were captured and prioritised (MoSCoW).\n\n{reqtbl}"},
        {"heading": "Process Maps (current → future)", "body_markdown": proc_md},
        {"heading": "Data & Integrations", "body_markdown":
            "### Data objects\n" + ("\n".join(f"- {d}" for d in ba.get("data_objects") or []) or "_TBD_")
            + "\n\n### Integrations\n" + (_table(["System", "Direction", "Note"],
              [[i.get("system", ""), i.get("direction", ""), i.get("note", "")]
               for i in ba.get("integrations") or []]))},
    ]


def _sections_frs(eng) -> list:
    fns = eng.stages.get("functional") or []
    blocks = []
    for f in fns:
        opts = f.get("solution_options") or []
        rec = next((o for o in opts if o.get("recommended")), opts[0] if opts else {})
        fin = f.get("finance") or {}
        fin_md = ""
        if fin.get("ifrs") or fin.get("tax"):
            parts = []
            if fin.get("tax"):
                parts.append(f"_Tax:_ {fin['tax'].get('country')} VAT {fin['tax'].get('vat')}")
            for i in fin.get("ifrs") or []:
                parts.append(f"_{i.get('standard')}:_ {i.get('treatment')}")
            fin_md = "\n\n**Accounting treatment.** " + " ".join(parts)
        mods = ", ".join(m.get("name", "") for m in
                         (f.get("standard_capability") or {}).get("modules") or [])
        blocks.append(
            f"### {(f.get('requirement_summary') or '')[:90]}\n\n"
            f"**Verdict:** {_VERDICT_LABEL.get(f.get('verdict',''), f.get('verdict',''))}"
            f"{' · ⚠ deferred (needs review)' if f.get('deferred') else ''}\n\n"
            f"{f.get('verdict_rationale','')}\n\n"
            f"**Odoo modules:** {mods or '—'}\n\n"
            f"**Recommended approach:** {rec.get('approach') or f.get('recommended_path','')}"
            f"{fin_md}")
    body = "\n\n---\n\n".join(blocks) or "_Run the functional analysis first._"
    return [
        {"heading": "Solution Overview", "body_markdown":
            f"This specification details how each requirement is met in Odoo, "
            f"standard-first. {len(fns)} requirements analysed.\n\n"
            f"{_table(['ID','Requirement','Area','Priority','Odoo fit','Module'], _frs_rows(eng))}"},
        {"heading": "Requirement Specifications", "body_markdown": body},
    ]


def _sections_charter(eng) -> list:
    est = eng.stages.get("estimate") or {}
    tl = est.get("timeline") or []
    team = est.get("team") or []
    phase_tbl = _table(["Phase", "Starts (week)", "Duration"],
                       [[t.get("phase", ""), t.get("starts_week", ""), f"{t.get('weeks','')}w"] for t in tl])
    team_md = "\n".join(f"- **{m.get('role','')}** — {m.get('allocation','')}" for m in team) or "_TBD_"
    pr = est.get("pricing") or {}
    gov = pm_knowledge.GOVERNANCE
    method_md = "\n".join(
        f"### {i+1}. {m['phase']}\n{m['objectives']}\n\n**Deliverables:** "
        f"{', '.join(m['deliverables'])}. **Exit:** {m['exit']}"
        for i, m in enumerate(pm_knowledge.METHODOLOGY))
    raid_md = ("**Risks**\n" + "\n".join(f"- {r[0]} ({r[1]}) — {r[2]}"
                                         for r in pm_knowledge.RISK_REGISTER))
    return [
        {"heading": "Objectives & Scope", "body_markdown":
            f"Deliver an Odoo ERP solution for {eng.company} covering the agreed scope, "
            f"standard-Odoo-first, on a phased plan with one production go-live.\n\n"
            f"- Total effort: **{est.get('total_man_days','TBD')} man-days**\n"
            f"- Duration: **{est.get('duration_weeks','TBD')} weeks**\n"
            f"- Custom builds: **{est.get('custom_builds',0)}**"},
        {"heading": "Delivery Methodology", "body_markdown": method_md},
        {"heading": "Delivery Plan", "body_markdown": phase_tbl},
        {"heading": "Team", "body_markdown": team_md},
        {"heading": "Governance", "body_markdown":
            f"- **Cadence:** {gov['cadence']}\n- **Steering:** {gov['steering']}\n"
            f"- **Reporting:** {gov['reporting']}\n- **Change control:** {gov['change_control']}"},
        {"heading": "Risks (RAID)", "body_markdown": raid_md},
        {"heading": "Commercials", "body_markdown":
            f"Estimated value: **{_aed(pr.get('estimate_aed'))}** "
            f"(band {_aed((pr.get('range_aed') or [None,None])[0])}–{_aed((pr.get('range_aed') or [None,None])[1])}). "
            f"{pr.get('vat_note','')} {pr.get('licensing_note','')}"},
    ]


def _sections_techdesign(eng) -> list:
    dev = eng.stages.get("developer") or {}
    customs = [f for f in (eng.stages.get("functional") or []) if f.get("verdict") == "custom"]
    files = dev.get("files") or []
    custom_md = "\n".join(f"- {(c.get('requirement_summary') or '')[:90]} — "
                          f"{(c.get('technical_design') or 'design TBD')}" for c in customs) or "_None._"
    file_md = "\n".join(f"- `{f.get('path','')}`" for f in files) or "_No module generated yet._"
    return [
        {"heading": "Technical Approach", "body_markdown":
            "Standard Odoo configuration first; custom modules only where the "
            "functional analysis returned a Custom verdict."},
        {"heading": "Custom Build Designs", "body_markdown": custom_md},
        {"heading": "Module Structure", "body_markdown":
            f"Module: `{dev.get('module_technical_name','—')}`\n\n{file_md}"},
    ]


def _sections_sow(eng) -> list:
    est = eng.stages.get("estimate") or {}
    pr = est.get("pricing") or {}
    over = est.get("overheads") or []
    ws = _table(["Workstream", "Man-days"], [[o.get("workstream", ""), o.get("man_days", "")] for o in over])
    return [
        {"heading": "Scope of Work", "body_markdown":
            f"C2P Consultants will deliver the Odoo implementation for {eng.company} "
            f"per the requirements catalog ({len((_ba(eng).get('functional_requirements') or []))} "
            f"requirements) and the delivery plan below."},
        {"heading": "Effort & Workstreams", "body_markdown":
            f"Total: **{est.get('total_man_days','TBD')} man-days** over "
            f"**{est.get('duration_weeks','TBD')} weeks**.\n\n{ws}"},
        {"heading": "Commercials & Terms", "body_markdown":
            f"Fee: **{_aed(pr.get('estimate_aed'))}**. {pr.get('vat_note','')} "
            f"{pr.get('licensing_note','')}\nPayment: 50% on signature, 50% on go-live sign-off."},
    ]


_BUILDERS = {
    "brd": _sections_brd, "frs": _sections_frs, "gapfit": _sections_frs,
    "charter": _sections_charter, "techdesign": _sections_techdesign, "sow": _sections_sow,
    "status": _sections_charter,
}


def build(doc_key: str, eng) -> dict[str, Any]:
    """Assemble a deliverable document from structured engagement data — no API."""
    name = DOC_TITLES.get(doc_key, "Deliverable")
    builder = _BUILDERS.get(doc_key, _sections_brd)
    sections = builder(eng)
    est = eng.stages.get("estimate") or {}
    reqs = _ba(eng).get("functional_requirements") or []
    exec_sum = (f"This {name} for {eng.company} is assembled from the engagement's "
                f"requirements analysis"
                + (f" ({len(reqs)} requirements)" if reqs else "")
                + (f", a {est.get('total_man_days')}-man-day / {est.get('duration_weeks')}-week "
                   f"delivery estimate" if est else "")
                + ". It reflects a standard-Odoo-first solution.")
    return {
        "doc_type": name, "title": name,
        "subtitle": eng.company, "version": "1.0",
        "prepared_for": eng.company, "prepared_by": "C2P Consultants",
        "executive_summary": exec_sum,
        "sections": sections,
        "acceptance_criteria": [r.get("requirement", "")[:120] for r in reqs
                                if r.get("priority") == "M"][:8] or
                               ["All in-scope requirements configured and signed off in UAT."],
        "assumptions": (_ba(eng).get("assumptions") if isinstance(_ba(eng).get("assumptions"), list)
                        else None) or
                       ["Standard Odoo where it fits; custom only where proven.",
                        "Client provides timely data, sign-offs and UAT resources."],
        "next_steps": ["Review and sign off this document.", "Proceed to the next delivery phase."],
        "source": "template",
    }
