"""Built-in SALES PITCH LIBRARY — ready-to-use commercial scripts (no API).

Where `sales_knowledge` holds the *strategy* (ICP, qualification, pricing), this
module holds the *words*: elevator pitches, cold emails, LinkedIn touches, call
openers, a discovery question bank, a demo flow, follow-up sequences, ROI talk
tracks, per-industry angles and closing scripts. Everything is deterministic and
embeddable so the prospecting / outreach / presales / comms agents can pitch,
follow up and handle a room with zero LLM calls. `digest()` feeds the agent
prompts; the helpers (`pitch_for`, `email`, `questions_for`, `followup_sequence`,
`roi_track`) return ready copy the local agents can send as-is.
"""
from __future__ import annotations

import re

BRAND = "C2P"  # tenant-neutral default; the active tenant name is substituted at call time.

# ── Positioning: elevator pitches at three lengths ─────────────────────────
POSITIONING = {
    "one_liner": "We put your whole business — sales, stock, finance and compliance — "
                 "on one Odoo platform, done right the first time.",
    "thirty_sec": "We're an Odoo ERP partner for GCC and Pakistan SMEs. Most of our clients "
                  "come to us drowning in spreadsheets and disconnected apps — stock that never "
                  "matches accounts, month-end that takes two weeks, VAT that's a scramble. We "
                  "put them on a single Odoo system with a standard-first method: configure "
                  "before we customise, phase the rollout, and hand over documented and trained. "
                  "Live in weeks, not years, at a fraction of SAP's cost.",
    "sixty_sec": "Think of everything your team runs the business on today — the sales sheet, "
                 "the stock file, the accounts package, the WhatsApp approvals. Each is an island, "
                 "and your people are the bridges, re-keying data and chasing numbers. We replace "
                 "those islands with one Odoo platform: a quote becomes an order becomes a "
                 "delivery becomes an invoice becomes a VAT-ready ledger, automatically. We do it "
                 "standard-first — Odoo already does 90% of what most SMEs need, so we configure "
                 "that, adapt your process to proven best practice, and only build custom where "
                 "you genuinely differ. That keeps cost down, go-live fast and upgrades safe. You "
                 "get a documented, trained, gated delivery with one partner accountable end to end.",
}

VALUE_PILLARS = [
    ("Standard-first", "90% of SME needs are already in Odoo — configure first, customise last. "
                       "Lower cost, faster go-live, upgrade-safe."),
    ("One source of truth", "Sales, purchase, stock, accounting and CRM on one platform — no "
                            "re-keying, no reconciliation between apps."),
    ("GCC-native", "AED/PKR, IFRS, 5% VAT, ZATCA e-invoicing and multi-company from day one."),
    ("Method, not heroics", "BRD → FRS → UAT → gated go-live → hypercare. Documented and trained, "
                            "so it sticks."),
    ("One accountable partner", "Functional, technical and PM under one roof — no finger-pointing "
                                "between vendors."),
]

# Reusable proof points (swap for real tenant case data when available).
PROOF_POINTS = [
    "A distributor cut month-end close from 15 days to 3 after moving off spreadsheets.",
    "A retailer unified POS, stock and accounts — stockouts down, no more nightly re-keying.",
    "A manufacturer got real-time job costing and stopped quoting at a loss.",
    "A multi-entity group consolidated three companies into one VAT-ready ledger.",
    "A trader passed an FTA VAT audit clean because the return came straight from the system.",
]

