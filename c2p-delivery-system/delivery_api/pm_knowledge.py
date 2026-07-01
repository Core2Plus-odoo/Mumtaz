"""Built-in Project-Management intelligence — deterministic delivery estimation.

A senior Odoo delivery manager doesn't need an LLM to size a project: effort is a
function of requirement count, Odoo-fit (standard/config/studio/custom) and a few
well-known multipliers (data migration, testing, training, governance). This
module encodes that estimating model so effort, timeline, team and a price band
are computed instantly, with NO API call — grounding the proposal/project stages.

Day rate and team shape are configurable via env.
"""
from __future__ import annotations

import math
import os
from typing import Optional

DAY_RATE_AED = float(os.getenv("C2P_DAY_RATE_AED", "1800"))   # blended consultant/day
TEAM_VELOCITY = float(os.getenv("C2P_TEAM_VELOCITY", "13.5"))  # effective md / week

# Build effort (man-days) per requirement by Odoo-fit verdict.
FIT_MD = {"standard": 0.5, "configurable": 1.5, "studio": 3.0,
          "custom": 8.0, "unknown": 2.0}

# Area complexity multipliers — some domains carry more config/testing weight.
AREA_FACTOR = {
    "accounting": 1.4, "finance": 1.4, "tax": 1.3, "manufacturing": 1.4,
    "mrp": 1.4, "inventory": 1.2, "warehouse": 1.2, "payroll": 1.5, "hr": 1.1,
    "pos": 1.2, "ecommerce": 1.3, "integration": 1.5, "crm": 1.0, "sales": 1.0,
    "purchase": 1.0, "project": 1.0,
}

# Wrap-around workstreams as a fraction of raw build effort (min floors in md).
OVERHEADS = [
    ("Discovery & design", 0.18, 4),
    ("Data migration", 0.15, 3),
    ("Testing & UAT", 0.20, 4),
    ("Training & change mgmt", 0.10, 2),
    ("PM & governance", 0.15, 3),
    ("Go-live & hypercare", 0.10, 3),
]

# Standard delivery phases (share of the TOTAL plan).
PHASES = [
    ("Discovery & Analysis", 0.12),
    ("Solution Design", 0.10),
    ("Configuration & Build", 0.34),
    ("Data Migration", 0.10),
    ("Testing & UAT", 0.16),
    ("Training & Go-Live", 0.10),
    ("Hypercare", 0.08),
]

TEAM = [
    {"role": "Project Manager", "allocation": "part-time"},
    {"role": "Functional Consultant (Odoo)", "allocation": "full-time"},
    {"role": "Business Analyst", "allocation": "discovery-heavy"},
    {"role": "Technical Developer", "allocation": "build phase"},
    {"role": "QA / Tester", "allocation": "test phase"},
]


# --------------------------------------------------------------------------- #
# Odoo ERP Implementation methodology — the full delivery playbook.
# --------------------------------------------------------------------------- #
METHODOLOGY = [
    dict(phase="Discovery & Analysis", workstream="Analysis",
         objectives="Understand the business, agree scope, baseline current processes.",
         activities=["Stakeholder interviews per business area", "As-is process mapping",
                     "Requirements gathering & prioritisation (MoSCoW)", "Fit-gap against standard Odoo"],
         deliverables=["Business Requirements Document (BRD)", "Process maps", "Prioritised backlog"],
         exit="BRD signed off; scope baselined."),
    dict(phase="Solution Design", workstream="Design",
         objectives="Design the to-be solution, standard-first; specify configuration and any gaps.",
         activities=["To-be process design", "Functional specification (FRS)",
                     "Configuration workbook", "Custom-development specs (only where proven)",
                     "Integration & data-migration design"],
         deliverables=["Functional Specification (FRS)", "Config workbook", "Technical design (customs)"],
         exit="FRS & design signed off."),
    dict(phase="Configuration & Build", workstream="Build",
         objectives="Configure modules and build the agreed customisations.",
         activities=["Configure master data & modules per workbook", "Develop custom modules",
                     "Build reports & dashboards", "Unit test each build"],
         deliverables=["Configured system (staging)", "Custom modules", "Reports"],
         exit="Build complete; unit-tested; ready for data & SIT."),
    dict(phase="Data Migration", workstream="Data",
         objectives="Migrate clean master and opening data into Odoo.",
         activities=["Extract from legacy", "Cleanse & de-duplicate", "Map & transform",
                     "Load (customers, vendors, products, stock, opening balances)", "Reconcile & validate"],
         deliverables=["Migration templates", "Loaded & reconciled data", "Validation sign-off"],
         exit="Data validated and reconciled to source (e.g. trial balance ties)."),
    dict(phase="Testing & UAT", workstream="Test",
         objectives="Prove the solution end-to-end and get business sign-off.",
         activities=["System integration testing (SIT)", "Prepare UAT scripts",
                     "Business UAT cycles", "Defect triage & fixes", "Performance check"],
         deliverables=["Test scripts", "Defect log", "UAT sign-off"],
         exit="UAT signed off; open defects within agreed threshold."),
    dict(phase="Training & Go-Live", workstream="Deploy",
         objectives="Prepare users and cut over to production.",
         activities=["Train-the-trainer & end-user training", "Cutover plan & dry-run",
                     "Production migration & go/no-go", "Go-live"],
         deliverables=["Training materials", "Cutover runbook", "Production go-live"],
         exit="Production live; users trained; cutover checklist complete."),
    dict(phase="Hypercare", workstream="Support",
         objectives="Stabilise, support and hand over to BAU.",
         activities=["On-site/near support (typically 2 weeks)", "Rapid defect resolution",
                     "KPI monitoring", "Handover to support"],
         deliverables=["Hypercare log", "Lessons learned", "Support handover"],
         exit="Stable operation; handover to support/BAU."),
]

