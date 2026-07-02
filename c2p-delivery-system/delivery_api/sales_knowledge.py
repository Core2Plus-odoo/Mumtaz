"""Built-in Sales & Marketing intelligence — how a GCC Odoo agency wins work.

The commercial playbook a senior partner applies by reflex: ICP and qualification
frameworks, discovery-call structure, objection handling, competitor positioning,
pricing/packaging, outreach cadence and marketing channels. `digest()` embeds it
in the prospect/outreach/presales/comms agents; helpers give local (no-API)
qualification scoring and objection/competitor lookups.
"""
from __future__ import annotations

import re

# ── ICP (who we win with) ──────────────────────────────────────────────────
ICP = dict(
    sweet_spot="Manufacturers, distributors, traders and retailers, 20–500 employees, "
               "UAE/GCC and Pakistan, on spreadsheets/Tally/QuickBooks/legacy ERP or an "
               "outgrown local system.",
    strong_signals=[
        "Multi-entity or multi-branch (consolidation pain)",
        "VAT/ZATCA compliance pressure or recent penalties",
        "Growth event: new warehouse, new branch, funding, acquisition",
        "Disconnected systems (POS ≠ stock ≠ accounts) / manual re-keying",
        "Hiring for finance/ops roles (process pain proxy)",
        "Existing Odoo used badly (rescue/optimisation engagements close fast)"],
    disqualifiers=[
        "Micro business (<10 staff) with no complexity — SaaS templates fit better",
        "Wants deep ERP for near-zero budget (< AED 15k)",
        "Heavy regulated verticals we don't cover (core banking, hospital HIS)",
        "Decision-maker not involved and no path to them"],
)

# ── Qualification (BANT + MEDDICC essentials) ──────────────────────────────
QUALIFICATION = [
    ("Budget", "Is there a named budget or a costed pain? Anchor: implementations "
               "run AED 25k–400k+ plus Odoo licences."),
    ("Authority", "Who signs? Owner/MD for SMEs; get them in the room by proposal."),
    ("Need", "A costed, dated pain (stockouts, month-end takes 15 days, VAT risk) — "
             "not 'we want an ERP'."),
    ("Timeline", "A forcing event (fiscal year, audit, lease, launch) beats 'someday'."),
    ("Metrics", "What number changes if we succeed? Baseline it in discovery."),
    ("Champion", "An internal owner who wins if the project wins."),
    ("Decision process", "Steps, committee, procurement, competitors in play."),
]

# ── Discovery call structure (first meeting) ───────────────────────────────
DISCOVERY_CALL = [
    "Open: their words first — 'what prompted the call?' (pain in their language)",
    "Map the business: entities, branches, headcount, systems in use today",
    "Quantify 2–3 pains (hours lost, stock value, penalty risk, missed sales)",
    "Sketch the to-be on standard Odoo — show, don't lecture (quick win credibility)",
    "Qualify: budget band, authority, timeline, decision process",
    "Close on a next step with a date: scoping workshop or requirements session",
]

# ── Objection handling ─────────────────────────────────────────────────────
OBJECTIONS = {
    "too expensive": "Reframe to cost-of-pain: quantify what manual work, stockouts or "
        "compliance risk costs per month; phase the rollout (MVP first) so value lands "
        "before the full spend; compare to SAP/Dynamics TCO (2–5×).",
    "we tried an erp before": "Failed ERP is usually failed scoping/adoption, not the tool. "
        "Point to our standard-first method, phased go-live, UAT gates and named exit "
        "criteria per phase — de-risk with a paid discovery/scoping sprint.",
    "odoo is open source / too cheap": "Odoo runs 12M+ users; enterprise support and "
        "SLA-backed hosting (Odoo.sh) are commercial-grade. Licence savings fund better "
        "implementation — where success is actually decided.",
    "we are too busy": "That IS the pain. Phased approach needs ~2–4 hrs/week from their "
        "team in discovery; we carry the build. Start with the one process bleeding most.",
    "can you customise everything": "We CAN, but won't by default: custom code raises cost "
        "and upgrade risk. Standard-first, adapt process to best practice where sensible, "
        "custom only for genuine differentiators — that discipline protects their money.",
    "cheaper freelancer / offshore quote": "Compare deliverables not day-rates: methodology, "
        "documents (BRD/FRS/UAT), gated go-live, hypercare, and someone accountable in the "
        "GCC. Rescue projects cost more than doing it right once.",
    "we need it in a month": "A scoped Phase-1 (one process, one entity) can land in weeks; "
        "a full multi-entity ERP cannot. Honest phasing beats a missed big-bang.",
}