# ── Cold email templates (subject + body; {tokens} filled by the agent) ────
COLD_EMAILS = {
    "pain_hypothesis": {
        "subject": "{company} — is stock matching your accounts?",
        "body": "Hi {name},\n\nWorking with {industry} businesses in {region}, the pattern we see "
                "is stock, sales and accounts living in separate tools — so numbers never quite "
                "agree and month-end drags.\n\nWe put companies like {company} on one Odoo system "
                "where a sale flows to stock, invoice and a VAT-ready ledger automatically. One "
                "recent client cut month-end from 15 days to 3.\n\nWorth a 15-minute call to see "
                "if it fits? I can show your process end-to-end, not a generic demo.\n\n{sender}",
    },
    "growth_trigger": {
        "subject": "New branch = new complexity for {company}?",
        "body": "Hi {name},\n\nSaw {company} is expanding — congratulations. Growth is exactly "
                "when spreadsheet-and-app setups start to crack: consolidation, inter-company "
                "stock, VAT across entities.\n\nWe help {industry} groups run multiple entities "
                "on one Odoo platform with a single consolidated view. Standard-first, phased, "
                "live in weeks.\n\nOpen to a short call this week?\n\n{sender}",
    },
    "vat_compliance": {
        "subject": "{company}: VAT return straight from the system",
        "body": "Hi {name},\n\nMost VAT pain isn't the tax — it's assembling the return from "
                "disconnected files at the last minute. In Odoo the return comes straight from "
                "the ledger, FTA/ZATCA-aligned, with an audit trail.\n\nWe set this up for "
                "{industry} businesses in {region} as part of a proper ERP, not a bolt-on. Happy "
                "to show you how it looks — 15 minutes?\n\n{sender}",
    },
    "rescue": {
        "subject": "Odoo not delivering what you hoped, {name}?",
        "body": "Hi {name},\n\nIf {company}'s Odoo (or other ERP) went in but isn't giving you the "
                "reports, automation or adoption you expected, that's almost always a scoping and "
                "process problem, not the tool.\n\nWe run rescue/optimisation sprints: audit what "
                "you have, fix the highest-value gaps standard-first, and get your team actually "
                "using it. Want a quick health-check call?\n\n{sender}",
    },
    "referral": {
        "subject": "{referrer} suggested we talk",
        "body": "Hi {name},\n\n{referrer} mentioned {company} might be outgrowing its current "
                "setup. We're an Odoo ERP partner working with {industry} businesses in {region} "
                "— one platform for sales, stock, finance and VAT, delivered standard-first.\n\n"
                "Happy to share what we did for similar firms. 15 minutes this week?\n\n{sender}",
    },
    "breakup": {
        "subject": "Closing the loop, {name}",
        "body": "Hi {name},\n\nI haven't heard back, so I'll assume the timing isn't right — no "
                "problem. If the spreadsheet-and-apps setup starts costing more than it saves, "
                "we're a message away. I'll leave you with our 'Excel-to-ERP' cost checklist in "
                "case it's useful.\n\nWishing {company} well.\n\n{sender}",
    },
}

LINKEDIN = {
    "connect": "Hi {name} — I work with {industry} businesses in {region} moving off spreadsheets "
               "onto one Odoo platform. Would be glad to connect and share what's working.",
    "message": "Thanks for connecting, {name}. No pitch — if it's ever useful, I can show how "
               "{industry} firms run sales, stock, finance and VAT in one place with far less "
               "manual work. Happy to send a short case study.",
}

# ── Discovery-call scripts ─────────────────────────────────────────────────
CALL_OPENER = (
    "Thanks for the time, {name}. Before I say anything about Odoo, I'd like to understand how "
    "{company} runs today so anything I show is relevant. Can you walk me through what happens "
    "from a customer order to getting paid — and where it hurts most?"
)

DISCOVERY_QUESTIONS = {
    "business": [
        "How many entities, branches or warehouses do you run?",
        "Headcount overall, and in finance/operations specifically?",
        "What systems do you use today — for sales, stock, accounting, payroll?",
        "Where does data get re-keyed or reconciled by hand between them?",
    ],
    "pain": [
        "What takes far longer than it should each week or month?",
        "How long is your month-end close, and why?",
        "How often do stock figures disagree with what's actually on the shelf?",
        "When did a manual error or delay last cost you money or a customer?",
    ],
    "finance_vat": [
        "How is the VAT return assembled today — and how stressful is it?",
        "Any FTA/ZATCA penalties, audit findings or near-misses?",
        "Can you see profit by product, project or branch when you need it?",
        "How current are your management accounts on any given day?",
    ],
    "goals": [
        "If one thing were automated tomorrow, what would free up the most time?",
        "What does 'good' look like in 12 months — and what number proves it?",
        "Is there a forcing event — audit, fiscal year, new branch, funding?",
        "Who else needs to be comfortable for a project like this to go ahead?",
    ],
}

DEMO_FLOW = [
    "Anchor on THEIR process from discovery — 'you said quotes take a day; watch this.'",
    "Quote → sales order → delivery → invoice in one flow; show it hits stock and accounts live.",
    "Show a real-time dashboard (sales, stock value, receivables) — the visibility they lack.",
    "Show the VAT/tax report generating from the same data — compliance without extra work.",
    "One 'wow' relevant to their pain (barcode picking, job costing, multi-company consolidation).",
    "Stop before feature-fatigue; tie every screen back to a pain they named. Confirm fit, then scope.",
]

# ── Follow-up sequence (value touches, not nags) ───────────────────────────
FOLLOWUPS = [
    ("Day 0", "Recap email: the 2–3 pains they named + how the phased plan addresses each. "
              "Attach the one-page summary."),
    ("Day 2", "LinkedIn touch or a relevant proof point (case study matching their industry)."),
    ("Day 5", "Call. If no answer, voicemail + short 'sending the ROI checklist' email."),
    ("Day 8", "Value asset: 'Excel-to-ERP cost calculator' or 'VAT/ZATCA readiness checklist'."),
    ("Day 12", "Direct ask: 'Should we book the scoping workshop, or is timing off?'"),
    ("Day 18", "Break-up email — leaves the door open, often triggers a reply."),
]

