"""Built-in Project-Management intelligence — deterministic delivery estimation.

A senior Odoo delivery manager doesn't need an LLM to size a project: effort is a
function of requirement count, Odoo-fit (standard/config/studio/custom) and a few
well-known multipliers (data migration, testing, training, governance). This
module encodes that estimating model so effort, timeline, team and a price band
are computed instantly, with NO API call — grounding the proposal/project stages.

Day rate and team shape are configurable via env.
"""
from __future__ import annotations

import math
import os
from typing import Optional

DAY_RATE_AED = float(os.getenv("C2P_DAY_RATE_AED", "1800"))   # blended consultant/day
TEAM_VELOCITY = float(os.getenv("C2P_TEAM_VELOCITY", "13.5"))  # effective md / week

# Build effort (man-days) per requirement by Odoo-fit verdict.
FIT_MD = {"standard": 0.5, "configurable": 1.5, "studio": 3.0,
          "custom": 8.0, "unknown": 2.0}

# Area complexity multipliers — some domains carry more config/testing weight.
AREA_FACTOR = {
    "accounting": 1.4, "finance": 1.4, "tax": 1.3, "manufacturing": 1.4,
    "mrp": 1.4, "inventory": 1.2, "warehouse": 1.2, "payroll": 1.5, "hr": 1.1,
    "pos": 1.2, "ecommerce": 1.3, "integration": 1.5, "crm": 1.0, "sales": 1.0,
    "purchase": 1.0, "project": 1.0,
}

# Wrap-around workstreams as a fraction of raw build effort (min floors in md).
OVERHEADS = [
    ("Discovery & design", 0.18, 4),
    ("Data migration", 0.15, 3),
    ("Testing & UAT", 0.20, 4),
    ("Training & change mgmt", 0.10, 2),
    ("PM & governance", 0.15, 3),
    ("Go-live & hypercare", 0.10, 3),
]

# Standard delivery phases (share of the TOTAL plan).
PHASES = [
    ("Discovery & Analysis", 0.12),
    ("Solution Design", 0.10),
    ("Configuration & Build", 0.34),
    ("Data Migration", 0.10),
    ("Testing & UAT", 0.16),
    ("Training & Go-Live", 0.10),
    ("Hypercare", 0.08),
]

TEAM = [
    {"role": "Project Manager", "allocation": "part-time"},
    {"role": "Functional Consultant (Odoo)", "allocation": "full-time"},
    {"role": "Business Analyst", "allocation": "discovery-heavy"},
    {"role": "Technical Developer", "allocation": "build phase"},
    {"role": "QA / Tester", "allocation": "test phase"},
]


def digest() -> str:
    """A compact PM estimating reference to embed in an agent's system prompt."""
    fit = "; ".join(f"{k}={v}md" for k, v in FIT_MD.items())
    over = "; ".join(f"{n} {int(f * 100)}%" for n, f, _ in OVERHEADS)
    ph = "; ".join(f"{n} {int(s * 100)}%" for n, s in PHASES)
    return ("PM ESTIMATING MODEL (C2P). Build effort per requirement by Odoo-fit: " + fit +
            " (× area factor). Overheads on build effort: " + over +
            ". Delivery phases (share of plan): " + ph +
            f". Blended day rate AED {int(DAY_RATE_AED)}; price band ±15–20%; add 5% VAT; "
            "Odoo licensing billed separately. Always phase large scope (MVP first).")


def _area_factor(area: Optional[str]) -> float:
    a = (area or "").lower()
    for key, f in AREA_FACTOR.items():
        if key in a:
            return f
    return 1.0


def _risks(reqs, customs: int, finance: int) -> list:
    risks = []
    if customs:
        risks.append(f"{customs} custom build(s) — confirm specs early; re-test on each Odoo upgrade.")
    if finance:
        risks.append("Finance/tax scope — validate VAT treatment and statutory reports with the client's accountant.")
    if len(reqs) > 25:
        risks.append("Large scope — phase the rollout (MVP first) to control change and UAT load.")
    risks.append("Data migration quality is the usual critical path — get sample data early.")
    risks.append("Lock scope at design sign-off; route changes through a change-request gate.")
    return risks


def estimate(requirements: list, day_rate: Optional[float] = None) -> dict:
    """Size a delivery from a requirements list. Each item may carry
    'verdict'/'odoo_fit', 'area', 'priority'. Returns a full estimate — no API."""
    rate = float(day_rate or DAY_RATE_AED)
    items = requirements or []
    build_md = 0.0
    customs = finance = 0
    by_area: dict[str, float] = {}
    for r in items:
        fit = (r.get("verdict") or r.get("odoo_fit") or "unknown").lower()
        if fit not in FIT_MD:
            fit = "unknown"
        area = r.get("area") or "general"
        md = FIT_MD[fit] * _area_factor(area)
        build_md += md
        by_area[area] = round(by_area.get(area, 0) + md, 1)
        if fit == "custom":
            customs += 1
        if _area_factor(area) >= 1.3 and ("financ" in area.lower() or "tax" in area.lower()
                                          or "account" in area.lower()):
            finance += 1

    build_md = round(build_md, 1)
    overheads = []
    over_total = 0.0
    for name, frac, floor in OVERHEADS:
        md = max(round(build_md * frac, 1), floor)
        overheads.append({"workstream": name, "man_days": md})
        over_total += md
    total_md = round(build_md + over_total, 1)
    weeks = max(2, math.ceil(total_md / TEAM_VELOCITY))

    timeline, acc = [], 0
    for name, share in PHASES:
        wk = max(1, round(weeks * share))
        timeline.append({"phase": name, "weeks": wk, "starts_week": acc + 1})
        acc += wk

    price = round(total_md * rate)
    return {
        "source": "pm-knowledge",
        "requirements_costed": len(items),
        "build_man_days": build_md,
        "overheads": overheads,
        "total_man_days": total_md,
        "effort_by_area": by_area,
        "duration_weeks": weeks,
        "timeline": timeline,
        "team": TEAM,
        "pricing": {
            "model": "Time & Materials / fixed-price band",
            "day_rate_aed": rate,
            "estimate_aed": price,
            "range_aed": [round(price * 0.85), round(price * 1.2)],
            "vat_note": "Add 5% UAE VAT.",
            "licensing_note": "Odoo subscription (user + apps) billed separately by Odoo.",
        },
        "custom_builds": customs,
        "risks": _risks(items, customs, finance),
        "assumptions": [
            "Standard Odoo where it fits; custom only where proven necessary.",
            "One production go-live; phased rollout for large scope.",
            "Client provides timely data, sign-offs and UAT resources.",
        ],
    }
