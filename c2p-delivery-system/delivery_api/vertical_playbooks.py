"""Vertical playbooks — the full FIVE-ROLE view of each industry C2P sells into.

Composes, per vertical, what every role needs on day one:
  Sales & Marketing → the angle, proof points and objections for THIS vertical
  Business Analyst  → the discovery focus areas (from ba_knowledge)
  Project Manager   → typical scope, duration and price band (via pm_knowledge)
  Functional        → processes/pains/modules/KPIs (from industry.py JSON) +
                      the Phase-1 starter configuration
  Technical         → the customs that usually survive standard-first scrutiny

`full_playbook(key)` returns the composed dict; `sales_block(industry)` is a
prompt-ready commercial block injected into the sales-facing agents at call
time. Everything runs locally — no API.
"""
from __future__ import annotations

from typing import Optional

import industry
import ba_knowledge
import pm_knowledge

# Per-vertical commercial + delivery overlay. Keys match industry_playbooks.json.
OVERLAY = {
    "manufacturing": dict(
        sales_angle="Sell shop-floor visibility and material control: quantify scrap, "
                    "stockouts and late orders; demo BoM→MO→cost flow end to end.",
        proof_points=["Live production costing (no more month-end surprises)",
                      "Reorder-triggered purchasing kills material stockouts",
                      "OEE/scrap dashboards from day one"],
        typical_reqs=22, phase1="Inventory + Purchase + Manufacturing core; finance next.",
        config_starter=["Warehouses/locations & routes", "Products with BoMs & routings",
                        "Work centres", "Reordering rules", "UoM & costing method (FIFO/AVCO)"],
        usual_customs=["Shop-floor tablet tweaks (Studio first)", "Costing/variance reports",
                       "Machine/PLC integration (custom connector)"]),
    "trading_distribution": dict(
        sales_angle="Sell margin & stock truth: landed-cost-correct margins per SKU/customer, "
                    "and one view from PO to delivery. Traders buy speed — show a 6-week Phase 1.",
        proof_points=["Landed costs on every import shipment", "Customer/quantity pricelists",
                      "Reordering that matches supplier lead times"],
        typical_reqs=16, phase1="Purchase + Inventory + Sales with pricelists; finance in wave 2.",
        config_starter=["Vendor pricelists & lead times", "Customer pricelists",
                        "Reordering rules", "Landed cost types", "Delivery routes"],
        usual_customs=["Commission engine (genuine custom)", "B2B price/stock portal beyond standard"]),
    "retail": dict(
        sales_angle="Sell one stock + one customer across stores and web: POS↔stock↔accounting "
                    "in one system. Demo an end-of-day close in minutes.",
        proof_points=["Offline-capable POS with central stock", "Loyalty & promotions built in",
                      "eCommerce sharing the same catalogue/stock"],
        typical_reqs=18, phase1="POS + Inventory + Accounting for wave-1 stores; eCommerce wave 2.",
        config_starter=["POS configs & payment methods", "Store warehouses + replenishment",
                        "Pricelists & promotions/loyalty", "Product categories & barcodes"],
        usual_customs=["Tiered loyalty engines", "Local payment-gateway connectors"]),
    "fmcg": dict(
        sales_angle="Sell van-sales discipline and expiry control: route accounting, FEFO, "
                    "trade promotions. Distributors feel expiry write-offs — quantify them.",
        proof_points=["FEFO + expiry tracking end to end", "Van/route sales workflows",
                      "Trade promo accruals visible"],
        typical_reqs=20, phase1="Inventory (lots/FEFO) + Sales/Van + Purchase; promos wave 2.",
        config_starter=["Lots + expiration + FEFO removal", "Route/van warehouses",
                        "Customer pricelists & promo rules", "Reordering by depot"],
        usual_customs=["Van-sales mobile flows beyond standard", "Trade-promotion settlement engine"]),
    "food_beverage": dict(
        sales_angle="Sell recipe cost truth and outlet control: theoretical vs actual food cost, "
                    "central kitchen → outlets, POS with kitchen printing.",
        proof_points=["Recipe/BoM costing per dish", "Central kitchen replenishment",
                      "POS with kitchen display/printers"],
        typical_reqs=18, phase1="POS(restaurant) + Inventory + central-kitchen MRP-lite.",
        config_starter=["Restaurant POS + floors/printers", "Recipes as BoMs/kits",
                        "Outlet warehouses + transfers", "Waste/scrap reasons"],
        usual_customs=["Aggregator (Talabat/Deliveroo) order integration", "Advanced menu engineering reports"]),
    "construction_contracting": dict(
        sales_angle="Sell project cost control: budget vs committed vs actual per project, "
                    "progress billing and retention — the numbers contractors fight over.",
        proof_points=["Project P&L with committed costs (POs) visible",
                      "Progress/milestone invoicing with retention",
                      "Subcontractor tracking"],
        typical_reqs=24, phase1="Projects + Purchase + analytic accounting; payroll/equipment later.",
        config_starter=["Analytic plans per project", "Project templates & task stages",
                        "Milestone invoicing", "Approval thresholds on POs"],
        usual_customs=["Retention handling on invoices/bills", "IPC (payment-certificate) documents",
                       "Equipment/plant costing"]),
    "healthcare": dict(
        sales_angle="Sell inventory + billing discipline for clinics/pharmacy: batch/expiry, "
                    "insurance vs cash billing split, purchasing control. (Clinical EMR stays out of scope.)",
        proof_points=["Pharmacy batch/expiry control", "Insurance/cash split billing",
                      "Consumables cost per department (analytic)"],
        typical_reqs=16, phase1="Inventory (lots/expiry) + Purchase + Invoicing; HR wave 2.",
        config_starter=["Lots + expiry + FEFO", "Departments as analytic accounts",
                        "Patient/insurer partner categories", "Approval on purchases"],
        usual_customs=["Insurance-claim submission formats", "EMR/LIS integration (custom connector)"]),
    "professional_services": dict(
        sales_angle="Sell utilisation and project margin: timesheet→invoice with zero leakage, "
                    "T&M vs fixed-fee visibility per engagement.",
        proof_points=["Timesheets flow straight to invoices", "Project margin live, not at year-end",
                      "Retainers/subscriptions automated"],
        typical_reqs=12, phase1="Projects + Timesheets + Sales/Invoicing; CRM alongside.",
        config_starter=["Project templates & billing types", "Employee cost/sale rates",
                        "Timesheet policies", "Retainer subscription plans"],
        usual_customs=["Complex partner/principal commission splits", "Client portals beyond standard"]),
    "automotive": dict(
        sales_angle="Sell bay utilisation and parts margin: job cards with parts+labour, "
                    "VIN history, counter sales of spares — one system for workshop & trade.",
        proof_points=["Job cards: labour + parts costed per vehicle", "Vehicle/VIN service history",
                      "Spare-parts pricing tiers (retail/trade)"],
        typical_reqs=16, phase1="Repairs/job-cards on Projects or FSM + Inventory + POS for counter sales.",
        config_starter=["Vehicle records on partners (Studio fields)", "Service products & labour rates",
                        "Parts categories & tiered pricelists", "Workshop task stages"],
        usual_customs=["Full job-card documents", "Insurance-repair estimation formats"]),
    "logistics": dict(
        sales_angle="Sell billable-service capture: every handling/storage/transport activity "
                    "billed, WMS-grade ops without WMS-grade licence costs.",
        proof_points=["Storage & handling charges auto-billed", "3PL client stock ring-fenced (owners)",
                      "Fleet costs per trip/vehicle"],
        typical_reqs=18, phase1="Inventory (multi-owner) + Sales/billing + Fleet basics.",
        config_starter=["Locations per client (consignee)", "Service products for handling/storage",
                        "Analytic per client/route", "Fleet vehicles & costs"],
        usual_customs=["Client WMS portals / EDI integration", "Trip/route costing engines"]),
    "real_estate": dict(
        sales_angle="Sell portfolio cash-flow control: leases with schedules, PDC handling, "
                    "service-charge billing and owner statements.",
        proof_points=["Lease contracts with rent schedules & escalation", "PDC lifecycle tracked",
                      "Owner/portfolio P&L via analytic"],
        typical_reqs=14, phase1="Rental/subscription contracts + Invoicing + analytic; maintenance wave 2.",
        config_starter=["Properties/units as products or rental assets", "Lease plans (subscription/rental)",
                        "Analytic per property/owner", "Payment terms incl. PDC flow"],
        usual_customs=["PDC (post-dated cheque) management", "RERA/Ejari document formats",
                       "Owner-statement reports"]),
}