RISK_REGISTER = [
    ("Poor/late data quality delays go-live", "High", "Get sample data in discovery; parallel cleansing workstream."),
    ("Scope creep / evolving requirements", "High", "Baseline at design sign-off; change-request gate with impact assessment."),
    ("Low user adoption", "Medium", "Early involvement, role-based training, super-users, phased rollout."),
    ("Integration complexity underestimated", "Medium", "Prototype integrations early; agree owners and SLAs."),
    ("Over-customisation increases cost & upgrade risk", "Medium", "Standard-first; challenge every custom; Studio before code."),
    ("Insufficient client resource for UAT/sign-off", "Medium", "Name owners in the charter; schedule UAT windows upfront."),
    ("Statutory/VAT/e-invoicing compliance gaps", "Medium", "Validate with the client's auditor; use localisation modules."),
    ("Cutover issues at go-live", "Medium", "Cutover dry-run; go/no-go checklist; rollback plan."),
]

GOVERNANCE = {
    "cadence": "Weekly delivery status + fortnightly steering committee.",
    "steering": "C2P Delivery Lead + Client Sponsor + workstream owners; decisions and risks escalated here.",
    "reporting": "Weekly RAG status (scope/schedule/budget/risks), open decisions, and next-week plan.",
    "change_control": "All scope changes via a change request with effort/cost/schedule impact and sponsor approval.",
}


def methodology() -> str:
    """Compact implementation-methodology reference for embedding in prompts."""
    phases = "; ".join(f"{i+1}. {p['phase']}" for i, p in enumerate(METHODOLOGY))
    return ("ODOO ERP IMPLEMENTATION METHODOLOGY (C2P). Phased delivery: " + phases +
            ". Each phase has clear deliverables and exit criteria; standard-Odoo-first; "
            "data quality is the usual critical path; weekly RAG + steering governance; "
            "scope baselined at design sign-off with a change-request gate; 2-week hypercare.")


def build_project_plan(eng) -> dict:
    """Generate a full implementation project plan (the 'project' stage shape)
    from the estimate + methodology — NO API call."""
    est = eng.stages.get("estimate") or {}
    tl = {t.get("phase"): t for t in (est.get("timeline") or [])}
    reqs = (eng.stages.get("ba_requirements") or {}).get("functional_requirements") or []
    customs = [r for r in reqs if (r.get("odoo_fit") in ("custom", "studio"))]

    phases = []
    for m in METHODOLOGY:
        # match methodology phase to the estimate's timeline where possible
        wk = next((t.get("weeks") for name, t in tl.items()
                   if name and (name.split()[0].lower() in m["phase"].lower()
                                or m["phase"].split()[0].lower() in name.lower())), None)
        tasks = [{"name": a, "workstream": m["workstream"],
                  "owner_role": ("Developer" if m["workstream"] == "Build" and "custom" in a.lower()
                                 else "Functional Consultant" if m["workstream"] in ("Analysis", "Design", "Build")
                                 else "PM" if m["workstream"] == "Deploy" else "Consultant"),
                  "depends_on": ""}
                 for a in m["activities"]]
        phases.append({"name": m["phase"], "weeks": wk or 2,
                       "milestone": m["exit"], "tasks": tasks})

    return {
        "project_name": f"{eng.company} — Odoo ERP Implementation",
        "phases": phases,
        "raid": {
            "risks": [f"{r[0]} ({r[1]}) — {r[2]}" for r in RISK_REGISTER],
            "assumptions": ["Standard Odoo where it fits; custom only where proven.",
                            "Client provides timely data, sign-offs and UAT resources.",
                            "One production go-live; phased rollout for large scope."],
            "issues": [],
            "dependencies": ["Timely, clean legacy data", "Named client owners for UAT/sign-off",
                             "Access/credentials for integrations"],
        },
        "governance": GOVERNANCE,
        "custom_builds": len(customs),
        "source": "pm-knowledge",
    }


