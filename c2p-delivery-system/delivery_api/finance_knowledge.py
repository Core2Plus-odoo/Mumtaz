"""Built-in Chartered-Accountant intelligence — tax, IFRS and compliance.

Encodes the finance knowledge a Big-4-grade Odoo accounting consultant applies by
reflex: GCC/Pakistan VAT regimes, IFRS treatments, e-invoicing/compliance, and
the Odoo accounting modules that deliver them. `advise()` returns the correct
treatment + Odoo mapping + compliance notes for a finance requirement with NO API
call, so accounting requirements are grounded in real standards, not guessed.
"""
from __future__ import annotations

import re
from typing import Optional

# --------------------------------------------------------------------------- #
# Indirect-tax regimes (rates current as of 2026; always confirm at delivery).
# --------------------------------------------------------------------------- #
TAX_REGIMES = {
    "AE": {"name": "United Arab Emirates", "vat": "5%", "authority": "FTA",
           "modules": ["l10n_ae"],
           "notes": "Standard 5% VAT; 0% exports/designated zones; FTA VAT return; "
                    "9% Corporate Tax (since Jun-2023) — track taxable profit; "
                    "UAE e-invoicing programme phasing in from 2026."},
    "SA": {"name": "Saudi Arabia", "vat": "15%", "authority": "ZATCA",
           "modules": ["l10n_sa"],
           "notes": "15% VAT; ZATCA Fatoora e-invoicing Phase 2 (integrated, "
                    "cleared invoices with QR/UUID) is mandatory by waves."},
    "BH": {"name": "Bahrain", "vat": "10%", "authority": "NBR", "modules": ["l10n_bh"],
           "notes": "10% VAT (raised from 5% in 2022)."},
    "OM": {"name": "Oman", "vat": "5%", "authority": "OTA", "modules": ["l10n_om"],
           "notes": "5% VAT since 2021."},
    "QA": {"name": "Qatar", "vat": "none-yet", "authority": "GTA", "modules": [],
           "notes": "No VAT in force yet; monitor GCC framework."},
    "KW": {"name": "Kuwait", "vat": "none-yet", "authority": "—", "modules": [],
           "notes": "VAT not yet implemented."},
    "PK": {"name": "Pakistan", "vat": "17% GST", "authority": "FBR", "modules": ["l10n_pk"],
           "notes": "Sales tax/GST ~18% federal goods (FBR); provincial services "
                    "sales tax (SRB/PRA/KPRA/BRA) 13-16%; FBR/IRIS filing; extensive "
                    "withholding tax regime; annual income-tax return + wealth statement."},
}

# --------------------------------------------------------------------------- #
# Direct / corporate tax regimes (rates as of 2026; confirm at delivery).
# --------------------------------------------------------------------------- #
CORPORATE_TAX = {
    "AE": {"name": "UAE Corporate Tax", "rate": "9%", "authority": "FTA",
           "notes": "0% on taxable income up to AED 375,000, 9% above. Effective for "
                    "financial years starting on/after 1 Jun 2023. Registration is "
                    "mandatory for all taxable persons (deadlines by licence-issue "
                    "month). Qualifying Free Zone Persons (QFZP) may keep 0% on "
                    "qualifying income if substance/de-minimis met. Small Business "
                    "Relief up to AED 3m revenue. 9-month filing/payment window."},
    "SA": {"name": "Saudi Corporate Income Tax / Zakat", "rate": "20% CIT / 2.5% Zakat",
           "authority": "ZATCA",
           "notes": "20% CIT on non-GCC ownership share; 2.5% Zakat on Saudi/GCC "
                    "share of the Zakat base; mixed companies apportion. WHT 5-20% "
                    "on cross-border payments."},
    "QA": {"name": "Qatar Income Tax", "rate": "10%", "authority": "GTA",
           "notes": "10% on foreign-owned share of profits; Qatari/GCC-owned largely "
                    "exempt; WHT 5% on certain cross-border services."},
    "BH": {"name": "Bahrain", "rate": "0% (15% DMTT)", "authority": "NBR",
           "notes": "No general CIT; 15% Domestic Minimum Top-up Tax on large MNEs "
                    "(Pillar Two) from 2025."},
    "PK": {"name": "Pakistan Corporate Tax", "rate": "29%", "authority": "FBR",
           "notes": "29% company rate + super tax on high income; minimum turnover "
                    "tax; separate rates for SMEs/banks; heavy WHT + advance tax."},
}

