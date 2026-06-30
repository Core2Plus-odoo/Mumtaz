"""Built-in Odoo intelligence — curated, deterministic knowledge so the agency
classifies routine requirements WITHOUT an API call.

The functional consultant's job is largely pattern recognition against known Odoo
capability: "CRM pipeline stages" is always standard-configurable, "tiered
loyalty accrual" is always a custom build. That knowledge lives here as rules, so
clear-cut requirements are resolved instantly and for free; only genuinely novel
or ambiguous ones fall through to the model.

`classify(requirement)` returns a functional-stage-shaped result plus a
confidence, so the output is a drop-in for the LLM path and renders identically.
Knowledge is current to Odoo v17–v19 (UAE/GCC defaults).
"""
from __future__ import annotations

import re
from typing import Optional

# --------------------------------------------------------------------------- #
# Odoo capability map — what standard/enterprise modules cover (v17–v19).
# --------------------------------------------------------------------------- #
MODULES = {
    "crm": "Leads, opportunities, multi-team pipelines, configurable stages, lost reasons, activities.",
    "sale_management": "Quotations, sales orders, pricelists, discounts, optional/upsell products.",
    "account": "Invoicing, taxes, journals, payments, analytic accounting, multi-company consolidation.",
    "l10n_ae": "UAE chart of accounts, 5% VAT, FTA tax report.",
    "l10n_sa": "Saudi localization, ZATCA/Fatoora e-invoicing (Phase 1 & 2).",
    "stock": "Warehouses, internal transfers, reordering rules (min/max), lots/serials, routes.",
    "purchase": "RFQs, purchase orders, vendor pricelists, reordering, vendor bills.",
    "mrp": "Bills of materials, work orders, work centres, manufacturing orders, routings.",
    "project": "Projects, task stages, sub-tasks, milestones; timesheets via hr_timesheet.",
    "hr": "Employees, departments, org chart; recruitment, appraisals, time-off, expenses via apps.",
    "hr_payroll": "Payroll rules, payslips (localized rules vary by country).",
    "point_of_sale": "POS sessions, payment methods, receipts, offline mode, restaurant.",
    "loyalty": "Coupons, promotions, gift cards, simple loyalty (points/discount) in Sales & POS.",
    "website_sale": "eCommerce storefront, online catalogue, cart, online payments.",
    "website": "CMS pages, forms, customer portal building blocks.",
    "portal": "Customer/vendor self-service portal (quotes, invoices, tasks, tickets).",
    "helpdesk": "Ticketing, SLA policies, teams (enterprise).",
    "documents": "Document management, workspaces, workflows (enterprise).",
    "sign": "E-signature requests (enterprise).",
    "approvals": "Generic approval requests/types (enterprise).",
    "base_automation": "No-code automated actions / server actions on record events.",
    "studio": "Odoo Studio — no-code fields, views, simple automations, basic reports (enterprise).",
    "subscription": "Recurring sales / subscriptions (enterprise: sale_subscription).",
    "sale_renting": "Rental orders, durations, pricing.",
    "industry_fsm": "Field Service — on-site tasks, scheduling (enterprise).",
    "appointment": "Online appointment booking (enterprise).",
    "stock_barcode": "Barcode scanning for warehouse operations (enterprise).",
}


def _m(*names) -> list:
    return [{"name": n, "version_note": MODULES.get(n, "")} for n in names]


