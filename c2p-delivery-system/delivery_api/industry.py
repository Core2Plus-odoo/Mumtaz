"""Industry playbook library — owned, deterministic domain knowledge.

C2P's accumulated answer to "what does a <industry> Odoo project look like":
the processes, the pains, the standard Odoo modules required, GCC localisation,
KPIs, and the customizations that usually come up. Agents load the matching
playbook before scoping so proposals name the right modules and project plans
are grounded — fewer cold-reasoned guesses, more institutional knowledge. The
data lives in an open, portable JSON file (data/industry_playbooks.json).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Optional

_DATA = os.path.join(os.path.dirname(__file__), "data", "industry_playbooks.json")


@lru_cache(maxsize=1)
def _load() -> dict:
    with open(_DATA, encoding="utf-8") as f:
        return json.load(f)


def list_industries() -> list[dict]:
    return [{"key": k, "name": v["name"], "aliases": v.get("aliases", [])}
            for k, v in _load().items()]


def get(key: str) -> Optional[dict]:
    return _load().get(key)


def match_industry(text: Optional[str]) -> Optional[str]:
    """Best-effort match of free text to a playbook key via key/name/aliases."""
    if not text:
        return None
    t = text.strip().lower()
    data = _load()
    if t in data:
        return t
    # name or alias appears in the text (or vice-versa)
    for k, v in data.items():
        cands = [v["name"].lower(), k.replace("_", " ")] + [a.lower() for a in v.get("aliases", [])]
        for c in cands:
            if c and (c in t or t in c):
                return k
    return None


def playbook_block(industry_text: Optional[str]) -> str:
    """A prompt-ready block of the matched industry playbook, or '' if no match."""
    key = match_industry(industry_text)
    if not key:
        return ""
    p = _load()[key]
    mods = p.get("odoo_modules", {})

    def j(x):
        return ", ".join(x) if x else "—"

    return (
        f"\n\nINDUSTRY PLAYBOOK — {p['name']} (C2P owned reference; ground your "
        f"scope, module choices and plan in this, and prefer these standard "
        f"modules before proposing anything custom):\n"
        f"- Key processes: {j(p.get('key_processes'))}\n"
        f"- Common pains: {j(p.get('common_pains'))}\n"
        f"- Odoo core modules: {j(mods.get('core'))}\n"
        f"- Recommended modules: {j(mods.get('recommended'))}\n"
        f"- Optional / scale modules: {j(mods.get('optional'))}\n"
        f"- GCC localisation: {p.get('gcc_localization', '—')}\n"
        f"- Typical KPIs: {j(p.get('typical_kpis'))}\n"
        f"- Common customizations (only where standard/Studio cannot cover): "
        f"{j(p.get('common_customizations'))}\n"
    )