# --------------------------------------------------------------------------- #
# Regulatory / compliance programmes beyond tax filing.
# --------------------------------------------------------------------------- #
COMPLIANCE = [
    dict(keys=["economic substance", "esr", "substance"],
         name="Economic Substance Regulations (UAE)",
         note="Relevant Activities must meet substance tests and file an ESR "
              "notification + report annually; penalties for non-filing."),
    dict(keys=["transfer pricing", "tp", "arm's length", "related party"],
         name="Transfer Pricing (OECD / UAE CT)",
         note="Related-party transactions at arm's length; maintain Master File / "
              "Local File and a disclosure form where thresholds are met."),
    dict(keys=["country by country", "cbcr", "pillar two", "global minimum"],
         name="CbCR / Pillar Two",
         note="Large MNE groups (>EUR 750m) file CbCR and face a 15% global minimum "
              "tax (DMTT being adopted across the GCC)."),
    dict(keys=["ultimate beneficial", "ubo", "beneficial owner"],
         name="UBO Register",
         note="Maintain and file a register of ultimate beneficial owners with the "
              "licensing authority; keep it current on ownership change."),
    dict(keys=["anti money", "aml", "kyc", "goaml"],
         name="AML / goAML",
         note="DNFBPs register on goAML and file suspicious-transaction reports; "
              "keep KYC and a risk-based AML programme."),
]

# --------------------------------------------------------------------------- #
# IFRS / accounting treatment library.
# --------------------------------------------------------------------------- #
IFRS = [
    dict(keys=["revenue recognition", "ifrs 15", "performance obligation",
               "deferred revenue", "unbilled"],
         std="IFRS 15", treatment="Recognise revenue as performance obligations are "
         "satisfied; defer advance billings as contract liabilities.",
         odoo="Use deferred revenue + analytic; sale_subscription for recurring; "
               "milestone invoicing on projects."),
    dict(keys=["lease", "ifrs 16", "right of use", "rou asset"],
         std="IFRS 16", treatment="Capitalise leases as right-of-use assets with a "
         "lease liability; depreciate ROU and unwind interest.",
         odoo="Model ROU as a fixed asset + a loan/liability schedule; account.asset."),
    dict(keys=["fixed asset", "depreciation", "capitalise", "wdv", "straight line"],
         std="IAS 16", treatment="Capitalise PP&E; depreciate over useful life "
         "(straight-line or reducing balance); review residual/impairment.",
         odoo="account_asset: asset models, depreciation boards, disposal."),
    dict(keys=["inventory valuation", "fifo", "weighted average", "landed cost",
               "lower of cost", "nrv"],
         std="IAS 2", treatment="Value inventory at lower of cost and NRV; FIFO or "
         "weighted-average; include landed costs.",
         odoo="Stock valuation (automated/perpetual), FIFO/AVCO, stock_landed_costs."),
    dict(keys=["foreign currency", "fx", "exchange rate", "multi-currency",
               "revaluation", "unrealised"],
         std="IAS 21", treatment="Record at transaction rate; revalue monetary "
         "balances at period-end; post unrealised FX gain/loss.",
         odoo="Multi-currency + periodic FX revaluation; rate provider/cron."),
    dict(keys=["consolidation", "group accounts", "inter-company", "minority",
               "subsidiary"],
         std="IFRS 10", treatment="Consolidate controlled entities; eliminate "
         "inter-company balances and unrealised profit.",
         odoo="Multi-company + inter-company rules; consolidation via account "
               "groups / external consolidation tool."),
    dict(keys=["provision", "accrual", "contingent", "ias 37"],
         std="IAS 37", treatment="Provide for present obligations that are probable "
         "and measurable; disclose contingencies.",
         odoo="Recurring/manual journal entries; analytic for tracking."),
    dict(keys=["impairment", "ecl", "expected credit loss", "bad debt", "ifrs 9"],
         std="IFRS 9", treatment="Recognise expected credit losses on receivables; "
         "classify/measure financial instruments.",
         odoo="Aged-receivable + follow-up (dunning); manual ECL provision JE."),
    dict(keys=["deferred tax", "current tax", "income tax", "ias 12", "corporate tax"],
         std="IAS 12", treatment="Recognise current tax on taxable profit and "
         "deferred tax on temporary differences (e.g. depreciation, provisions).",
         odoo="Tax journal + deferred-tax accounts; analytic for the CT computation; "
              "book the 9% UAE CT provision at period-end."),
    dict(keys=["employee benefit", "gratuity", "end of service", "eosb", "leave",
               "ias 19", "provident"],
         std="IAS 19", treatment="Provide for end-of-service benefits / gratuity and "
         "accrued leave over the service period; actuarial for large schemes.",
         odoo="EOSB & leave provision journals (recurring); HR/payroll drives the "
              "accrual; disclose the movement."),
    dict(keys=["business combination", "goodwill", "acquisition", "ifrs 3", "ppa"],
         std="IFRS 3", treatment="Measure identifiable assets/liabilities at fair "
         "value at acquisition; recognise goodwill; test it for impairment.",
         odoo="Booked via journals + asset register; consolidation handles the group."),
    dict(keys=["intangible", "software capitalisation", "development cost", "ias 38",
               "amortisation"],
         std="IAS 38", treatment="Capitalise intangibles meeting recognition criteria; "
         "amortise over useful life; expense research.",
         odoo="account_asset for intangibles + amortisation boards."),
    dict(keys=["cash flow statement", "ias 7", "operating investing financing"],
         std="IAS 7", treatment="Present cash flows by operating, investing and "
         "financing (indirect method common).",
         odoo="Standard Cash Flow report; tag accounts to the correct section."),
    dict(keys=["segment", "ifrs 8", "operating segment"],
         std="IFRS 8", treatment="Report performance by operating segment as seen by "
         "the chief operating decision maker.",
         odoo="Analytic plans per segment/branch drive segment reporting."),
]

