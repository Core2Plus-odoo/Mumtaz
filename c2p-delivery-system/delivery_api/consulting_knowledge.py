"""Built-in Management-Consultant intelligence — frameworks, SOPs, KPIs, change.

Encodes the management-consulting knowledge a top-tier operator applies by reflex:
diagnostic and design frameworks, a standard SOP anatomy, per-function KPI trees,
process-mapping method, target operating model and change management. `advise()`
returns the right frameworks + approach + deliverable + KPIs for a consulting
requirement with NO API call; `digest()` grounds the agents' prompts. This makes
the consulting skill set as deeply built-in as the ERP/finance ones.
"""
from __future__ import annotations

import re
from typing import Optional

# --------------------------------------------------------------------------- #
# Framework library — the consultant's toolkit, keyed by what they solve.
# --------------------------------------------------------------------------- #
FRAMEWORKS = [
    dict(keys=["process map", "as-is", "as is", "current state", "sipoc", "swimlane",
               "value stream", "workflow map"],
         name="Process mapping (SIPOC + swimlane)",
         use="Capture the as-is process end-to-end with Suppliers-Inputs-Process-"
             "Outputs-Customers and swimlanes by role; measure cycle time, handoffs, "
             "rework and wait.",
         deliverable="As-is process map + pain/waste log + baseline metrics."),
    dict(keys=["gap", "maturity", "assessment", "diagnostic", "benchmark", "current vs"],
         name="Capability & gap assessment",
         use="Score capability maturity (1-5) per process area against a target "
             "operating model; quantify the gap and its business impact.",
         deliverable="Maturity heatmap + prioritised gap register (impact × effort)."),
    dict(keys=["redesign", "to-be", "to be", "future state", "bpr", "reengineer",
               "optimis", "optimize", "streamline", "lean", "six sigma", "dmaic"],
         name="Process redesign (Lean / DMAIC)",
         use="Design the to-be process: eliminate non-value-add steps, automate "
             "handoffs, add controls; DMAIC for measurable defects/cycle-time.",
         deliverable="To-be process + quantified improvement (time/cost/quality) + "
                     "RACI + control points."),
    dict(keys=["sop", "standard operating", "procedure", "work instruction", "playbook",
               "policy"],
         name="SOP authoring",
         use="Document the procedure so anyone can execute it consistently — purpose, "
             "scope, roles, step-by-step, controls, exceptions, KPIs, revision.",
         deliverable="Approved SOP pack per process, versioned, with a RACI."),
    dict(keys=["kpi", "metric", "scorecard", "balanced scorecard", "okr", "dashboard",
               "performance framework", "measure"],
         name="KPI / Balanced Scorecard",
         use="Cascade objectives to a KPI tree across four perspectives (financial, "
             "customer, process, learning); define formula, owner, target, cadence.",
         deliverable="KPI tree + owner/target/cadence + reporting dashboard spec."),
    dict(keys=["strategy", "market", "competitive", "porter", "pestle", "swot",
               "growth", "value proposition", "positioning"],
         name="Strategy diagnosis (SWOT / 5-Forces / PESTLE)",
         use="Frame the market and the firm: PESTLE (macro), Porter's 5 Forces "
             "(industry), SWOT (firm), then options scored on attractiveness × "
             "feasibility.",
         deliverable="Situation analysis + scored strategic options + roadmap."),
    dict(keys=["operating model", "tom", "org design", "organisation", "organization",
               "structure", "restructure", "roles and responsibilities", "raci"],
         name="Target Operating Model & org design",
         use="Define how the business runs across people, process, technology, data "
             "and governance; map roles to a RACI; size the org and spans/layers.",
         deliverable="TOM on a page + org chart + RACI + role charters."),
    dict(keys=["change", "adoption", "adkar", "kotter", "transformation",
               "communication plan", "stakeholder"],
         name="Change management (ADKAR / Kotter)",
         use="Drive adoption: stakeholder map, Awareness-Desire-Knowledge-Ability-"
             "Reinforcement plan, comms cadence, training and a resistance log.",
         deliverable="Change plan + stakeholder map + comms/training calendar."),
    dict(keys=["cost", "efficiency", "productivity", "margin", "working capital",
               "profitability", "cost reduction"],
         name="Cost & efficiency diagnostic",
         use="Baseline cost-to-serve and drivers; find quick wins vs structural; "
             "model the P&L impact and payback.",
         deliverable="Cost baseline + opportunity backlog with $ impact and payback."),
]