# ── ROI / value talk tracks (with worked examples to say out loud) ─────────
ROI_TRACKS = {
    "manual_labour": "If two people spend a day each week re-keying between systems, that's ~80 "
                     "hours a month. Cost that at their loaded rate and the ERP often pays back in "
                     "under a year on labour alone — before you count the errors avoided.",
    "month_end": "A 15-day close means you're steering the business on numbers two weeks old. "
                 "Getting to a 3-day close isn't just time saved — it's decisions made on current "
                 "reality instead of last month's guess.",
    "stockouts": "Every stockout is a sale you trained the customer to take elsewhere; every "
                 "overstock is cash on a shelf. Real-time stock tied to sales and purchasing "
                 "trims both — usually a quick, visible win.",
    "compliance": "One VAT penalty or a messy audit can cost more than the year's implementation "
                  "fee. A return that comes straight from the ledger turns a monthly scramble into "
                  "a click — and de-risks the audit entirely.",
    "tco_vs_sap": "Against SAP or Dynamics, Odoo's licence-plus-implementation TCO is typically "
                  "2–5× lower for a comparable SME scope. The saving funds a better implementation "
                  "— which is where success is actually decided.",
}

# ── Per-industry pitch angles (hook + top pains + the line that lands) ─────
INDUSTRY_PITCH = {
    "manufacturing": {
        "hook": "Quote jobs on real costs, not gut feel.",
        "pains": ["No live job/BOM costing", "Material shortages stall production",
                  "Planning lives in spreadsheets"],
        "line": "Odoo ties BOMs, work orders and stock to accounting so you see margin per job "
                "as it runs — and stop quoting at a loss.",
    },
    "distribution": {
        "hook": "One truth for stock, sales and accounts across every branch.",
        "pains": ["Stock never matches accounts", "Multi-warehouse blind spots",
                  "Manual pricing/discount chaos"],
        "line": "A sale moves stock and posts to the ledger in one flow — consolidated across "
                "branches, VAT-ready, no re-keying.",
    },
    "retail": {
        "hook": "POS, stock and accounting that finally agree.",
        "pains": ["POS ≠ stock ≠ accounts", "No real-time margin", "Multi-store consolidation"],
        "line": "Odoo POS feeds the same stock and ledger as everything else — nightly re-keying "
                "gone, real-time margin in.",
    },
    "construction": {
        "hook": "Cost and bill projects without the spreadsheet gymnastics.",
        "pains": ["Project cost overruns unseen", "Retentions/variations untracked",
                  "Subcontractor and material chaos"],
        "line": "Project accounting ties budgets, POs, timesheets and billing together so overruns "
                "show up while you can still act.",
    },
    "services": {
        "hook": "From proposal to invoice without the leakage.",
        "pains": ["Unbilled time and expenses", "No project profitability view",
                  "Disconnected CRM and finance"],
        "line": "Odoo runs CRM, project delivery, timesheets and invoicing on one spine — bill "
                "everything you deliver, see profit per client.",
    },
    "trading": {
        "hook": "Landed cost and margin you can actually trust.",
        "pains": ["Landed cost guesswork", "Multi-currency mess", "Slow, risky VAT returns"],
        "line": "Odoo lands cost onto every shipment and posts multi-currency, VAT-ready entries "
                "automatically — real margin, clean returns.",
    },
    "education": {
        "hook": "Admissions, fees and finance in one system.",
        "pains": ["Fee collection in spreadsheets", "No consolidated finance view",
                  "Manual reporting to management/board"],
        "line": "Odoo links admissions, fee invoicing and accounting so collections and management "
                "reporting stop being a monthly project.",
    },
    "healthcare": {
        "hook": "Run the business side of care on one clean ledger.",
        "pains": ["Billing disconnected from stock/pharmacy", "Insurance receivables ageing",
                  "Compliance-grade reporting by hand"],
        "line": "Odoo unifies procurement, pharmacy stock, billing and accounting so receivables "
                "and reporting stop leaking (clinical systems integrate alongside).",
    },
}

# ── Closing scripts ────────────────────────────────────────────────────────
CLOSING = {
    "trial_close": "Based on what you've shown me, does this feel like it solves the problem you "
                   "started with — or is there a gap I've missed?",
    "next_step": "The right next step is a short paid scoping workshop: we map your priority "
                 "process and come back with a fixed-price Phase 1. Can we hold a date next week?",
    "risk_reversal": "We de-risk it deliberately: paid scoping first, phased go-live, UAT sign-off "
                     "and named exit criteria per phase. You commit to the next phase only when "
                     "the last one lands.",
    "urgency": "You mentioned {event}. To be live before that, we'd need to start scoping in the "
               "next couple of weeks — shall we pencil it in?",
    "summary_close": "So: one platform, standard-first, phased, documented and trained, one partner "
                     "accountable — starting with the process costing you most. Are you happy to "
                     "move to scoping?",
}