# --------------------------------------------------------------------------- #
# Common finance processes → Odoo capability.
# --------------------------------------------------------------------------- #
PROCESSES = [
    dict(keys=["bank reconciliation", "bank statement", "reconcile bank"],
         odoo="Bank statement import (CAMT/CSV/OFX) + reconciliation models/rules.",
         fit="configurable"),
    dict(keys=["chart of accounts", "coa", "account structure"],
         odoo="Localized CoA (l10n_*) + account groups; configure, don't build.",
         fit="standard"),
    dict(keys=["cost center", "cost centre", "analytic", "department p&l",
               "project profitability"],
         odoo="Analytic accounting (plans + distribution) for cost centres/projects.",
         fit="configurable"),
    dict(keys=["budget", "budgetary control"],
         odoo="account_budget: budgetary positions vs analytic actuals.",
         fit="configurable"),
    dict(keys=["payment follow", "dunning", "collection", "aged receivable",
               "credit control"],
         odoo="Follow-up levels (dunning) + aged partner reports.",
         fit="configurable"),
    dict(keys=["e-invoice", "einvoice", "e invoicing", "fatoora", "zatca", "peppol"],
         odoo="Localized e-invoicing (l10n_sa ZATCA / EDI / UBL); config + certs.",
         fit="studio"),
    dict(keys=["financial statement", "balance sheet", "profit and loss", "p&l",
               "cash flow", "trial balance"],
         odoo="Standard accounting reports + Studio/spreadsheet for layouts.",
         fit="standard"),
    dict(keys=["withholding tax", "wht", "tax deduction at source"],
         odoo="Withholding tax codes + tax groups; report per regime.",
         fit="configurable"),
    dict(keys=["intercompany", "inter-company invoicing", "ic elimination"],
         odoo="Inter-company rules auto-create the mirror documents.",
         fit="configurable"),
    dict(keys=["gratuity", "end of service", "eosb", "leave provision"],
         odoo="Recurring provision journals driven by HR/payroll; analytic per entity.",
         fit="configurable"),
    dict(keys=["prepayment", "accrual", "deferred expense", "amortise expense"],
         odoo="Deferred expense/revenue models auto-spread over the period.",
         fit="configurable"),
    dict(keys=["petty cash", "expense claim", "employee expense", "reimbursement"],
         odoo="Expenses app: claims, approval, reimbursement, analytic + tax.",
         fit="standard"),
    dict(keys=["deferred tax", "corporate tax provision", "ct computation"],
         odoo="CT provision JE + deferred-tax accounts; analytic to derive taxable "
              "profit from the P&L.",
         fit="configurable"),
    dict(keys=["fixed asset register", "asset register", "capex", "disposal"],
         odoo="account_asset: register, depreciation boards, disposal/scrap, reports.",
         fit="standard"),
    dict(keys=["payroll", "wps", "salary", "sif", "end of service settlement"],
         odoo="Odoo Payroll (localised rules) + WPS/SIF export; posts to accounting.",
         fit="configurable"),
    dict(keys=["month end", "period close", "closing checklist", "lock date"],
         odoo="Closing entries, lock dates, reconciliation status; recurring checklist.",
         fit="configurable"),
    dict(keys=["revenue recognition schedule", "deferred revenue", "unbilled",
               "milestone billing"],
         odoo="Deferred revenue models + milestone/progress invoicing on projects.",
         fit="configurable"),
]