def digest() -> str:
    """A compact PM estimating reference to embed in an agent's system prompt."""
    fit = "; ".join(f"{k}={v}md" for k, v in FIT_MD.items())
    over = "; ".join(f"{n} {int(f * 100)}%" for n, f, _ in OVERHEADS)
    ph = "; ".join(f"{n} {int(s * 100)}%" for n, s in PHASES)
    return ("PM ESTIMATING MODEL (C2P). Build effort per requirement by Odoo-fit: " + fit +
            " (× area factor). Overheads on build effort: " + over +
            ". Delivery phases (share of plan): " + ph +
            f". Blended day rate AED {int(DAY_RATE_AED)}; price band ±15–20%; add 5% VAT; "
            "Odoo licensing billed separately. Always phase large scope (MVP first).")


def _area_factor(area: Optional[str]) -> float:
    a = (area or "").lower()
    for key, f in AREA_FACTOR.items():
        if key in a:
            return f
    return 1.0


def _risks(reqs, customs: int, finance: int) -> list:
    risks = []
    if customs:
        risks.append(f"{customs} custom build(s) — confirm specs early; re-test on each Odoo upgrade.")
    if finance:
        risks.append("Finance/tax scope — validate VAT treatment and statutory reports with the client's accountant.")
    if len(reqs) > 25:
        risks.append("Large scope — phase the rollout (MVP first) to control change and UAT load.")
    risks.append("Data migration quality is the usual critical path — get sample data early.")
    risks.append("Lock scope at design sign-off; route changes through a change-request gate.")
    return risks


def estimate(requirements: list, day_rate: Optional[float] = None) -> dict:
    """Size a delivery from a requirements list. Each item may carry
    'verdict'/'odoo_fit', 'area', 'priority'. Returns a full estimate — no API."""
    rate = float(day_rate or DAY_RATE_AED)
    items = requirements or []
    build_md = 0.0
    customs = finance = 0
    by_area: dict[str, float] = {}
    for r in items:
        fit = (r.get("verdict") or r.get("odoo_fit") or "unknown").lower()
        if fit not in FIT_MD:
            fit = "unknown"
        area = r.get("area") or "general"
        md = FIT_MD[fit] * _area_factor(area)
        build_md += md
        by_area[area] = round(by_area.get(area, 0) + md, 1)
        if fit == "custom":
            customs += 1
        if _area_factor(area) >= 1.3 and ("financ" in area.lower() or "tax" in area.lower()
                                          or "account" in area.lower()):
            finance += 1

    build_md = round(build_md, 1)
    overheads = []
    over_total = 0.0
    for name, frac, floor in OVERHEADS:
        md = max(round(build_md * frac, 1), floor)
        overheads.append({"workstream": name, "man_days": md})
        over_total += md
    total_md = round(build_md + over_total, 1)
    weeks = max(2, math.ceil(total_md / TEAM_VELOCITY))

    timeline, acc = [], 0
    for name, share in PHASES:
        wk = max(1, round(weeks * share))
        timeline.append({"phase": name, "weeks": wk, "starts_week": acc + 1})
        acc += wk

    price = round(total_md * rate)
    return {
        "source": "pm-knowledge",
        "requirements_costed": len(items),
        "build_man_days": build_md,
        "overheads": overheads,
        "total_man_days": total_md,
        "effort_by_area": by_area,
        "duration_weeks": weeks,
        "timeline": timeline,
        "team": TEAM,
        "pricing": {
            "model": "Time & Materials / fixed-price band",
            "day_rate_aed": rate,
            "estimate_aed": price,
            "range_aed": [round(price * 0.85), round(price * 1.2)],
            "vat_note": "Add 5% UAE VAT.",
            "licensing_note": "Odoo subscription (user + apps) billed separately by Odoo.",
        },
        "custom_builds": customs,
        "risks": _risks(items, customs, finance),
        "assumptions": [
            "Standard Odoo where it fits; custom only where proven necessary.",
            "One production go-live; phased rollout for large scope.",
            "Client provides timely data, sign-offs and UAT resources.",
        ],
    }
