"""Odoo native-automation knowledge — the no-code toolkit the architect reaches
for before any custom code, plus the standard integrated data flows.

Embedded in the functional/config/developer agents so they design automation with
Automation Rules / Server Actions / Scheduled Actions / templates / activities /
approvals / sequences — connected to the standard O2C / P2P / Make chains — rather
than writing code. `suggest()` produces a first-pass automation design + connection
map locally (no API).
"""
from __future__ import annotations

import re

TOOLKIT = {
    "Automation Rule": "No-code trigger→action on create / update / create-or-update / "
        "delete / timed condition (N days before/after a date) / stage or state change. "
        "Actions: update record, create activity, send email/SMS, add followers, create "
        "record, run Python, or chain server actions. Scope with a filter/domain. "
        "(Called 'Automated Actions' in v16.)",
    "Server Action": "ir.actions.server — update/create record, run Python, send email/SMS, "
        "add followers, create activity, or group actions. Bind to a button, an Action menu, "
        "an Automation Rule, or a Scheduled Action.",
    "Scheduled Action": "ir.cron — recurring time-based jobs.",
    "Email/SMS Template": "mail.template with dynamic QWeb/Jinja placeholders.",
    "Activity & Activity Plan": "mail.activity — scheduled, assignable to-dos; Activity Plans "
        "for onboarding / follow-up sequences.",
    "Approval": "Approvals app, Studio approval rules, and standard to-approve flows "
        "(purchase double validation, expense/time-off approval, amount thresholds).",
    "Sequence": "ir.sequence — auto-numbering (prefix, per-company, per-period).",
}

# Built-in process automation to CONFIGURE (not rebuild), per area.
PROCESS_AUTOMATION = {
    "Sales / O2C": "quotation templates, online sign & pay, invoicing policy (ordered vs "
        "delivered), down payments, subscriptions (recurring invoicing), rule-based pricelists, "
        "sales-team assignment.",
    "CRM": "lead assignment rules (rule-based & round-robin), predictive lead scoring, "
        "stage-based automated activities.",
    "Purchase / P2P": "reordering rules → auto RFQ/PO, vendor pricelists, purchase agreements "
        "(blanket/tender), 3-way bill control, approval thresholds.",
    "Inventory": "routes & rules (MTO, dropship, cross-dock), reordering & replenishment, "
        "putaway rules, storage categories, lot/serial, the scheduler.",
    "Accounting": "fiscal positions (auto tax/account mapping), payment terms, bank "
        "reconciliation models, recurring/automatic entries, deferred revenue/expense, asset "
        "models (auto depreciation), follow-up (dunning) levels, analytic distribution models, "
        "e-invoicing (ZATCA/Peppol), automatic invoice sending.",
    "Manufacturing": "BoMs (kit/phantom/variants), routing & work centres, MPS, "
        "reorder-triggered production, quality checks, maintenance triggers.",
    "Project / Helpdesk / FSM": "task stage automation, recurring tasks, project templates, "
        "SLA policies, auto-assignment, timesheet → invoicing.",
    "Marketing / Website": "marketing-automation campaign flows (email→wait→condition→action), "
        "abandoned-cart automation, automated emails.",
    "Documents / Sign": "workflow rules, signature-request flows.",
}

CHAINS = {
    "Order-to-Cash": "crm.lead → sale.order → stock.picking → account.move (invoice) → payment",
    "Procure-to-Pay": "purchase.order → stock.picking (receipt) → account.move (bill) → payment",
    "Make / Replenish": "demand or reordering rule → mrp.production / RFQ → stock moves → valuation",
}

# keyword → (tool, trigger-template, action-template, connection objects)
_RULES = [
    (["follow up", "follow-up", "reminder", "overdue", "no activity", "24 hour", "sla"],
     "Automation Rule", "Timed condition on the date/stage field (e.g. N hours in stage without activity)",
     "Create an activity / send a reminder email to the responsible user", ["mail.activity", "the record"]),
    (["auto-create", "auto create", "generate", "when.*create", "on new"],
     "Automation Rule", "On create/update matching a filter",
     "Create or update the related record (chain a Server Action)", ["the source & target models"]),
    (["approval", "approve", "authorization", "sign off", "sign-off"],
     "Approval", "Amount/condition threshold on the document",
     "Route to approver(s) via Approvals / Studio approval rule / standard to-approve", ["the document + approver"]),
    (["email", "notify", "notification", "send sms", "alert"],
     "Email/SMS Template", "On stage/state change or timed condition",
     "Send an Email/SMS template with dynamic placeholders", ["mail.template", "followers"]),
    (["schedule", "nightly", "daily", "recurring job", "periodic", "batch"],
     "Scheduled Action", "ir.cron on a recurring schedule",
     "Run a Server Action over the matching records", ["ir.cron", "target model"]),
    (["number", "sequence", "auto-number", "reference code", "prefix"],
     "Sequence", "Document creation", "Assign an ir.sequence (prefix, per-company/period)", ["ir.sequence"]),
    (["reorder", "min max", "replenish", "auto purchase", "auto rfq"],
     "Automation Rule", "Stock below reordering rule minimum",
     "Standard reordering rule auto-creates the RFQ/PO or MO (configure, don't code)",
     ["stock.warehouse.orderpoint", "purchase.order/mrp.production"]),
    (["assign", "round robin", "round-robin", "distribute leads"],
     "Automation Rule", "On lead/record create matching a team/domain",
     "Standard assignment rules (rule-based / round-robin)", ["crm.team", "res.users"]),
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower())


def suggest(requirement: str) -> dict:
    """First-pass native-automation design + connection map for a requirement."""
    t = _norm(requirement)
    designs, conn = [], set()
    for keys, tool, trig, act, objs in _RULES:
        if any(re.search(k, t) for k in keys):
            designs.append({"tool": tool, "trigger": trig, "action": act, "filter": ""})
            conn.update(objs)
    # always map to the standard chain it belongs to
    if any(w in t for w in ("quotation", "sales order", "invoice", "customer", "crm", "lead", "opportunity")):
        conn.add("O2C: " + CHAINS["Order-to-Cash"])
    if any(w in t for w in ("purchase", "vendor", "rfq", "bill", "procure")):
        conn.add("P2P: " + CHAINS["Procure-to-Pay"])
    if any(w in t for w in ("manufactur", "production", "bom", "work order", "replenish")):
        conn.add("Make: " + CHAINS["Make / Replenish"])
    return {"automation_design": designs, "connection_map": sorted(conn)}


def digest() -> str:
    """Native-automation reference to embed in the architect agents' prompts."""
    tk = "\n".join(f"- {k}: {v}" for k, v in TOOLKIT.items())
    pa = "\n".join(f"- {k}: {v}" for k, v in PROCESS_AUTOMATION.items())
    ch = "; ".join(f"{k} = {v}" for k, v in CHAINS.items())
    return ("ODOO NATIVE AUTOMATION TOOLKIT (use BEFORE any custom code):\n" + tk +
            "\nBUILT-IN PROCESS AUTOMATION TO CONFIGURE (don't rebuild):\n" + pa +
            "\nSTANDARD INTEGRATED FLOWS — automate ALONG these, never across:\n" + ch +
            "\nModel workflows with state/stage + status bar + Automation Rules on state change. "
            "Custom only by _inherit of a standard model, connected to these flows.")
