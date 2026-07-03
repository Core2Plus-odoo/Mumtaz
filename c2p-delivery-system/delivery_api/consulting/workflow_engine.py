"""Consulting OS Layer 4 — the WORKFLOW ENGINE.

Workflows are DATA: an ordered list of steps composed from `step_library`.
`SERVICE_WORKFLOW[service]` names the step sequence for each service the
consultant sells; `compose()` expands those keys into full step objects, and
`generate()` turns a consultant profile into the set of workflows that
consultant should run — the built-in `erp_implementation` workflow reproduces
the existing Odoo delivery pipeline exactly, so autopilot stays backward
compatible. The runner (a generalised autopilot_step) will later walk these
step lists; here we only define and compose them.
"""
from __future__ import annotations

from . import service_catalog as cat
from . import step_library as lib

# service_key -> ordered step keys. Odoo services reuse the full delivery spine;
# finance/consulting services are shorter, cadence- or engagement-shaped chains.
SERVICE_WORKFLOW: dict[str, list[str]] = {
    # Odoo ERP partner
    "erp_implementation": ["lead_qualification", "discovery", "requirements",
                            "estimation", "proposal", "project_plan",
                            "functional_design", "development", "configuration",
                            "documentation", "qa_uat", "deployment", "reporting"],
    "odoo_customization": ["requirements", "estimation", "proposal",
                           "functional_design", "development", "qa_uat",
                           "deployment"],
    "odoo_integration": ["discovery", "requirements", "estimation", "proposal",
                         "development", "qa_uat", "deployment"],
    "odoo_training": ["discovery", "proposal", "documentation", "reporting"],
    "odoo_support": ["lead_qualification", "proposal", "configuration",
                     "qa_uat", "reporting"],
    # Bookkeeper (recurring cadence)
    "bookkeeping": ["client_onboarding", "data_collection", "bookkeeping_close",
                    "reconciliation", "financial_statements", "reporting"],
    "vat_filing": ["data_collection", "vat_computation", "return_filing",
                   "reporting"],
    "financial_reporting": ["data_collection", "financial_statements",
                            "reporting"],
    "payroll_processing": ["data_collection", "payroll_run", "reporting"],
    # Chartered accountant
    "compliance_advisory": ["discovery", "compliance_review", "advisory_report"],
    "audit_preparation": ["data_collection", "audit_prep", "advisory_report"],
    "cfo_advisory": ["discovery", "data_collection", "financial_statements",
                     "advisory_report", "reporting"],
    # Management consultant
    "sop_design": ["process_mapping", "sop_generation", "documentation"],
    "bpr": ["process_mapping", "gap_analysis", "process_redesign",
            "documentation"],
    "strategy_consulting": ["discovery", "strategy_analysis", "advisory_report"],
    "kpi_design": ["discovery", "kpi_framework", "documentation"],
}

# Fallback chain for any service without an explicit workflow.
_DEFAULT_WORKFLOW = ["discovery", "proposal", "documentation", "reporting"]

_SERVICE_LABELS = {s: l for c in cat.SERVICE_CATALOG.values() for s, l in c.items()}


def compose(service: str) -> dict:
    """Expand a service into a full workflow definition (steps as objects)."""
    keys = SERVICE_WORKFLOW.get(service) or _DEFAULT_WORKFLOW
    steps = [lib.step(k) for k in keys if lib.step(k)]
    return {
        "key": service,
        "label": _SERVICE_LABELS.get(service, service),
        "steps": steps,
        "gates": sorted({s["gate"] for s in steps if s.get("gate")}),
        "documents": _ordered_unique(d for s in steps for d in s.get("documents", [])),
        "agents": _ordered_unique(a for s in steps for a in s.get("agents", [])),
        "step_count": len(steps),
        "builtin": service == "erp_implementation",
    }


def generate(services: list) -> list[dict]:
    """Compose one workflow per service the consultant sells (dedup, catalog
    order). `erp_implementation` is always available as the built-in pipeline."""
    seen, out = set(), []
    for s in services or []:
        if s in seen:
            continue
        seen.add(s)
        out.append(compose(s))
    return out


def _ordered_unique(items) -> list:
    out: list = []
    for i in items:
        if i not in out:
            out.append(i)
    return out
