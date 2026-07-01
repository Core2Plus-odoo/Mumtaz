"""Agent-brain layer — makes the functional analysis SMARTER by cross-referencing
every knowledge source, self-correcting against the standard-first rule, reusing
prior analyses (memory), and decomposing compound requirements.

Applied to every functional result (local or model) so verdicts are more accurate
and the standard-first discipline is enforced: a requirement is never 'custom' if
native automation or standard configuration genuinely covers it.
"""
from __future__ import annotations

import re

import odoo_automation
import odoo_standard

_RUNG = {"standard": 0, "configurable": 1, "studio": 2, "custom": 3, "unknown": 1}
_RUNG_NAME = {0: "standard", 1: "configurable", 2: "studio", 3: "custom"}
# requirements that are genuinely custom even if keywords look automatable
_CUSTOM_SIGNALS = ("tier", "tiered", "integrat", "connector", "sync with", "external system",
                   "bespoke", "proprietary", "commission", "custom algorithm", "middleware",
                   "api integration", "webhook to")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower())


def refine_verdict(out: dict, requirement: str) -> dict:
    """Self-correct the verdict against standard-first: downgrade an over-eager
    'custom'/'studio' when native automation or strong standard coverage applies —
    unless the requirement carries a genuine custom signal."""
    if not out:
        return out
    text = _norm(requirement)
    verdict = out.get("verdict") or "unknown"
    rung = _RUNG.get(verdict, 1)
    genuine_custom = any(s in text for s in _CUSTOM_SIGNALS)

    auto = out.get("automation_design") or odoo_automation.suggest(requirement).get("automation_design")
    std = out.get("standard_first_apps") or odoo_standard.covered_by(requirement)
    strong_std = any((s.get("score") or 0) >= 4 for s in (std or []))

    reason = None
    if not genuine_custom and rung >= 3:              # custom → configurable if automatable
        if auto:
            rung = 1
            reason = ("Self-corrected to Configurable: native Odoo automation "
                      "(no code) covers this — custom build not required.")
        elif strong_std:
            rung = 1
            reason = ("Self-corrected to Configurable: strong standard-Odoo coverage — "
                      "configure standard first, no custom.")
    if not genuine_custom and rung == 2 and strong_std:   # studio → standard if strongly covered
        rung = 0
        reason = "Self-corrected to Standard: fully covered by standard configuration."

    if reason and rung != _RUNG.get(verdict, 1):
        out["verdict"] = _RUNG_NAME[rung]
        out["verdict_rationale"] = reason + " " + (out.get("verdict_rationale") or "")
        out["handoff_to_dev"] = rung >= 3
        if rung < 3:
            out["custom"] = {"needed": False, "inherits": "", "connection": ""}
            out.setdefault("risks", [])
        out["self_corrected"] = True
    return out


def decompose(requirement: str) -> list:
    """Split a compound requirement into sub-requirements (for smarter analysis)."""
    t = requirement or ""
    parts = re.split(r"\s*(?:;|,\s+and\s+|\band also\b|\bplus\b|\bas well as\b)\s*", t)
    parts = [p.strip(" .") for p in parts if len(p.strip()) > 12]
    return parts if len(parts) > 1 else []


def similar_prior(eng, requirement: str, threshold: float = 0.55):
    """Reuse memory: find a prior functional analysis on this engagement whose
    requirement is very similar (keyword overlap), so the agent recognises
    already-solved patterns instead of re-deriving them."""
    words = set(re.findall(r"[a-z]{4,}", _norm(requirement)))
    if not words:
        return None
    best, best_score = None, 0.0
    for f in (eng.stages.get("functional") or []):
        prior = _norm(f.get("requirement_summary") or "")
        pw = set(re.findall(r"[a-z]{4,}", prior))
        if not pw:
            continue
        overlap = len(words & pw) / max(1, len(words | pw))
        if overlap > best_score:
            best, best_score = f, overlap
    if best and best_score >= threshold:
        return {"verdict": best.get("verdict"),
                "requirement": best.get("requirement_summary"),
                "similarity": round(best_score, 2)}
    return None


def enrich(out: dict, requirement: str, eng=None) -> dict:
    """Full smart pass over a functional result: cross-knowledge, self-correct,
    add sub-requirements and memory hints. Idempotent and safe."""
    if not out:
        return out
    try:
        subs = decompose(requirement)
        if subs:
            out["sub_requirements"] = subs
        if eng is not None:
            prior = similar_prior(eng, requirement)
            if prior:
                out["memory"] = prior
        refine_verdict(out, requirement)
    except Exception:  # smartness must never break the analysis
        pass
    return out
