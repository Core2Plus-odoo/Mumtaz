"""Fully-local agent generators — run the whole pipeline with NO model / no API.

These produce schema-compatible outputs for the stages that were otherwise
LLM-only (presales, requirements catalog, proposal) by assembling from the
built-in Odoo / BA / PM / finance knowledge. Output is templated (not AI-crafted
prose) but complete and professional — so the agency operates end-to-end with
zero Anthropic (or any) API cost. When a model IS configured, the endpoints use
it and fall back to these.
"""
from __future__ import annotations

import re
from typing import Optional

import odoo_knowledge
import pm_knowledge
import ba_knowledge

_ICP = ("manufactur", "distribut", "retail", "trad", "wholesale", "ecommerce",
        "fmcg", "logistics", "construc")


def _icp_score(industry: Optional[str]) -> tuple[int, str]:
    ind = (industry or "").lower()
    if any(k in ind for k in _ICP):
        return 82, "Strong ICP fit — a C2P sweet-spot industry (Odoo covers the core well)."
    if ind:
        return 62, "Moderate ICP fit — viable Odoo scope; qualify size and complexity."
    return 55, "Industry not specified — qualify further before committing effort."


def _lines(notes: str) -> list:
    parts = re.split(r"[\n;••]|(?<=[.!?])\s+", notes or "")
    return [p.strip(" -–—\t") for p in parts if len(p.strip()) > 8][:12]


def build_presales(company: str, industry: Optional[str], country: str,
                   notes: str = "") -> dict:
    score, rationale = _icp_score(industry)
    areas = ba_knowledge.focus_areas(industry)
    note_reqs = _lines(notes)
    cand = [{"requirement": r, "priority": "Medium"} for r in note_reqs]
    for a in areas[:5]:
        cand.append({"requirement": f"Implement {a} in Odoo (standard-first)",
                     "priority": "High" if a in ("Accounting & Finance", "Sales & CRM") else "Medium"})
    modules = sorted(
        {m for a in areas for m in (ba_knowledge.AREAS.get(a, {}).get("modules") or [])})
    return {
        "company_profile": {"name": company, "industry": industry or "Unknown",
                            "country": country or "UAE/GCC", "size_band": "SME (20–500)"},
        "icp_fit": {"score": score, "rationale": rationale},
        "discovery": {
            "pains": note_reqs[:5] or ["Disconnected systems / manual processes",
                                       "No real-time visibility across the business"],
            "current_systems": ["To be confirmed in discovery"],
            "goals": ["Unify operations on Odoo", "Real-time reporting", "Standard-first, upgrade-safe"]},
        "candidate_requirements": cand[:12],
        "modules_in_scope": modules,
        "red_flags": [] if score >= 60 else ["Fit unclear — validate scope/budget"],
        "recommendation": "pursue" if score >= 60 else "nurture",
        "next_action": "Run Business Analyst discovery to build the requirements catalog.",
        "source": "local",
    }


