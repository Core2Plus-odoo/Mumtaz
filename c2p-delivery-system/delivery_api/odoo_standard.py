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
    "payroll": dict(name="Payroll", module="hr_payroll", features=[
        "Salary structures, rules & structure types per country",
        "Payslips (batches), inputs, allowances/deductions, end-of-service",
        "Contracts drive pay; integrates Time Off, Attendance, Work Entries",
        "Posts to accounting; bank/WPS/SIF payment file export"],
        settings=["Salary structures", "Salary rules", "Work entry types", "Payslip batches"]),
    "rental": dict(name="Rental", module="sale_renting", features=[
        "Rental orders with durations, pickup/return, availability calendar",
        "Time-based pricing (hour/day/week), late fees, security deposits",
        "Stock reservation for rented products, condition checks"],
        settings=["Rental pricing", "Return/late fees", "Rentable products"]),
    "fsm": dict(name="Field Service", module="industry_fsm", features=[
        "On-site tasks, scheduling & dispatch, mobile worksheets",
        "Track time & materials on task, sign-off, invoice from task",
        "Recurring interventions, GPS/route, product usage on-site"],
        settings=["Worksheet templates", "Task types", "Billing from tasks"]),
    "quality": dict(name="Quality", module="quality_control", features=[
        "Control points on receipts/manufacturing/delivery operations",
        "Check types (pass-fail, measure, picture, instructions)",
        "Quality alerts, root-cause, non-conformance workflow"],
        settings=["Control points", "Quality teams", "Check types"]),
    "maintenance": dict(name="Maintenance", module="maintenance", features=[
        "Equipment register, preventive & corrective requests",
        "Maintenance teams, stages, calendar & Kanban, MTBF/MTTR KPIs",
        "Trigger from Manufacturing/Quality; scheduled preventive plans"],
        settings=["Equipment categories", "Maintenance teams", "Preventive frequency"]),
    "marketing": dict(name="Marketing", module="marketing_automation", features=[
        "Email/SMS marketing: lists, segmentation, A/B, analytics (mass_mailing)",
        "Automation flows: multi-step drip campaigns with conditions & scoring",
        "Landing pages/forms, UTM tracking, lead nurturing to CRM"],
        settings=["Mailing lists", "Campaigns", "Marketing flows"]),
    "events": dict(name="Events", module="event", features=[
        "Event registration, multiple ticket types, online & on-site",
        "Tracks/agenda, sponsors, badges, check-in (barcode)",
        "Sell tickets via eCommerce, email/SMS reminders, community"],
        settings=["Event types", "Ticket types", "Registration questions"]),
    "documents": dict(name="Documents (DMS)", module="documents", features=[
        "Workspaces with access rights, tags, versions & split/merge",
        "Automated workflows/actions on files (approve, create record)",
        "Capture from email/scan; share links; e-sign integration"],
        settings=["Workspaces", "Tags", "File workflows"]),
    "knowledge": dict(name="Knowledge", module="knowledge", features=[
        "Nested articles, rich content, templates, item/kanban embeds",
        "Access control, favourites, search; internal + shared articles"],
        settings=["Articles", "Access rights", "Templates"]),
    "planning": dict(name="Planning", module="planning", features=[
        "Shift planning by role/resource, templates & recurrences",
        "Publish/send shifts, open shifts, workload & availability",
        "Integrates timesheets, sales orders (plan billable work)"],
        settings=["Roles", "Shift templates", "Working schedules"]),
    "elearning": dict(name="eLearning", module="website_slides", features=[
        "Courses, lessons (video/PDF/quiz), certifications & badges",
        "Paid courses via eCommerce, forums, progress tracking"],
        settings=["Courses", "Certification", "Access rules"]),
    "barcode": dict(name="Barcode", module="stock_barcode", features=[
        "Barcode-driven receipts, deliveries, transfers, inventory counts",
        "Scan lots/serials & locations; batch/cluster picking on device"],
        settings=["Barcode nomenclature", "Operation defaults"]),
    "dashboards": dict(name="Spreadsheet & Dashboards", module="spreadsheet_dashboard",
        features=[
        "Live spreadsheets on Odoo data (pivot, formulas, charts)",
        "Shareable dashboards; insert list/pivot from any report",
        "The standard route for custom management reporting layouts"],
        settings=["Dashboards", "Spreadsheet templates"]),
}