# --------------------------------------------------------------------------- #
# Classification rules. Each: trigger keywords, the Odoo answer, verdict, effort.
# `strong` keywords give a confident match on their own; `weak` add weight.
# `block` keywords veto the rule (disambiguation).
# --------------------------------------------------------------------------- #
RULES = [
    # ---- CRM ----------------------------------------------------------------
    dict(id="crm_pipeline", strong=["pipeline", "crm stage", "sales stage", "lead stage",
         "opportunity stage", "sales funnel", "kanban stage"],
         weak=["lead", "opportunity", "crm", "stage", "source", "won", "lost"],
         modules=_m("crm"), verdict="configurable", effort="Low",
         desc="Standard CRM provides configurable pipelines, stages, lead sources, lost reasons and activities.",
         path="Configure CRM pipeline stages, a lead-source field/tag set, and activity types — no code."),
    dict(id="crm_followup", strong=["follow-up activity", "auto-schedule activity",
         "automated follow up", "activity reminder", "next activity"],
         weak=["follow up", "activity", "reminder", "overdue", "sla"],
         modules=_m("crm", "base_automation"), verdict="configurable", effort="Medium",
         desc="Activity types plus a no-code automated action schedule follow-ups on stage/time conditions.",
         path="Use Automated Actions (base_automation) to create the follow-up activity on the trigger condition."),
    # ---- Sales / pricing ----------------------------------------------------
    dict(id="pricelist", strong=["pricelist", "price list", "tiered pricing", "volume discount",
         "customer-specific price", "quantity discount"],
         weak=["price", "discount", "margin"],
         modules=_m("sale_management"), verdict="standard", effort="Low",
         desc="Sales pricelists support customer/quantity/date rules and discounts out of the box.",
         path="Configure pricelists with the required rules; no development."),
    dict(id="quotation", strong=["quotation template", "quote template", "sales order workflow",
         "optional products", "upsell"],
         weak=["quotation", "quote", "sales order", "proposal"],
         modules=_m("sale_management"), verdict="standard", effort="Low",
         desc="Quotation templates, optional/upsell lines and order confirmation are standard.",
         path="Set up quotation templates and product configuration."),
    # ---- Loyalty ------------------------------------------------------------
    dict(id="loyalty_simple", strong=["loyalty program", "loyalty points", "reward points",
         "gift card", "coupon", "promotion"],
         weak=["loyalty", "points", "reward", "voucher"],
         block=["tier", "tiered", "multi-level", "complex accrual", "partner accrual"],
         modules=_m("loyalty", "point_of_sale"), verdict="configurable", effort="Medium",
         desc="Standard Loyalty/Coupons covers points, discounts, gift cards and promotions in Sales & POS.",
         path="Configure a Loyalty program (earn/spend rules) — no code for standard point/discount schemes."),
    dict(id="loyalty_tiered", strong=["tiered loyalty", "loyalty tier", "membership tier",
         "multi-level loyalty", "tier accrual", "points per aed with tier"],
         weak=["tier", "tiered", "platinum", "gold tier", "silver tier"],
         modules=_m("loyalty"), verdict="custom", effort="High",
         desc="Standard loyalty has no multi-tier accrual/benefit engine; tier logic needs a module.",
         path="Build a custom module extending loyalty with tier definitions, accrual rates and benefits.",
         design="New model loyalty.tier (thresholds, accrual multiplier, benefits); extend loyalty.program and POS/sale order to apply tier on the partner; scheduled re-evaluation of tiers."),
    # ---- Inventory ----------------------------------------------------------
    dict(id="reordering", strong=["reordering rule", "min max", "minimum stock", "replenish",
         "reorder point", "auto purchase", "stock replenishment"],
         weak=["reorder", "replenishment", "stock level", "safety stock"],
         modules=_m("stock", "purchase"), verdict="configurable", effort="Low",
         desc="Reordering rules (min/max) auto-create internal transfers or POs to replenish stock.",
         path="Configure reordering rules per product/warehouse; enable buy/manufacture routes."),
    dict(id="multi_warehouse", strong=["multi warehouse", "multiple warehouses", "inter-warehouse",
         "internal transfer", "branch stock", "central distribution"],
         weak=["warehouse", "transfer", "dc", "depot", "branch"],
         modules=_m("stock"), verdict="configurable", effort="Medium",
         desc="Multi-warehouse, routes and internal transfers are standard inventory capability.",
         path="Configure warehouses, routes and resupply rules; no code."),
    dict(id="lots_serials", strong=["lot tracking", "serial number", "batch tracking",
         "expiry date", "traceability"],
         weak=["lot", "serial", "batch", "expiry", "traceab"],
         modules=_m("stock"), verdict="standard", effort="Low",
         desc="Lots/serial tracking, expiration dates and full traceability are standard.",
         path="Enable tracking on products and turn on expiration where needed."),
    dict(id="barcode", strong=["barcode scan", "barcode scanning", "handheld scanner"],
         weak=["barcode", "scanner", "scan"],
         modules=_m("stock_barcode"), verdict="standard", effort="Low",
         desc="The Barcode app (enterprise) covers warehouse scanning operations.",
         path="Install/enable Barcode; no development for standard flows."),
    # ---- Purchase -----------------------------------------------------------
    dict(id="purchase", strong=["purchase order", "rfq", "request for quotation",
         "vendor management", "procurement"],
         weak=["purchase", "vendor", "supplier", "procure"],
         modules=_m("purchase"), verdict="standard", effort="Low",
         desc="RFQs, POs, vendor pricelists and bill control are standard Purchase.",
         path="Configure Purchase, vendor pricelists and approval limits."),
    # ---- Accounting / Finance ----------------------------------------------
    dict(id="uae_vat", strong=["5% vat", "uae vat", "fta", "vat return", "tax report"],
         weak=["vat", "tax", "l10n", "emirates tax"],
         modules=_m("account", "l10n_ae"), verdict="standard", effort="Low",
         desc="UAE localization provides the CoA, 5% VAT taxes and the FTA tax report.",
         path="Install l10n_ae, set taxes/fiscal positions; no code."),
    dict(id="multi_company", strong=["multi company", "multi-company", "consolidation",
         "consolidated p&l", "inter-company", "multiple entities"],
         weak=["entity", "entities", "company", "consolidat", "branch accounts"],
         modules=_m("account"), verdict="configurable", effort="Medium",
         desc="Multi-company with inter-company rules and consolidated reporting is standard.",
         path="Configure companies, inter-company rules and consolidation; no code."),
    dict(id="zatca", strong=["zatca", "fatoora", "saudi e-invoic", "ksa e-invoic",
         "e-invoice ksa", "phase 2 e-invoic"],
         weak=["ksa", "saudi", "e-invoice", "einvoice"],
         modules=_m("l10n_sa"), verdict="studio", effort="Medium",
         desc="Saudi e-invoicing is delivered by l10n_sa; some integration/config may be needed.",
         path="Enable l10n_sa ZATCA features; configure devices/certificates. Localization, not bespoke code."),
    dict(id="payment_gateway", strong=["payment gateway", "online payment", "card payment integration",
         "stripe", "telr", "network international", "payment provider"],
         weak=["gateway", "checkout", "acquirer", "payment integration"],
         modules=_m("website_sale", "account"), verdict="configurable", effort="Medium",
         desc="Supported payment providers are configurable; an unsupported local gateway needs a connector.",
         path="Use a built-in payment provider if available; otherwise a custom acquirer module."),
    # ---- Manufacturing ------------------------------------------------------
    dict(id="manufacturing", strong=["bill of material", "bom", "work order", "work center",
         "manufacturing order", "production order", "routing"],
         weak=["manufactur", "production", "assembly", "mrp"],
         modules=_m("mrp"), verdict="standard", effort="Medium",
         desc="BoMs, routings, work orders and MOs are standard Manufacturing.",
         path="Configure MRP: BoMs, work centres and routings."),
    # ---- HR -----------------------------------------------------------------
    dict(id="hr_core", strong=["employee record", "org chart", "leave management",
         "time off", "expense claim", "attendance"],
         weak=["employee", "hr", "leave", "payroll", "appraisal", "recruit"],
         modules=_m("hr"), verdict="standard", effort="Low",
         desc="Employees, time-off, expenses, attendance and recruitment are standard HR apps.",
         path="Install the relevant HR apps and configure policies."),
    # ---- Project ------------------------------------------------------------
    dict(id="project", strong=["project task", "task stage", "milestone", "timesheet",
         "gantt", "project management"],
         weak=["project", "task", "kanban", "deadline"],
         modules=_m("project"), verdict="standard", effort="Low",
         desc="Projects, task stages, milestones and timesheets are standard.",
         path="Configure project stages and enable timesheets."),
    # ---- POS / eCommerce ----------------------------------------------------
    dict(id="pos", strong=["point of sale", "pos terminal", "cashier", "pos session",
         "offline pos", "receipt printer"],
         weak=["pos", "till", "checkout counter", "store sale"],
         modules=_m("point_of_sale"), verdict="standard", effort="Medium",
         desc="POS sessions, payment methods, receipts and offline mode are standard.",
         path="Configure POS, payment methods and receipts."),
    dict(id="ecommerce", strong=["ecommerce", "e-commerce", "online store", "web shop",
         "online catalogue", "website cart"],
         weak=["website", "online", "storefront", "cart"],
         modules=_m("website_sale"), verdict="standard", effort="Medium",
         desc="The eCommerce app provides storefront, catalogue, cart and online payment.",
         path="Configure website_sale: catalogue, delivery and payment."),
    dict(id="portal", strong=["customer portal", "self-service portal", "vendor portal",
         "client portal"],
         weak=["portal", "self service", "self-service"],
         modules=_m("portal"), verdict="standard", effort="Low",
         desc="The customer portal exposes quotes, orders, invoices, tasks and tickets.",
         path="Enable portal access; no code for standard documents."),
    # ---- Cross-cutting patterns --------------------------------------------
    dict(id="approval", strong=["approval workflow", "multi-level approval", "approval matrix",
         "sign off", "authorization workflow"],
         weak=["approval", "approve", "authorisation", "authorization"],
         modules=_m("approvals", "base_automation", "studio"), verdict="configurable", effort="Medium",
         desc="Approval app + automated actions cover most approval flows; complex matrices may need Studio.",
         path="Use the Approvals app or automated actions; Studio for bespoke multi-step matrices."),
    dict(id="report", strong=["custom report", "pdf report", "report layout", "printed document",
         "dashboard", "analytics report"],
         weak=["report", "dashboard", "kpi", "analytics", "statement"],
         modules=_m("studio", "account"), verdict="studio", effort="Medium",
         desc="Standard reports + Studio cover most layouts/dashboards; complex computed reports may need code.",
         path="Build with standard reporting / Studio; only deeply computed reports need a QWeb module."),
    dict(id="integration", strong=["api integration", "integrate with", "third-party integration",
         "sync with", "connector", "external system", "middleware", "webhook"],
         weak=["integration", "integrate", "sync", "interface", "api"],
         modules=_m(), verdict="custom", effort="High",
         desc="External-system integration with no native connector requires a custom connector module.",
         path="Build a custom connector (API client, mapping, scheduled/queued sync, error handling).",
         design="Custom module: API client + auth, field mapping models, queue/cron sync, idempotency and error logging; optional webhook controller."),
    dict(id="subscription", strong=["subscription", "recurring billing", "recurring invoice",
         "membership renewal"],
         weak=["recurring", "renewal", "monthly billing"],
         modules=_m("subscription"), verdict="standard", effort="Medium",
         desc="Recurring sales/subscriptions with automated invoicing are standard (enterprise).",
         path="Configure subscription plans and recurring billing."),
    dict(id="rental", strong=["rental", "renting", "equipment hire", "lease item"],
         weak=["rent", "hire", "lease"],
         modules=_m("sale_renting"), verdict="standard", effort="Low",
         desc="The Rental app covers durations, availability and rental pricing.",
         path="Configure rental products and pricing."),
    dict(id="fieldservice", strong=["field service", "on-site service", "technician dispatch",
         "service van"],
         weak=["field", "on site", "technician", "dispatch"],
         modules=_m("industry_fsm"), verdict="standard", effort="Medium",
         desc="Field Service handles on-site tasks, scheduling and worksheets (enterprise).",
         path="Configure Field Service teams and worksheets."),
    dict(id="appointment", strong=["online booking", "appointment booking", "schedule appointment",
         "reservation system"],
         weak=["appointment", "booking", "reservation", "calendar slot"],
         modules=_m("appointment"), verdict="standard", effort="Low",
         desc="The Appointments app provides online booking with availability rules (enterprise).",
         path="Configure appointment types and availability."),
    dict(id="helpdesk", strong=["helpdesk", "support ticket", "ticketing", "sla policy"],
         weak=["ticket", "support", "complaint", "sla"],
         modules=_m("helpdesk"), verdict="standard", effort="Low",
         desc="Helpdesk covers tickets, teams and SLA policies (enterprise).",
         path="Configure Helpdesk teams, stages and SLAs."),
]

