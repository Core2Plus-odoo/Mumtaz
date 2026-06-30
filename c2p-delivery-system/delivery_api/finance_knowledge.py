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
           "notes": "Sales tax/GST ~17% (provincial services taxes vary); FBR/IRIS "
                    "filing; withholding tax regime is significant."},
}

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
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower())


def regime(country_code: str) -> Optional[dict]:
    return TAX_REGIMES.get((country_code or "").upper())


def advise(requirement: str, country: Optional[str] = "AE") -> Optional[dict]:
    """Return accounting treatment + Odoo mapping + compliance for a finance
    requirement, or None if it isn't a finance topic. No API call."""
    t = _norm(requirement)
    if not t:
        return None
    out = {"source": "finance-knowledge", "ifrs": [], "process": None, "tax": None,
           "compliance": [], "risks": []}

    for entry in IFRS:
        if any(k in t for k in entry["keys"]):
            out["ifrs"].append({"standard": entry["std"], "treatment": entry["treatment"],
                                "odoo": entry["odoo"]})
    for p in PROCESSES:
        if any(k in t for k in p["keys"]):
            out["process"] = {"odoo": p["odoo"], "fit": p["fit"]}
            break

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

    if not (out["ifrs"] or out["process"] or out["tax"]):
        return None
    out["risks"].append("Confirm treatment with the client's auditor/CA before sign-off.")
    return out