# extra apps worth naming for completeness (feature-lite)
ALSO = {
    "appointment": "Appointments — online booking with availability rules.",
    "timesheet": "Timesheets — time logging on tasks; feeds billing & payroll.",
    "expense": "Expenses — claims, approval, reimbursement, reinvoicing.",
    "recruitment": "Recruitment — job posts, application pipeline, referrals.",
    "appraisal": "Appraisals — review cycles, goals, 360 feedback.",
    "fleet": "Fleet — vehicles, contracts, costs, assignments.",
    "lunch": "Lunch — internal meal ordering & vendor management.",
    "iot": "IoT — connect scales, printers, scanners, cameras to Odoo.",
    "whatsapp": "WhatsApp — templated messaging integrated with records.",
    "voip": "VoIP — click-to-call, call queues from CRM/Helpdesk.",
    "l10n_ae": "UAE localization — CoA, 5% VAT, FTA report, e-invoicing (2026).",
    "l10n_sa": "Saudi localization — CoA, 15% VAT, ZATCA/Fatoora e-invoicing.",
    "l10n_pk": "Pakistan localization — CoA and tax scaffolding (FBR).",
}

# app key -> the customisations clients TYPICALLY ask for beyond config, and the
# right standard-first route. Used to pre-empt over-eager custom verdicts:
# most of these are Studio/automation, not custom code.
COMMON_CUSTOMS = {
    "crm": [("Custom lead qualification fields/score", "studio + automation"),
            ("Approval on discount/quotation", "approvals / automation"),
            ("Territory or product-based auto-assignment", "automation rules")],
    "sale": [("Bespoke quotation PDF layout", "studio report designer"),
             ("Multi-level quote approval by margin/amount", "approvals"),
             ("Custom pricing beyond pricelist rules", "custom (thin, on top)")],
    "purchase": [("Extra approval tiers / delegation", "approvals / automation"),
                 ("Vendor scorecard fields", "studio")],
    "stock": [("Custom picking/label formats", "studio report designer"),
              ("Special reservation/allocation logic", "custom (route + rules first)"),
              ("Barcode flow tweaks", "barcode config / studio")],
    "mrp": [("Shop-floor terminal tweaks", "studio"),
            ("Custom costing beyond std/AVCO/FIFO", "analytic + custom (last resort)")],
    "account": [("Statutory report layouts (P&L/BS)", "spreadsheet dashboards / studio"),
                ("Localised e-invoicing formats", "localization module / EDI"),
                ("CT / deferred-tax computation", "analytic + provision JE")],
    "project": [("Custom billing rules", "config first, then thin custom"),
                ("Client-specific task portal fields", "studio")],
    "hr": [("Local contract/leave rules", "config + studio"),
           ("Custom appraisal templates", "studio")],
    "payroll": [("Country salary rules (EOSB, WPS)", "salary rules config first"),
                ("Custom payslip layout", "studio report designer")],
    "pos": [("Custom receipt/loyalty rules", "config + studio"),
            ("Hardware/IoT integration", "iot / interface module")],
    "website": [("Bespoke theme/blocks", "website builder + snippets"),
                ("Custom checkout steps", "studio / thin custom")],
}


def common_customs(app_key: str) -> list:
    """Typical customisations for an app and the standard-first route each takes."""
    return [{"ask": a, "route": r} for a, r in COMMON_CUSTOMS.get(app_key, [])]


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
    customs = "; ".join(
        f"{STANDARD[k]['name']}: " + ", ".join(f"{a}→{r}" for a, r in v[:2])
        for k, v in COMMON_CUSTOMS.items() if k in STANDARD)
    return ("ODOO STANDARD FUNCTIONALITY REFERENCE (v17–v19) — the house rule is "
            "STANDARD-FIRST: fully exhaust standard configuration, then Studio (no-code), "
            "before proposing ANY custom code. Standard Odoo already covers:\n"
            + "\n".join(lines) + "\nAlso standard/enterprise: " + also +
            "\nCommonly-asked 'customs' that are really config/Studio: " + customs +
            "\nWhen analysing a requirement: (1) name the standard capability & settings "
            "that meet it, (2) if partly met, use Studio/automation, (3) ONLY if neither "
            "works, specify a minimal custom module on TOP of standard — never replacing it.")


def full_reference() -> list:
    """The detailed catalog (for a reference view / document)."""
    out = []
    for key, a in STANDARD.items():
        out.append({"app": a["name"], "module": a["module"],
                    "features": a["features"], "settings": a["settings"],
                    "common_customs": common_customs(key)})
    return out