_GCC = ("AED defaults, 5% UAE VAT and multi-company are available out of the box; "
        "confirm KSA ZATCA needs separately if any Saudi entity is in scope.")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower())


def _hits(text: str, words) -> int:
    return sum(1 for w in words if w in text)


def _score(text: str, rule: dict):
    if any(b in text for b in rule.get("block", [])):
        return 0.0
    strong = _hits(text, rule.get("strong", []))
    weak = _hits(text, rule.get("weak", []))
    return strong * 1.0 + weak * 0.34


def _options(verdict: str, rule: dict) -> list:
    """Build the A/B/C solution ladder consistently with the verdict."""
    A = {"tier": "A", "label": "Standard configuration", "approach": rule["path"],
         "effort": "Low", "recommended": verdict in ("standard", "configurable"),
         "pros": ["No code", "Upgrade-safe", "Fastest to deliver"], "cons": []}
    B = {"tier": "B", "label": "Studio / automated actions",
         "approach": "No-code fields/views/automation via Studio or automated actions.",
         "effort": "Medium", "recommended": verdict == "studio",
         "pros": ["No Python", "Quick to change"], "cons": ["Limited to Studio's capabilities"]}
    C = {"tier": "C", "label": "Custom module",
         "approach": rule.get("design") or "Bespoke module implementing the required logic.",
         "effort": "High", "recommended": verdict == "custom",
         "pros": ["Exactly fits the requirement"],
         "cons": ["Build + maintenance cost", "Must track Odoo upgrades"]}
    if verdict in ("standard", "configurable"):
        return [A, B]
    if verdict == "studio":
        return [A, B]
    return [A, B, C]