NEGOTIATION = [
    "Never discount scope-free — trade price against scope, phasing or timeline.",
    "If they want a lower number, drop to a smaller Phase 1, not a cheaper everything.",
    "Hold value: restate the cost-of-pain before conceding a dirham.",
    "Anchor the band early (from the estimator) so the real number is never a shock.",
    "Keep licences and hosting separate and transparent — don't absorb Odoo's fees into yours.",
    "Give to get: a concession always buys a faster decision, a case-study, or a reference.",
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower())


# ── Local (no-API) helpers the agents can call ─────────────────────────────
def pitch_for(industry: str | None) -> dict:
    """Best-matching industry pitch angle (falls back to distribution)."""
    t = _norm(industry)
    for key, val in INDUSTRY_PITCH.items():
        if key in t:
            return {"industry": key, **val}
    # loose keyword mapping
    alias = {"factory": "manufacturing", "wholesale": "distribution", "shop": "retail",
             "store": "retail", "contractor": "construction", "consult": "services",
             "import": "trading", "export": "trading", "school": "education",
             "college": "education", "clinic": "healthcare", "hospital": "healthcare"}
    for word, key in alias.items():
        if word in t:
            return {"industry": key, **INDUSTRY_PITCH[key]}
    return {"industry": "distribution", **INDUSTRY_PITCH["distribution"]}


def email(kind: str = "pain_hypothesis", **tokens) -> dict:
    """Return a cold-email template, optionally filled with {tokens}."""
    tpl = COLD_EMAILS.get(kind) or COLD_EMAILS["pain_hypothesis"]
    if not tokens:
        return {"kind": kind, **tpl}
    defaults = {"name": "there", "company": "your company", "industry": "your",
                "region": "the GCC", "sender": BRAND, "referrer": "a mutual contact",
                "event": "your deadline"}
    ctx = {**defaults, **{k: v for k, v in tokens.items() if v}}
    try:
        return {"kind": kind,
                "subject": tpl["subject"].format(**ctx),
                "body": tpl["body"].format(**ctx)}
    except Exception:
        return {"kind": kind, **tpl}


def questions_for(area: str = "") -> list[str]:
    """Discovery questions for an area (business/pain/finance_vat/goals), or all."""
    a = _norm(area)
    for key, qs in DISCOVERY_QUESTIONS.items():
        if key in a or a in key:
            return qs
    if "vat" in a or "finance" in a or "tax" in a:
        return DISCOVERY_QUESTIONS["finance_vat"]
    return [q for qs in DISCOVERY_QUESTIONS.values() for q in qs]


def followup_sequence() -> list[dict]:
    """The value-touch follow-up cadence as structured steps."""
    return [{"when": w, "action": a} for w, a in FOLLOWUPS]


def roi_track(topic: str = "") -> str:
    """A ROI talk track by topic (manual_labour/month_end/stockouts/compliance/tco)."""
    t = _norm(topic)
    for key, track in ROI_TRACKS.items():
        if key.split("_")[0] in t or key in t:
            return track
    return ROI_TRACKS["manual_labour"]


def digest() -> str:
    """Compact pitch playbook for embedding in the outreach/presales/comms agents."""
    ind = "; ".join(f"{k}: {v['hook']}" for k, v in list(INDUSTRY_PITCH.items())[:5])
    emails = ", ".join(COLD_EMAILS.keys())
    return (
        "SALES PITCH LIBRARY (ready-to-use, no API needed).\n"
        f"Elevator: {POSITIONING['thirty_sec']}\n"
        "Value pillars: " + " | ".join(p[0] for p in VALUE_PILLARS) + "\n"
        f"Cold-email templates on file: {emails} (fill {{name/company/industry/region/sender}}).\n"
        "Discovery opener: " + CALL_OPENER + "\n"
        "Discovery areas: " + ", ".join(DISCOVERY_QUESTIONS.keys())
        + " (bank of " + str(sum(len(v) for v in DISCOVERY_QUESTIONS.values())) + " questions).\n"
        "Demo flow: " + " → ".join(d.split(";")[0].split(" — ")[0][:40] for d in DEMO_FLOW[:4]) + "\n"
        "Follow-up: value touches over ~18 days (recap → proof → call → asset → ask → break-up).\n"
        f"ROI tracks: {', '.join(ROI_TRACKS.keys())}.\n"
        f"Industry angles: {ind}.\n"
        "Close: trial-close for fit → paid scoping workshop as the next step → risk-reversal "
        "(phased, UAT-gated). Never discount scope-free; trade price for scope/phasing/timeline."
    )