def digest() -> str:
    """A compact CA/finance reference to embed in an agent's system prompt."""
    tax = "; ".join(f"{c} {d['name']} VAT {d['vat']} ({d['authority']})"
                    for c, d in TAX_REGIMES.items())
    ct = "; ".join(f"{c} {d['rate']}" for c, d in CORPORATE_TAX.items())
    ifrs = "; ".join(f"{e['std']} ({e['keys'][0]})" for e in IFRS)
    comp = "; ".join(e["name"] for e in COMPLIANCE)
    proc = "; ".join(f"{p['keys'][0]}→{p['fit']}" for p in PROCESSES)
    return ("CHARTERED-ACCOUNTANT REFERENCE. Apply the correct treatment, cite the "
            "standard, and map to Odoo accounting modules — standard-first.\n"
            "GCC/PK indirect tax: " + tax + "\nDirect/corporate tax: " + ct +
            "\nIFRS treatments: " + ifrs + "\nRegulatory compliance: " + comp +
            "\nFinance process → Odoo fit: " + proc)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower())


def regime(country_code: str) -> Optional[dict]:
    return TAX_REGIMES.get((country_code or "").upper())


def corporate_tax(country_code: str) -> Optional[dict]:
    return CORPORATE_TAX.get((country_code or "").upper())


def advise(requirement: str, country: Optional[str] = "AE") -> Optional[dict]:
    """Return accounting treatment + Odoo mapping + compliance for a finance
    requirement, or None if it isn't a finance topic. No API call."""
    t = _norm(requirement)
    if not t:
        return None
    out = {"source": "finance-knowledge", "ifrs": [], "process": None, "tax": None,
           "corporate_tax": None, "compliance": [], "risks": []}

    for entry in IFRS:
        if any(k in t for k in entry["keys"]):
            out["ifrs"].append({"standard": entry["std"], "treatment": entry["treatment"],
                                "odoo": entry["odoo"]})
    for p in PROCESSES:
        if any(k in t for k in p["keys"]):
            out["process"] = {"odoo": p["odoo"], "fit": p["fit"]}
            break

    for c in COMPLIANCE:
        if any(k in t for k in c["keys"]):
            out["compliance"].append({"programme": c["name"], "note": c["note"]})

    ct = corporate_tax(country or "AE")
    if ct and any(w in t for w in ["corporate tax", "income tax", "ct ", "profit tax",
                                   "deferred tax", "zakat", "qfzp", "free zone"]):
        out["corporate_tax"] = {"country": ct["name"], "rate": ct["rate"],
                                "authority": ct["authority"], "notes": ct["notes"]}

    reg = regime(country or "AE")
    if reg and (any(w in t for w in ["vat", "tax", "invoice", "e-invoice", "zatca",
                                     "fatoora", "fta", "compliance", "return"])
                or out["process"]):
        out["tax"] = {"country": reg["name"], "vat": reg["vat"],
                      "authority": reg["authority"], "modules": reg["modules"],
                      "notes": reg["notes"]}
        if any(w in t for w in ["e-invoice", "einvoice", "zatca", "fatoora", "e invoicing"]):
            out["compliance"].append(
                "E-invoicing is a statutory, deadline-driven programme — scope "
                "certificates/devices and clearance/reporting mode early.")

    if not (out["ifrs"] or out["process"] or out["tax"] or out["corporate_tax"]
            or out["compliance"]):
        return None
    out["risks"].append("Confirm treatment with the client's auditor/CA before sign-off.")
    return out
