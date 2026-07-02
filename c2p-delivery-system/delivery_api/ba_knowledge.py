"""Built-in Business-Analyst intelligence — a comprehensive Odoo discovery
framework so the BA can run a thorough requirements-gathering exercise with NO
API call.

For every business area it carries the questions a senior BA would ask, the data
to collect, the usual pain points, the KPIs to baseline and the Odoo modules that
answer it. `build_discovery()` assembles a full, industry-aware discovery plan
locally; `digest()` embeds the framework into the BA agent's prompt so the LLM
version is grounded in the same playbook.
"""
from __future__ import annotations

from typing import Optional

# --------------------------------------------------------------------------- #
# Discovery framework — one entry per business area.
# --------------------------------------------------------------------------- #
AREAS = {
    "Sales & CRM": dict(modules=["crm", "sale_management"], core=True,
        questions=[
            "How do leads arrive (web, WhatsApp, referrals, walk-in) and how are they captured today?",
            "What are your sales stages from first contact to won, and who owns each stage?",
            "Do you use quotation templates, pricelists, or customer-specific pricing/discounts?",
            "What approval is needed before a quote or discount goes to a customer?",
            "How are targets set and commissions calculated for the sales team?",
            "What sales reports/KPIs do management look at weekly?"],
        data=["Lead sources list", "Sales stages & lost reasons", "Pricelists & discount rules",
              "Product catalogue with prices", "Sales team structure & targets"],
        pains=["Leads lost / no follow-up", "Manual quotes in Excel", "No pipeline visibility",
               "Inconsistent pricing"],
        kpis=["Lead conversion %", "Average deal size", "Sales cycle length", "Win rate by source"]),
    "Purchasing & Procurement": dict(modules=["purchase", "stock"], core=True,
        questions=[
            "How do you decide what and when to buy — manual, reorder rules, or MRP?",
            "What is the RFQ / PO approval workflow and the value thresholds?",
            "How are vendor prices, lead times and MOQs managed?",
            "How do you three-way match PO ↔ receipt ↔ vendor bill?",
            "Do you import — and need landed cost (freight/duty) on inventory value?"],
        data=["Vendor master + terms", "Approval thresholds", "Vendor pricelists/lead times",
              "Historical purchase volumes"],
        pains=["Stockouts / overstock", "Maverick buying", "Slow approvals", "Price leakage"],
        kpis=["On-time delivery %", "Purchase price variance", "PO cycle time"]),
    "Inventory & Warehouse": dict(modules=["stock"], core=True,
        questions=[
            "How many warehouses/locations, and how does stock move between them?",
            "Do you track lots/serials, expiry, or barcodes?",
            "What replenishment method — min/max reorder rules, make-to-order, buy-to-order?",
            "How are stock counts / cycle counts performed and how often?",
            "What are your peak SKU count and daily transaction volumes?"],
        data=["Location/warehouse layout", "SKU list + tracking policy", "Opening stock",
              "Routes & operation types", "Transaction volumes"],
        pains=["Inaccurate stock", "Manual counts", "No traceability", "Slow picking"],
        kpis=["Stock accuracy %", "Inventory turns", "Days of inventory", "Order fill rate"]),
    "Manufacturing": dict(modules=["mrp"], core=False,
        questions=[
            "Do you make-to-stock or make-to-order, and how complex are your BoMs (multi-level)?",
            "How are work orders, work centres and routings organised on the shop floor?",
            "How do you handle scrap, by-products, and subcontracting?",
            "How is production capacity planned and scheduled?"],
        data=["Bills of materials", "Work centres & routings", "Production volumes", "Subcontractors"],
        pains=["Manual production tracking", "Material shortages", "No shop-floor visibility"],
        kpis=["OEE", "On-time production %", "Scrap rate", "Manufacturing lead time"]),
    "Accounting & Finance": dict(modules=["account", "l10n_ae"], core=True,
        questions=[
            "Which entities/branches and currencies are in scope, and do you consolidate?",
            "What is your chart-of-accounts and cost-centre / analytic structure?",
            "How is VAT handled (5% UAE / 15% KSA) and what statutory reports do you file?",
            "How do you reconcile banks, manage receivables/payables and dunning?",
            "Do you need fixed assets, budgets, deferred revenue or multi-currency revaluation?",
            "What financial statements & management reports are required, and by when?"],
        data=["Chart of accounts", "Entities & currencies", "Tax registrations", "Bank accounts",
              "Opening balances (TB)", "Asset register"],
        pains=["Slow month-end close", "Manual reconciliations", "VAT filing errors",
               "No real-time P&L"],
        kpis=["Days to close", "DSO / DPO", "Cash position accuracy", "Budget variance"]),
    "HR & Payroll": dict(modules=["hr"], core=False,
        questions=[
            "What HR processes are in scope — employees, recruitment, time-off, attendance, appraisals?",
            "Is payroll in scope, and under which country's rules (WPS for UAE)?",
            "How are expenses claimed and approved?"],
        data=["Employee master", "Leave policies", "Payroll rules / WPS", "Org chart"],
        pains=["Manual leave tracking", "Payroll errors", "Paper expense claims"],
        kpis=["Time-to-hire", "Absence rate", "Payroll accuracy"]),
    "Projects & Services": dict(modules=["project"], core=False,
        questions=[
            "How are projects/jobs structured, and do you bill by milestone, T&M, or fixed price?",
            "Do consultants log timesheets, and how does that flow to invoicing and payroll?",
            "How is project profitability tracked?"],
        data=["Project templates", "Billing model", "Timesheet policy", "Rate cards"],
        pains=["Revenue leakage", "No project margin visibility", "Manual timesheets"],
        kpis=["Project margin", "Utilisation %", "On-time delivery %"]),
    "POS & Retail": dict(modules=["point_of_sale"], core=False,
        questions=[
            "How many stores/tills, and do they need offline operation?",
            "What payment methods and receipt/fiscal requirements apply?",
            "Do you run loyalty, promotions or gift cards, and how complex are the rules?"],
        data=["Store list", "Payment methods", "Loyalty rules", "Peak transactions/day"],
        pains=["Disconnected POS & stock", "Manual end-of-day", "No unified customer view"],
        kpis=["Sales per store", "Basket size", "Loyalty redemption %"]),
    "eCommerce & Portal": dict(modules=["website_sale", "portal"], core=False,
        questions=[
            "Do you sell online, and should the store share catalogue/stock/pricing with Odoo?",
            "What online payment and delivery options are required?",
            "Do customers need a self-service portal (orders, invoices, tickets)?"],
        data=["Online catalogue", "Payment/delivery providers", "Portal requirements"],
        pains=["Manual re-keying of web orders", "Stock mismatch online/offline"],
        kpis=["Online conversion %", "Cart abandonment", "Fulfilment time"]),
}

