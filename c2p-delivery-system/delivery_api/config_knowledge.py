"""Built-in Odoo configuration planning — turn classified requirements into an
actionable Odoo setup plan with NO API call.

This is the planning half of the config stage: WHAT to configure, in which Odoo
area, for each requirement (derived from the curated capability knowledge), plus
the GCC baseline. It intentionally does NOT emit auto-executable create/write
operations — applying writes to a live Odoo stays a gated, deliberate action
(the LLM/consultant path). So this gives a complete config plan offline while
keeping live changes safe.
"""
from __future__ import annotations

import odoo_knowledge
import finance_knowledge


def _baseline(country_code: str = "AE") -> list:
    reg = finance_knowledge.regime(country_code) or finance_knowledge.regime("AE")
    steps = [
        "Create the company record (name, address, currency AED, logo).",
        f"Install localization {', '.join(reg['modules']) or 'for the country'} and load the chart of accounts.",
        f"Configure {reg['vat']} VAT taxes and fiscal positions ({reg['authority']}).",
        "Set the fiscal year, periods and number sequences (invoices, orders).",
        "Create users, assign groups/access rights, and set the default language/timezone.",
    ]
    return steps


def build_plan(eng, modules: str = "") -> dict:
    """Assemble an Odoo configuration plan from the engagement's requirements."""
    reqs = (eng.stages.get("ba_requirements") or {}).get("functional_requirements") or []
    if not reqs:
        fns = eng.stages.get("functional") or []
        reqs = [{"requirement": f.get("requirement_summary"), "area": None,
                 "odoo_fit": f.get("verdict")} for f in fns]
    if not reqs:
        cands = (eng.stages.get("presales") or {}).get("candidate_requirements") or []
        reqs = [{"requirement": (c.get("requirement") if isinstance(c, dict) else c)}
                for c in cands]

    by_area: dict[str, dict] = {}
    custom_flags = []
    for r in reqs:
        text = r.get("requirement") or ""
        if not text:
            continue
        cl = odoo_knowledge.classify(text)
        res = cl.get("result") or {}
        area = r.get("area") or (res.get("standard_capability", {}).get("modules") or [{}])[0].get("name") or "General"
        mods = [m.get("name") for m in (res.get("standard_capability", {}).get("modules") or [])]
        step = res.get("recommended_path") or f"Configure: {text[:90]}"
        bucket = by_area.setdefault(area, {"area": area, "modules": set(), "steps": []})
        bucket["modules"].update(m for m in mods if m)
        bucket["steps"].append(step)
        if (r.get("odoo_fit") or res.get("verdict")) in ("custom", "studio"):
            custom_flags.append(text[:80])

    plan = [{"area": b["area"], "modules": sorted(b["modules"]),
             "steps": sorted(set(b["steps"]))}
            for b in by_area.values()]

    risks = ["This is a configuration PLAN — review before applying to live Odoo.",
             "Validate exact field values and master data with the client."]
    if custom_flags:
        risks.append(f"{len(custom_flags)} item(s) need Studio/custom work, not just config: "
                     + "; ".join(custom_flags[:3]) + ("…" if len(custom_flags) > 3 else ""))

    return {
        "summary": f"Configuration plan for {eng.company}: GCC baseline + "
                   f"{len(plan)} area(s) covering {len(reqs)} requirements.",
        "baseline": _baseline(),
        "plan": plan,
        "operations": [],          # no auto-execute; live writes stay gated
        "risks": risks,
        "source": "template",
    }
