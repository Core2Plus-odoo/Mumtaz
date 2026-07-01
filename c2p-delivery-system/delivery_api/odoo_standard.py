"""Comprehensive Odoo STANDARD functionality reference (v17–v19).

The house rule is standard-Odoo-first: configure what standard (and Studio)
already do before writing a single line of custom code. To do that well the
agents must actually KNOW what standard Odoo covers. This module is that
knowledge — a per-app catalog of standard features and their key settings — plus
digests to embed in the agents' prompts and a `covered_by()` lookup used by the
functional/config stages to prove a standard path first.
"""
from __future__ import annotations

import re

# app key -> {name, module, features[], settings[]}
STANDARD = {
    "crm": dict(name="CRM", module="crm", features=[
        "Lead & opportunity capture (web forms, email alias, import, manual)",
        "Multi-team pipelines with drag-drop Kanban stages and probability",
        "Lead scoring & assignment rules (round-robin, by team/tag)",
        "Activities & next-actions, calendar sync, automated activity plans",
        "Lost reasons, expected revenue, recurring revenue (MRR)",
        "UTM source/medium/campaign tracking; lead sources",
        "Reporting: pipeline analysis, conversion, forecast"],
        settings=["Stages", "Teams", "Tags", "Lost reasons", "Recurring plans"]),
    "sale": dict(name="Sales", module="sale_management", features=[
        "Quotations & sales orders, quotation templates, e-sign & online payment",
        "Pricelists (multi-currency, quantity/date/customer rules), discounts",
        "Optional & upsell products, product variants & configurator",
        "Down payments, delivery & invoicing policies (ordered/delivered)",
        "Customer portal (quotes, orders, invoices), amendments",
        "Margins, coupons/promotions (via loyalty), commissions (basic)"],
        settings=["Pricelists", "Quotation templates", "Payment terms", "Incoterms"]),
    "purchase": dict(name="Purchase", module="purchase", features=[
        "RFQs & purchase orders, multi-level approval by amount",
        "Vendor pricelists, lead times, MOQ, blanket/call-off orders",
        "Reordering (min/max) & procurement propagation from sales/MRP",
        "3-way match (PO ↔ receipt ↔ bill), bill control policy",
        "Vendor portal, purchase agreements, requisitions"],
        settings=["Approval thresholds", "Vendor pricelists", "Purchase agreements"]),
    "stock": dict(name="Inventory", module="stock", features=[
        "Multi-warehouse & multi-location, hierarchical locations",
        "Reordering rules (min/max), make-to-order, buy/manufacture routes",
        "Lots/serials, expiration, full traceability, quality holds",
        "Putaway & removal strategies (FIFO/LIFO/FEFO), storage categories",
        "Delivery/receipt operations, backorders, scrap, inventory adjustments",
        "Landed costs, multi-step routes (pick/pack/ship), dropshipping, cross-dock",
        "Valuation: standard/FIFO/AVCO, automated (perpetual) accounting"],
        settings=["Warehouses", "Routes", "Operation types", "Reordering rules"]),
    "mrp": dict(name="Manufacturing", module="mrp", features=[
        "Bills of materials (multi-level, kits, by-products, phantom)",
        "Work orders, work centres, routings, capacity & OEE",
        "Manufacturing orders, backflush, scrap, unbuild",
        "Subcontracting (multi-level), MPS, PLM (ECO) in enterprise",
        "Quality control points integrated with operations"],
        settings=["BoMs", "Work centres", "Routings", "MPS"]),
    "account": dict(name="Accounting", module="account", features=[
        "Localized chart of accounts, journals, taxes & fiscal positions",
        "Customer/vendor invoices & bills, credit notes, payment terms",
        "Bank sync/import (CAMT/OFX/CSV) & reconciliation models",
        "Analytic accounting (plans + distribution) for cost centres/projects",
        "Multi-currency with revaluation, multi-company & inter-company",
        "Assets & depreciation, deferred revenue/expense, budgets",
        "Follow-ups (dunning), aged reports, financial statements, tax reports",
        "Consolidation, audit trail, e-invoicing localizations (ZATCA/UAE)"],
        settings=["CoA", "Taxes", "Fiscal positions", "Journals", "Analytic plans"]),
    "project": dict(name="Project", module="project", features=[
        "Projects, task stages, sub-tasks, dependencies, milestones",
        "Timesheets (hr_timesheet), planning/Gantt, recurring tasks",
        "Billing: ordered qty, timesheets (T&M), milestones; profitability",
        "Customer portal, task templates, project updates & status"],
        settings=["Stages", "Task templates", "Billing policy"]),
    "hr": dict(name="Human Resources", module="hr", features=[
        "Employee records, departments, org chart, contracts",
        "Recruitment (job posts, pipeline), referrals",
        "Time Off (leave types, approvals, accruals, allocations)",
        "Attendances (check-in/out, kiosk), Appraisals, Skills",
        "Expenses (submit, approve, reinvoice), Fleet, Employee portal"],
        settings=["Leave types", "Working schedules", "Expense categories"]),
    "pos": dict(name="Point of Sale", module="point_of_sale", features=[
        "Sessions, multiple payment methods, cash control, receipts",
        "Offline mode, restaurant/floor plans, kitchen printers",
        "Loyalty, coupons, gift cards, discounts, price control",
        "Integrated with inventory & accounting, multi-store"],
        settings=["Payment methods", "POS config", "Pricelists"]),
    "website": dict(name="Website / eCommerce", module="website_sale", features=[
        "Drag-drop CMS, blogs, forms, SEO, multi-website & multi-lang",
        "eCommerce catalogue, variants, cart, online payment & delivery",
        "Customer portal, wishlists, comparisons, cross/up-sell",
        "Shared catalogue/stock/pricing with back office"],
        settings=["Payment providers", "Delivery methods", "Website settings"]),
    "helpdesk": dict(name="Helpdesk", module="helpdesk", features=[
        "Ticketing, teams, SLA policies, escalation",
        "Channels (email, web form, live chat), knowledge base",
        "Ratings, refunds/returns, timesheets on tickets"],
        settings=["Teams", "SLA policies", "Stages"]),
    "subscription": dict(name="Subscriptions", module="sale_subscription", features=[
        "Recurring plans, automatic invoicing & payment, upsell/downsell",
        "MRR/churn analytics, renewals, closing & reopening"],
        settings=["Subscription plans", "Recurring pricelists"]),
    "sign": dict(name="Sign / Approvals / Documents", module="sign", features=[
        "E-signature requests & templates (Sign)",
        "Generic approval requests & types (Approvals)",
        "Document management, workspaces, workflows (Documents)"],
        settings=["Sign templates", "Approval types", "Document workspaces"]),
    "studio": dict(name="Studio (no-code)", module="studio", features=[
        "Add fields, edit views/forms/lists/kanban, menus & models",
        "Automated actions & simple server actions (no Python)",
        "Report designer (QWeb) & PDF layouts, approval rules",
        "Use BEFORE custom code for tailoring that isn't config"],
        settings=["Custom fields/views", "Automations", "Report designer"]),
    "automation": dict(name="Automation", module="base_automation", features=[
        "No-code automated actions on create/write/time/stage conditions",
        "Server actions: set field, create/update record, send email, webhook",
        "Scheduled actions (cron) for recurring logic"],
        settings=["Automation rules", "Scheduled actions"]),
}