CROSS = {
    "Reporting & BI": ["Which dashboards/KPIs must each department see daily?",
                       "Any board/management pack format to reproduce?"],
    "Integrations": ["Which external systems must Odoo exchange data with (payment, bank, WMS, e-commerce, government)?",
                     "Real-time or batch, and who owns each system?"],
    "Data Migration": ["What master and opening data must migrate (customers, vendors, products, stock, balances)?",
                       "In what format is it today, and how clean is it?"],
    "Security & Access": ["What roles/access levels are needed and any segregation-of-duties rules?",
                          "Any audit or approval-trail requirements?"],
}

INDUSTRY_FOCUS = {
    "manufactur": ["Manufacturing", "Inventory & Warehouse", "Purchasing & Procurement", "Accounting & Finance", "Sales & CRM"],
    "distribut": ["Inventory & Warehouse", "Purchasing & Procurement", "Sales & CRM", "Accounting & Finance"],
    "retail": ["POS & Retail", "Inventory & Warehouse", "Sales & CRM", "Accounting & Finance", "eCommerce & Portal"],
    "trad": ["Inventory & Warehouse", "Purchasing & Procurement", "Sales & CRM", "Accounting & Finance"],
    "servic": ["Projects & Services", "Sales & CRM", "Accounting & Finance", "HR & Payroll"],
    "construc": ["Projects & Services", "Purchasing & Procurement", "Inventory & Warehouse", "Accounting & Finance"],
    "ecommerce": ["eCommerce & Portal", "Inventory & Warehouse", "Sales & CRM", "Accounting & Finance"],
}

_STAKEHOLDERS = [
    {"role": "CEO / Managing Director", "why": "Vision, priorities, sign-off authority"},
    {"role": "Finance Manager / Controller", "why": "CoA, tax, reporting, month-end"},
    {"role": "Operations / Supply-Chain Manager", "why": "Inventory, purchasing, fulfilment"},
    {"role": "Sales Manager", "why": "Pipeline, pricing, targets"},
    {"role": "IT Lead", "why": "Infrastructure, integrations, data, access"},
]


def focus_areas(industry: Optional[str]) -> list:
    ind = (industry or "").lower()
    for key, areas in INDUSTRY_FOCUS.items():
        if key in ind:
            return areas
    return [a for a, v in AREAS.items() if v.get("core")]   # sensible default


def build_discovery(company: str, industry: Optional[str] = None,
                    extra_areas: Optional[list] = None) -> dict:
    """Assemble a comprehensive, industry-aware discovery plan — no API call."""
    names = list(dict.fromkeys(focus_areas(industry) + (extra_areas or [])))
    process_areas = []
    for name in names:
        a = AREAS.get(name)
        if not a:
            continue
        process_areas.append({
            "area": name,
            "why": f"Baseline current process, pains {', '.join(a['pains'][:2])} and KPIs.",
            "questions": a["questions"],
            "data_to_collect": a["data"],
        })
    return {
        "summary": f"Structured Odoo discovery for {company}"
                   + (f" ({industry})" if industry else "")
                   + f": {len(process_areas)} business areas, "
                     "with cross-cutting reporting, integration, migration and access scope.",
        "process_areas": process_areas,
        "stakeholders_to_interview": _STAKEHOLDERS,
        "documents_to_request": sorted({d for n in names for d in AREAS.get(n, {}).get("data", [])})[:14],
        "integrations_to_scope": CROSS["Integrations"],
        "volumes_and_nfr": ["Peak transaction volumes per area", "Number of users by role",
                            "Uptime / performance expectations", "Data residency / compliance"],
        "key_decisions_for_client": [
            "Which entities/branches go live in wave 1?",
            "Standard-Odoo-first: accept best-practice process where it fits?",
            "Reporting pack format and must-have dashboards",
            "Data migration scope (how much history?)"] +
            [q for area in ("Data Migration", "Security & Access") for q in CROSS[area]],
        "source": "ba-knowledge",
    }


def digest() -> str:
    """Compact discovery framework for embedding in the BA agent's prompt."""
    lines = []
    for name, a in AREAS.items():
        lines.append(f"- {name} ({', '.join(a['modules'])}): "
                     f"ask about {a['questions'][0][:70]}…; KPIs {', '.join(a['kpis'][:2])}")
    return ("BA DISCOVERY FRAMEWORK (C2P) — cover every relevant business area; for "
            "each, capture current process, pains, volumes, rules, exceptions and KPIs, "
            "then map to standard Odoo.\n" + "\n".join(lines) +
            "\nAlways scope: reporting/BI, integrations, data migration, security/access.")