# --------------------------------------------------------------------------- #
# The standard SOP anatomy — every SOP the SOP-generator writes follows this.
# --------------------------------------------------------------------------- #
SOP_SECTIONS = [
    "Purpose — why this procedure exists and the outcome it guarantees",
    "Scope — where it applies (and where it does not)",
    "Roles & RACI — who is Responsible/Accountable/Consulted/Informed",
    "Definitions — terms, systems and documents referenced",
    "Procedure — numbered steps, each with the actor, system action and decision",
    "Controls — approvals, segregation of duties, checks and thresholds",
    "Exceptions — what to do when the happy path breaks; escalation",
    "KPIs — how performance of this process is measured",
    "Records & retention — what is filed, where, for how long",
    "Revision history — version, date, owner, change",
]

# --------------------------------------------------------------------------- #
# KPI trees per function — the metrics a consultant baselines and targets.
# --------------------------------------------------------------------------- #
KPI_TREES = {
    "sales": ["Pipeline coverage (pipeline ÷ quota)", "Win rate", "Sales cycle days",
              "CAC", "Quota attainment", "Net revenue retention"],
    "finance": ["DSO", "DPO", "Cash conversion cycle", "Gross/Net margin %",
                "Budget variance %", "Days to close (month-end)"],
    "operations": ["OTIF (on-time-in-full)", "Cycle time", "First-pass yield / defect %",
                   "Capacity utilisation", "Rework %", "Inventory turns"],
    "service": ["First response time", "Resolution time (SLA)", "CSAT / NPS",
                "First-contact resolution", "Backlog age"],
    "hr": ["Time-to-hire", "Attrition %", "Absence %", "Training hours/FTE",
           "Revenue per FTE"],
    "procurement": ["Savings vs baseline %", "PO cycle time", "Supplier OTIF",
                    "Maverick-spend %", "Contract coverage %"],
}

# --------------------------------------------------------------------------- #
# Consulting engagement method — the phases a consulting project runs through.
# --------------------------------------------------------------------------- #
METHOD = [
    "Frame — align on objectives, scope, success criteria and stakeholders",
    "Discover — interviews, data, process walk-throughs; baseline the metrics",
    "Diagnose — root-cause the gaps (5 Whys / fishbone); size the impact",
    "Design — to-be processes, TOM, SOPs and the KPI framework",
    "Plan — prioritised roadmap (impact × effort), owners, quick wins first",
    "Enable — change, training and adoption so it sticks",
    "Sustain — governance cadence and KPIs to hold the gains",
]


def digest() -> str:
    """A compact management-consulting reference to embed in an agent's prompt."""
    fw = "; ".join(f"{f['name']} ({f['keys'][0]})" for f in FRAMEWORKS)
    kpi = "; ".join(f"{fn}: {', '.join(ms[:3])}" for fn, ms in KPI_TREES.items())
    return ("MANAGEMENT-CONSULTANT REFERENCE. Diagnose with the right framework, "
            "quantify the impact, and design decision-ready deliverables.\n"
            "Method: " + " → ".join(m.split(" — ")[0] for m in METHOD) + "\n"
            "Frameworks: " + fw + "\n"
            "SOP anatomy: " + " | ".join(s.split(" — ")[0] for s in SOP_SECTIONS) + "\n"
            "KPI trees by function: " + kpi)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower())


def frameworks_for(text: str) -> list[dict]:
    t = _norm(text)
    return [f for f in FRAMEWORKS if any(k in t for k in f["keys"])]


def kpis_for(text: str) -> dict:
    """Return the KPI trees whose function is referenced in the text."""
    t = _norm(text)
    hits = {fn: ms for fn, ms in KPI_TREES.items() if fn in t}
    return hits or {}


def advise(requirement: str) -> Optional[dict]:
    """Return the consulting frameworks + approach + deliverable + KPIs for a
    requirement, or None if it isn't a consulting topic. No API call."""
    t = _norm(requirement)
    if not t:
        return None
    fws = frameworks_for(t)
    kpis = kpis_for(t)
    wants_sop = any(k in t for k in ("sop", "procedure", "work instruction",
                                     "playbook", "policy"))
    if not (fws or kpis or wants_sop):
        return None
    out = {
        "source": "consulting-knowledge",
        "frameworks": [{"name": f["name"], "use": f["use"],
                        "deliverable": f["deliverable"]} for f in fws],
        "kpis": kpis,
        "sop_anatomy": SOP_SECTIONS if wants_sop else [],
        "method": [m.split(" — ")[0] for m in METHOD],
        "risks": ["Baseline the metrics before redesign so improvement is provable.",
                  "Design for adoption — a process only counts once people run it."],
    }
    return out