# extra apps worth naming for completeness (feature-lite)
ALSO = {
    "sale_renting": "Rental — rental orders, durations, availability, pricing.",
    "industry_fsm": "Field Service — on-site tasks, scheduling, worksheets.",
    "appointment": "Appointments — online booking with availability rules.",
    "quality": "Quality — control points, checks, alerts on operations.",
    "maintenance": "Maintenance — equipment, preventive/corrective requests.",
    "marketing_automation": "Marketing Automation — campaigns, drip flows, scoring.",
    "mass_mailing": "Email Marketing — mailing lists, campaigns, A/B, analytics.",
    "event": "Events — registration, tracks, tickets, online events.",
    "documents": "Documents — DMS workspaces, workflows, sharing.",
    "planning": "Planning — shift planning, resource scheduling.",
    "l10n_ae": "UAE localization — CoA, 5% VAT, FTA report.",
    "l10n_sa": "Saudi localization — ZATCA/Fatoora e-invoicing.",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower())


def covered_by(requirement: str) -> list:
    """Which standard apps/features plausibly cover a requirement — used to prove
    a standard path before considering custom."""
    t = _norm(requirement)
    hits = []
    for key, app in STANDARD.items():
        blob = _norm(app["name"] + " " + " ".join(app["features"]) + " " + " ".join(app["settings"]))
        score = sum(1 for w in set(re.findall(r"[a-z]{4,}", t)) if w in blob)
        if score >= 2:
            hits.append({"app": app["name"], "module": app["module"], "score": score,
                         "features": app["features"][:3]})
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:3]


def digest() -> str:
    """Compact standard-features reference to embed in agent prompts."""
    lines = [f"- {a['name']} ({a['module']}): " + "; ".join(a["features"][:4])
             for a in STANDARD.values()]
    also = "; ".join(ALSO.values())
    return ("ODOO STANDARD FUNCTIONALITY REFERENCE (v17–v19) — the house rule is "
            "STANDARD-FIRST: fully exhaust standard configuration, then Studio (no-code), "
            "before proposing ANY custom code. Standard Odoo already covers:\n"
            + "\n".join(lines) + "\nAlso standard/enterprise: " + also +
            "\nWhen analysing a requirement: (1) name the standard capability & settings "
            "that meet it, (2) if partly met, use Studio/automation, (3) ONLY if neither "
            "works, specify a minimal custom module on TOP of standard — never replacing it.")


def full_reference() -> list:
    """The detailed catalog (for a reference view / document)."""
    out = []
    for a in STANDARD.values():
        out.append({"app": a["name"], "module": a["module"],
                    "features": a["features"], "settings": a["settings"]})
    return out
