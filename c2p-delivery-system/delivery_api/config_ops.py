"""Deterministic Odoo configuration EXECUTION engine — turn requirements into
real, safe, idempotent Odoo operations the consultants actually apply.

Unlike config_knowledge (which produces a human plan), this emits concrete
create/ensure operations against safe, self-contained models (CRM stages, lead
sources, sales teams, product/contact categories) parsed from the requirement
text. Every op is idempotent ("ensure": create only if it doesn't already
exist), so applying — or re-applying — never duplicates. Execution stays gated
in main.py; this just makes there be something real to execute.
"""
from __future__ import annotations

import re
from typing import Optional


def _list_after(text: str, keyword_pat: str) -> list:
    """Extract a delimited list that follows a keyword + colon, e.g.
    'stages: A -> B -> C' or 'picklist: X, Y, Z'."""
    m = re.search(keyword_pat + r"[^:]{0,40}:\s*([^.;\n]+)", text, re.I)
    if not m:
        return []
    seg = m.group(1)
    parts = re.split(r"\s*(?:→|-+>|—+>?|›|>|,|/|\band\b)\s*", seg)
    out = []
    for p in parts:
        p = p.strip(" .·-\t")
        if 1 <= len(p) <= 32 and re.search(r"[A-Za-z]", p) and p.lower() not in (
                "etc", "and so on", "defined", "a defined"):
            out.append(p)
    return out[:10]


def _requirement_texts(eng) -> list:
    reqs = (eng.stages.get("ba_requirements") or {}).get("functional_requirements") or []
    texts = [r.get("requirement") for r in reqs if r.get("requirement")]
    if not texts:
        texts = [f.get("requirement_summary") for f in (eng.stages.get("functional") or [])
                 if f.get("requirement_summary")]
    if not texts:
        texts = [c.get("requirement") if isinstance(c, dict) else c
                 for c in ((eng.stages.get("presales") or {}).get("candidate_requirements") or [])]
    return [t for t in texts if t]


def _ensure(model: str, name: str, label: str, extra: Optional[dict] = None) -> dict:
    return {"label": label, "model": model, "method": "ensure",
            "domain": [["name", "=", name]], "values": {"name": name, **(extra or {})}}


def build_operations(eng) -> list:
    """Parse the requirements and emit safe, idempotent Odoo config operations."""
    ops = []
    seen = set()

    def add(op):
        key = (op["model"], op["values"].get("name"))
        if key not in seen:
            seen.add(key)
            ops.append(op)

    for text in _requirement_texts(eng):
        low = text.lower()

        # CRM pipeline stages
        if "stage" in low and ("pipeline" in low or "crm" in low or "lead" in low or "sales" in low):
            for i, name in enumerate(_list_after(text, r"stages?")):
                add(_ensure("crm.stage", name, f"CRM stage · {name}", {"sequence": (i + 1) * 10}))

        # Lead source picklist
        if "source" in low or "picklist" in low:
            for name in _list_after(text, r"(?:source|picklist)"):
                add(_ensure("utm.source", name, f"Lead source · {name}"))

        # Sales teams
        if "sales team" in low or "sales channel" in low:
            for name in _list_after(text, r"(?:sales teams?|channels?)"):
                add(_ensure("crm.team", name, f"Sales team · {name}"))

        # Product categories
        if "product categor" in low or "item categor" in low:
            for name in _list_after(text, r"(?:product|item) categor\w*"):
                add(_ensure("product.category", name, f"Product category · {name}"))

        # Contact / customer tags
        if "customer tag" in low or "contact tag" in low or "customer segment" in low:
            for name in _list_after(text, r"(?:customer|contact)\s+(?:tags?|segments?)"):
                add(_ensure("res.partner.category", name, f"Contact tag · {name}"))

    return ops
