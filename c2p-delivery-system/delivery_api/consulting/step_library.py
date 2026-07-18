"""Consulting OS Layer 4 — the workflow STEP LIBRARY.

Workflows are DATA composed from these reusable steps. Each step names the
existing agent(s) that execute it, the document(s) it produces, the approval
gate it must clear (see policy.AUTONOMY), the event it emits, and a plain
`done_when`. The workflow engine composes ordered lists of these keys per
service; nothing here runs an agent — the runner (generalised autopilot_step)
does that. Agent keys map to the real run_agent tasks already in main.py; a
few finance/consulting steps reuse knowledge modules (finance_knowledge,
pm_knowledge) rather than an LLM task.
"""
from __future__ import annotations

# key -> step definition. `agents` are run_agent task keys OR knowledge hooks
# (prefixed "kb:"). `gate` is a policy.AUTONOMY action or None. `documents`
# are doc_templates keys the step contributes.
STEP_LIBRARY: dict[str, dict] = {
    # --- shared delivery spine (Odoo + general) ---
    "lead_qualification": {
        "label": "Lead Qualification",
        "agents": ["presales"], "documents": [], "gate": None,
        "emits": "qualification.done",
        "done_when": "ICP fit scored and pursue/nurture/pass recommended",
    },
    "discovery": {
        "label": "Discovery",
        "agents": ["ba_discovery"], "documents": ["discovery"], "gate": None,
        "emits": "discovery.done",
        "done_when": "pains, current systems, goals and KPIs captured",
    },
    "requirements": {
        "label": "Requirements Catalog",
        "agents": ["ba"], "documents": ["requirements_catalog"], "gate": None,
        "emits": "requirements.done",
        "done_when": "prioritised requirements catalogued",
    },
    "estimation": {
        "label": "Estimation",
        "agents": ["kb:pm_knowledge"], "documents": [], "gate": None,
        "emits": "estimate.done",
        "done_when": "effort, duration and price band estimated",
    },
    "proposal": {
        "label": "Proposal",
        "agents": ["proposal"], "documents": ["proposal"], "gate": "proposal_send",
        "emits": "proposal.generated",
        "done_when": "scoped proposal drafted (sending is gated)",
    },
    "project_plan": {
        "label": "Project Plan",
        "agents": ["project"], "documents": ["charter"], "gate": None,
        "emits": "project.created",
        "done_when": "phased plan, RAID and governance defined",
    },
    "functional_design": {
        "label": "Functional Design",
        "agents": ["functional"], "documents": ["frs"], "gate": None,
        "emits": "functional.done",
        "done_when": "standard-first verdict + solution design per requirement",
    },
    "development": {
        "label": "Development",
        "agents": ["developer"], "documents": ["tech_design"], "gate": "code_deploy",
        "emits": "developer.done",
        "done_when": "custom modules generated and code-reviewed (deploy gated)",
    },
    "configuration": {
        "label": "Configuration",
        "agents": ["config"], "documents": ["config_plan"], "gate": "config_apply",
        "emits": "config.done",
        "done_when": "idempotent Odoo config plan built (apply gated)",
    },
    "documentation": {
        "label": "Documentation",
        "agents": ["docwriter"], "documents": ["brd", "frs", "sow"], "gate": None,
        "emits": "documents.done",
        "done_when": "BRD/FRS/SOW assembled from structured data",
    },
    "qa_uat": {
        "label": "QA & UAT",
        "agents": ["director"], "documents": [], "gate": None,
        "emits": "qa.done",
        "done_when": "delivery reviewed against acceptance criteria",
    },
    "deployment": {
        "label": "Deployment",
        "agents": ["config", "developer"], "documents": [], "gate": "code_deploy",
        "emits": "deployed",
        "done_when": "config applied and/or modules pushed to the client Odoo",
    },
    "reporting": {
        "label": "Reporting",
        "agents": ["kb:pm_status"], "documents": ["status_report"], "gate": None,
        "emits": "reporting.done",
        "done_when": "status / KPI report produced for the client",
    },

    # --- bookkeeping & accounting cadence (finance_knowledge) ---
    "client_onboarding": {
        "label": "Client Onboarding",
        "agents": ["ba_discovery"], "documents": ["discovery"], "gate": None,
        "emits": "client.onboarded",
        "done_when": "chart of accounts, tax profile and opening balances agreed",
    },
    "data_collection": {
        "label": "Data Collection",
        "agents": ["kb:finance_knowledge"], "documents": [], "gate": None,
        "emits": "data.collected",
        "done_when": "source documents and transactions gathered for the period",
    },
    "bookkeeping_close": {
        "label": "Monthly Close",
        "agents": ["kb:finance_knowledge"], "documents": [], "gate": None,
        "emits": "close.done",
        "done_when": "journals posted, sub-ledgers reconciled, period locked",
    },
    "reconciliation": {
        "label": "Reconciliation",
        "agents": ["kb:finance_knowledge"], "documents": [], "gate": None,
        "emits": "reconciliation.done",
        "done_when": "bank, receivable and payable balances reconciled",
    },
    "financial_statements": {
        "label": "Financial Statements",
        "agents": ["kb:finance_knowledge"], "documents": ["financials"], "gate": None,
        "emits": "financials.done",
        "done_when": "P&L, balance sheet and cash flow prepared (IFRS-aligned)",
    },
    "vat_computation": {
        "label": "VAT Computation",
        "agents": ["kb:finance_knowledge"], "documents": [], "gate": None,
        "emits": "vat.computed",
        "done_when": "output/input VAT computed for the FTA/ZATCA return",
    },
    "return_filing": {
        "label": "Return Filing",
        "agents": ["kb:finance_knowledge"], "documents": ["filing"], "gate": "client_comms_sensitive",
        "emits": "return.prepared",
        "done_when": "return prepared and reviewed (submission is gated)",
    },
    "payroll_run": {
        "label": "Payroll Run",
        "agents": ["kb:finance_knowledge"], "documents": [], "gate": None,
        "emits": "payroll.run",
        "done_when": "salaries, deductions and WPS file computed for the cycle",
    },

    # --- chartered-accountant advisory ---
    "compliance_review": {
        "label": "Compliance Review",
        "agents": ["kb:finance_knowledge"], "documents": [], "gate": None,
        "emits": "compliance.reviewed",
        "done_when": "tax/regulatory position assessed against the regime",
    },
    "audit_prep": {
        "label": "Audit Preparation",
        "agents": ["kb:finance_knowledge"], "documents": ["audit_pack"], "gate": None,
        "emits": "audit.prepared",
        "done_when": "schedules, working papers and confirmations assembled",
    },
    "advisory_report": {
        "label": "Advisory Report",
        "agents": ["docwriter"], "documents": ["advisory"], "gate": None,
        "emits": "advisory.done",
        "done_when": "findings and recommendations written up for the client",
    },

    # --- management-consultant (process / strategy) ---
    "process_mapping": {
        "label": "Process Mapping",
        "agents": ["ba_discovery"], "documents": ["process_map"], "gate": None,
        "emits": "process.mapped",
        "done_when": "as-is processes mapped with owners, inputs and outputs",
    },
    "gap_analysis": {
        "label": "Gap Analysis",
        "agents": ["ba"], "documents": [], "gate": None,
        "emits": "gap.analysed",
        "done_when": "gaps between as-is and target operating model identified",
    },
    "process_redesign": {
        "label": "Process Redesign",
        "agents": ["functional"], "documents": ["to_be"], "gate": None,
        "emits": "process.redesigned",
        "done_when": "to-be processes designed with quantified improvements",
    },
    "sop_generation": {
        "label": "SOP Generation",
        "agents": ["docwriter"], "documents": ["sop"], "gate": None,
        "emits": "sop.generated",
        "done_when": "standard operating procedures authored per process",
    },
    "strategy_analysis": {
        "label": "Strategy Analysis",
        "agents": ["research", "ba"], "documents": [], "gate": None,
        "emits": "strategy.analysed",
        "done_when": "market, capability and options analysis completed",
    },
    "kpi_framework": {
        "label": "KPI Framework",
        "agents": ["kb:pm_knowledge"], "documents": ["kpi"], "gate": None,
        "emits": "kpi.designed",
        "done_when": "KPI tree with targets and owners defined",
    },

    # --- extended delivery / advisory steps ---
    "data_migration": {
        "label": "Data Migration",
        "agents": ["config"], "documents": ["migration_plan"], "gate": None,
        "emits": "data.migrated",
        "done_when": "master and opening data cleaned, mapped, loaded and reconciled",
    },
    "training_delivery": {
        "label": "Training Delivery",
        "agents": ["docwriter", "director"], "documents": ["training_pack"], "gate": None,
        "emits": "training.delivered",
        "done_when": "role-based training run and user manuals handed over",
    },
    "health_check": {
        "label": "Health Check",
        "agents": ["director", "functional"], "documents": ["health_report"], "gate": None,
        "emits": "healthcheck.done",
        "done_when": "existing system audited; prioritised gaps and quick wins listed",
    },
    "hypercare": {
        "label": "Hypercare",
        "agents": ["director"], "documents": [], "gate": None,
        "emits": "hypercare.done",
        "done_when": "post go-live issues triaged and resolved through stabilisation",
    },
    "analytics_dashboards": {
        "label": "Analytics & Dashboards",
        "agents": ["config"], "documents": ["dashboards"], "gate": "config_apply",
        "emits": "analytics.done",
        "done_when": "KPI dashboards and reports built on live data (apply gated)",
    },
    "integration_design": {
        "label": "Integration Design",
        "agents": ["functional"], "documents": ["integration_spec"], "gate": None,
        "emits": "integration.designed",
        "done_when": "endpoints, data contracts and error handling specified",
    },
    "change_management": {
        "label": "Change Management",
        "agents": ["ba_discovery"], "documents": ["change_plan"], "gate": None,
        "emits": "change.planned",
        "done_when": "stakeholders, adoption plan and comms defined",
    },
    "budgeting_forecast": {
        "label": "Budgeting & Forecast",
        "agents": ["kb:finance_knowledge"], "documents": ["budget"], "gate": None,
        "emits": "budget.done",
        "done_when": "annual budget and rolling forecast modelled with drivers",
    },
}


def step(key: str) -> dict:
    """Return a copy of a step definition (with its key attached) or {}."""
    s = STEP_LIBRARY.get(key)
    if not s:
        return {}
    return {"key": key, **s}


def all_gates() -> set[str]:
    """Distinct approval gates referenced by the library (for policy checks)."""
    return {s["gate"] for s in STEP_LIBRARY.values() if s.get("gate")}