def build_catalog(eng) -> dict:
    """Requirements catalog from presales candidates + discovery areas, each
    classified against built-in Odoo knowledge."""
    cands = [c.get("requirement") if isinstance(c, dict) else c
             for c in ((eng.stages.get("presales") or {}).get("candidate_requirements") or [])]
    disc = eng.stages.get("ba_discovery") or {}
    for pa in disc.get("process_areas") or []:
        area = pa.get("area")
        cands.append(f"Configure {area} per discovery")
    cands = [c for c in dict.fromkeys(cands) if c]

    frs, scope = [], set()
    for i, req in enumerate(cands, 1):
        cl = odoo_knowledge.classify(req)
        res = cl.get("result") or {}
        mods = (res.get("standard_capability", {}).get("modules") or [{}])
        area = (mods[0].get("name") if mods else None) or "General"
        scope.add(area)
        frs.append({
            "id": f"FR-{i:02d}", "area": area, "requirement": req,
            "priority": "M" if i <= max(3, len(cands) // 2) else "S",
            "odoo_fit": res.get("verdict") or "unknown",
            "module_hint": area,
            "acceptance": (res.get("recommended_path") or "Configured and signed off in UAT")[:160],
        })
    customs = [f["requirement"] for f in frs if f["odoo_fit"] in ("custom", "studio")]
    return {
        "summary": f"{len(frs)} requirements catalogued for {eng.company}; "
                   f"{len(customs)} need custom/Studio work, the rest standard-first.",
        "scope_areas": sorted(scope),
        "functional_requirements": frs,
        "non_functional_requirements": ["Role-based access & audit trail",
                                        "Performance at peak volumes", "Data residency / compliance"],
        "data_objects": ["Customers", "Vendors", "Products", "Opening stock", "GL balances"],
        "integrations": [],
        "process_maps": [{"process": a, "current_state": "Manual / disconnected",
                          "future_state": f"Standard Odoo {a} process"} for a in sorted(scope)][:6],
        "open_questions": customs and [f"Confirm detailed rules for: {c[:70]}" for c in customs[:5]] or [],
        "assumptions": ["Standard Odoo where it fits; custom only where proven."],
        "risks": ["Data migration quality is the usual critical path."],
        "source": "local",
    }


def build_proposal(eng) -> dict:
    est = eng.stages.get("estimate") or {}
    if not est:
        ba = (eng.stages.get("ba_requirements") or {}).get("functional_requirements") or []
        sized = ([{"odoo_fit": r.get("odoo_fit"), "area": r.get("area")} for r in ba]
                 or [{"verdict": f.get("verdict")} for f in (eng.stages.get("functional") or [])])
        est = pm_knowledge.estimate(sized) if sized else {}
    pr = est.get("pricing") or {}
    ba = eng.stages.get("ba_requirements") or {}
    areas = ba.get("scope_areas") or []
    reqs = ba.get("functional_requirements") or []
    customs = [r for r in reqs if r.get("odoo_fit") in ("custom", "studio")]

    phases = [{"name": m["phase"], "deliverables": m["deliverables"]}
              for m in pm_knowledge.METHODOLOGY]
    eff = [{"workstream": o.get("workstream"), "role": "Consultant", "man_days": o.get("man_days")}
           for o in (est.get("overheads") or [])]
    if est.get("build_man_days"):
        eff.insert(0, {"workstream": "Configuration & Build", "role": "Functional/Developer",
                       "man_days": est.get("build_man_days")})
    timeline = [{"milestone": t.get("phase"), "week": t.get("starts_week")}
                for t in (est.get("timeline") or [])]
    return {
        "solution_summary": (f"C2P Consultants will implement Odoo ERP for {eng.company}, "
                             f"standard-Odoo-first, across {', '.join(areas) or 'the agreed scope'}. "
                             f"{len(customs)} item(s) require custom/Studio work; the rest is "
                             "delivered by configuration on a phased plan with one production go-live."),
        "in_scope": [r.get("requirement") for r in reqs][:20] or
                    [f"{a} implementation" for a in areas],
        "out_of_scope": ["Third-party licences", "Hardware", "Non-Odoo custom systems",
                         "Changes raised after design sign-off (via change request)"],
        "phases": phases,
        "effort_estimate": eff or [{"workstream": "Implementation", "role": "Consultant",
                                    "man_days": est.get("total_man_days")}],
        "assumptions": ["Standard Odoo where it fits; custom only where proven.",
                        "Client provides timely data, sign-offs and UAT resources."],
        "dependencies": ["Clean legacy data", "Named client owners for UAT/sign-off"],
        "commercial": {
            "pricing_model": pr.get("model") or "Fixed-price band",
            "estimate_aed": pr.get("estimate_aed"),
            "vat_note": pr.get("vat_note") or "Add 5% UAE VAT.",
            "licensing_note": pr.get("licensing_note") or "Odoo subscription billed separately by Odoo."},
        "timeline": timeline,
        "success_criteria": ["All in-scope requirements configured & signed off in UAT",
                             "Production go-live with trained users", "Standard, upgrade-safe solution"],
        "source": "local",
    }