def full_playbook(key: str) -> Optional[dict]:
    """Compose the five-role playbook for a vertical. None if unknown."""
    base = industry.get(key)
    if not base:
        return None
    ov = OVERLAY.get(key, {})
    reqs = ov.get("typical_reqs", 16)
    sized = pm_knowledge.estimate([{"odoo_fit": "configurable"}] * reqs)
    pr = sized.get("pricing", {})
    return {
        "key": key, "name": base["name"],
        "sales": {
            "angle": ov.get("sales_angle", ""),
            "proof_points": ov.get("proof_points", []),
            "pains_to_quantify": base.get("common_pains", [])[:4],
        },
        "ba": {
            "focus_areas": ba_knowledge.focus_areas(base["name"]),
            "key_processes": base.get("key_processes", []),
            "kpis": base.get("typical_kpis", []),
        },
        "pm": {
            "typical_requirements": reqs,
            "duration_weeks": sized.get("duration_weeks"),
            "effort_man_days": sized.get("total_man_days"),
            "price_band_aed": pr.get("range_aed"),
            "phase1": ov.get("phase1", ""),
        },
        "functional": {
            "modules": base.get("odoo_modules", {}),
            "gcc_localization": base.get("gcc_localization", ""),
            "config_starter": ov.get("config_starter", []),
        },
        "technical": {
            "usual_customs": ov.get("usual_customs", []) or base.get("common_customizations", []),
            "note": "Everything else standard-first; customs inherit standard models.",
        },
    }


def list_verticals() -> list[dict]:
    return [{"key": k, "name": v["name"], "has_overlay": k in OVERLAY}
            for k, v in ((i["key"], industry.get(i["key"])) for i in industry.list_industries())]


def sales_block(industry_text: Optional[str]) -> str:
    """Prompt-ready commercial block for the sales-facing agents (presales,
    prospect, outreach) — the vertical's angle, proofs and pains to quantify."""
    key = industry.match_industry(industry_text)
    ov = OVERLAY.get(key or "")
    if not ov:
        return ""
    base = industry.get(key) or {}
    pains = "; ".join((base.get("common_pains") or [])[:3])
    return (f"\n\nVERTICAL SALES PLAYBOOK — {base.get('name', key)}:\n"
            f"- Angle: {ov['sales_angle']}\n"
            f"- Proof points: {'; '.join(ov['proof_points'])}\n"
            f"- Pains to quantify in discovery: {pains}\n"
            f"- Typical shape: ~{ov.get('typical_reqs', 16)} requirements; "
            f"Phase 1 = {ov.get('phase1', 'core scope first')}")