def classify(requirement: str, industry: Optional[str] = None,
             installed_modules: Optional[str] = None) -> dict:
    """Resolve a requirement against built-in Odoo knowledge.

    Returns {"result": <functional-stage dict>|None, "confidence": 0..1,
    "matched": rule_id|None}. High confidence ⇒ no API call is needed.
    """
    text = _norm(requirement)
    if not text:
        return {"result": None, "confidence": 0.0, "matched": None}
    scored = sorted(((_score(text, r), r) for r in RULES), key=lambda x: x[0], reverse=True)
    top_score, top = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    if top_score <= 0:
        return {"result": None, "confidence": 0.0, "matched": None}

    # Confidence: a strong keyword hit (>=1.0) with clear separation is decisive.
    margin = top_score - second
    confidence = min(1.0, 0.45 + 0.4 * min(top_score, 2.0) / 2.0 + 0.15 * min(margin, 1.0))
    if top_score < 1.0:                       # only weak hits — let the model decide
        confidence = min(confidence, 0.5)

    verdict = top["verdict"]
    cap = top.get("modules", [])
    result = {
        "requirement_summary": requirement.strip()[:240],
        "verdict": verdict,
        "verdict_rationale": top["desc"],
        "standard_capability": {
            "available": verdict != "custom",
            "modules": cap,
            "description": top["desc"],
        },
        "gap_analysis": ("Met by standard configuration." if verdict in ("standard", "configurable")
                         else "Needs Studio (no Python)." if verdict == "studio"
                         else "No standard/Studio path covers this — a custom module is required."),
        "solution_options": _options(verdict, top),
        "technical_design": top.get("design") if verdict == "custom" else None,
        "risks": (["Confirm exact business rules before build.",
                   "Custom code must be re-tested on each Odoo upgrade."]
                  if verdict == "custom" else
                  ["Validate the specific configuration values with the client."]),
        "gcc_considerations": _GCC,
        "recommended_path": top["path"],
        "handoff_to_dev": verdict == "custom",
        "source": "knowledge-base",            # marker: resolved with no API call
        "matched_rule": top["id"],
    }
    return {"result": result, "confidence": round(confidence, 2), "matched": top["id"]}