# ── Competitor positioning ─────────────────────────────────────────────────
COMPETITORS = {
    "SAP Business One": "Strong finance brand; 2–5× licence+implementation TCO, heavier "
        "change cycles, partner-locked. Odoo wins on cost, UX, speed, app breadth (POS/"
        "eCommerce/HR in one).",
    "Microsoft Dynamics 365 BC": "Good MS-stack fit; higher licence cost, modules feel "
        "separate, local partner quality varies. Odoo wins on integrated suite + price.",
    "Zoho One": "Cheap and broad but shallow ops (inventory/manufacturing/accounting depth). "
        "Odoo wins when real warehouse/MRP/multi-entity accounting is needed.",
    "Tally / QuickBooks / Xero": "Bookkeeping, not ERP — no ops backbone. Position Odoo as "
        "the operational upgrade that keeps the accountant happy (proper CoA, VAT reports).",
    "Oracle NetSuite": "Capable mid-market cloud ERP; significantly higher subscription, "
        "US-centric partners. Odoo wins on GCC localisation cost and flexibility.",
    "Local/vertical ERPs": "Deep vertical fit but vendor-risk, dated UX, weak ecosystems. "
        "Odoo wins on longevity, community, upgrade path.",
}

# ── Pricing & packaging ────────────────────────────────────────────────────
PRICING = [
    "Anchor with a band early (from the local estimator) — avoids late sticker shock.",
    "Package: Discovery sprint (fixed, small) → Phase-1 fixed price → T&M change requests.",
    "Payment terms: 50% on SoW signature, 50% on go-live sign-off (or 40/40/20 UAT).",
    "Always separate: implementation fee vs Odoo licences (billed by Odoo) vs hosting.",
    "Quote 5% UAE VAT explicitly; multi-entity/KSA scope priced as options.",
    "Never discount scope-free: trade price against scope, phasing or timeline.",
]

# ── Outreach & marketing playbook ──────────────────────────────────────────
OUTREACH = [
    "Sequence: personalised email (pain hypothesis + proof) → LinkedIn touch → "
    "call → value follow-up (case study / VAT checklist) → break-up email. 5 touches, 3 weeks.",
    "Message = their industry + a costed pain + one proof point + soft CTA (15-min call). "
    "Never feature-dump Odoo.",
    "Referrals & accountants/auditors are the highest-converting GCC channel — nurture them.",
    "Content that converts: VAT/ZATCA compliance guides, 'Excel to ERP' cost calculators, "
    "industry demo videos (10 min, their process end-to-end).",
    "Events: local chamber/industry meetups out-convert paid ads for 20–500-employee firms.",
    "Odoo partner listing + Google reviews are table stakes — keep them current.",
]

WIN_THEMES = [
    "Standard-first = lower cost, faster go-live, upgrade-safe (our core differentiator).",
    "GCC-native: AED/IFRS/5% VAT/ZATCA and multi-company from day one.",
    "Method, not heroics: BRD → FRS → UAT → gated go-live → hypercare, documents included.",
    "One accountable partner: functional + technical + PM under one roof (no finger-pointing).",
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower())


def qualify(notes: str, industry: str | None = None) -> dict:
    """Local BANT-style qualification scan of discovery notes — no API."""
    t = _norm(notes) + " " + _norm(industry)
    found, missing = [], []
    checks = {
        "Budget": ("budget", "aed", "cost", "price", "invest"),
        "Authority": ("owner", "md ", "ceo", "director", "founder", "decision"),
        "Need (costed pain)": ("stockout", "manual", "penalt", "delay", "error",
                               "hours", "excel", "disconnect", "month-end", "vat"),
        "Timeline": ("by ", "quarter", "month", "deadline", "year-end", "go live",
                     "golive", "asap", "fiscal"),
    }
    for name, keys in checks.items():
        (found if any(k in t for k in keys) else missing).append(name)
    signals = [s for s in ICP["strong_signals"] if any(w in t for w in
               _norm(s).split()[:2])]
    score = min(95, 35 + 15 * len(found) + 5 * len(signals))
    return {"score": score, "found": found, "missing": missing,
            "ask_next": [f"Qualify {m}" for m in missing][:3]}


def handle_objection(text: str) -> str | None:
    """Look up the playbook response for an objection — no API."""
    t = _norm(text)
    for key, resp in OBJECTIONS.items():
        if any(w in t for w in key.split()[:2]):
            return resp
    return None


def digest() -> str:
    """Compact sales & marketing playbook for embedding in agent prompts."""
    quals = "; ".join(f"{q[0]} ({q[1][:60]}…)" if len(q[1]) > 60 else f"{q[0]} ({q[1]})"
                      for q in QUALIFICATION[:4])
    obj = "; ".join(f"'{k}'→{v[:70]}…" for k, v in list(OBJECTIONS.items())[:4])
    comp = "; ".join(f"{k}: {v[:65]}…" for k, v in list(COMPETITORS.items())[:4])
    return ("SALES & MARKETING PLAYBOOK (C2P, GCC Odoo agency).\n"
            f"ICP: {ICP['sweet_spot']}\nStrong signals: "
            + "; ".join(ICP['strong_signals'][:4])
            + "\nDisqualify: " + "; ".join(ICP['disqualifiers'][:2])
            + f"\nQualify with BANT+: {quals}"
            + "\nDiscovery call: " + " → ".join(s.split(':')[0] for s in DISCOVERY_CALL)
            + f"\nObjection playbook: {obj}"
            + f"\nCompetitive positioning: {comp}"
            + "\nPricing: " + " ".join(PRICING[:3])
            + "\nOutreach: " + OUTREACH[0] + " " + OUTREACH[1]
            + "\nWin themes: " + " | ".join(WIN_THEMES))
