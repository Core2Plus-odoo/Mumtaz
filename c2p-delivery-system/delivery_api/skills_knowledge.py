"""Built-in senior-practitioner SKILLS — the high-end competencies a top-tier
Odoo delivery operator applies by reflex, across every role.

The other knowledge packs answer *what* (Odoo standards, finance/tax, PM method,
BA discovery, consulting frameworks, sales scripts). This pack answers *how a
senior does it well*: the expert techniques, decision heuristics and the
junior-vs-senior anti-patterns that separate a principal consultant, solution
architect and delivery lead from a beginner.

`digest()` grounds the agents' prompts with the senior operating overlay;
`skills_for(text)` returns the relevant skills for a requirement; `for_role(role)`
returns the skill set for one delivery role — all deterministic, NO API.
"""
from __future__ import annotations

import re
from typing import Optional

# --------------------------------------------------------------------------- #
# Skill library — grouped by discipline. Each entry carries the senior
# technique, a one-line reflex heuristic, and the anti-pattern it avoids.
# --------------------------------------------------------------------------- #
SKILLS = [
    # ---- Solution architecture -------------------------------------------- #
    dict(area="Solution Architecture", level="expert",
         keys=["architecture", "fit-gap", "fit gap", "design", "solution", "blueprint",
               "standard-first", "customis", "customiz", "scope"],
         skill="Standard-first fit-gap",
         expert="Map every requirement to the closest standard Odoo capability BEFORE "
                "considering config, then Studio, then custom-on-top (inherit, never "
                "fork). Record the decision and the reason per requirement so scope is "
                "traceable and upgrade-safety is provable.",
         heuristic="If it can be a setting, it is not a customisation — prove a standard "
                   "path exists before quoting build.",
         antipattern="Quoting bespoke development for a need Odoo already ships, or "
                     "overwriting core instead of extending it."),
    dict(area="Solution Architecture", level="expert",
         keys=["integration", "api", "interface", "middleware", "sync", "webhook",
               "connector", "third-party", "third party"],
         skill="Integration architecture",
         expert="Choose the pattern deliberately: real-time API vs batch, sync vs async, "
                "point-to-point vs middleware. Design for idempotency, retries with "
                "back-off, an error queue, reconciliation and observability. Own the "
                "canonical source of truth per data object.",
         heuristic="Every integration needs an answer to 'what happens when it fails at "
                   "3am' before it ships.",
         antipattern="Fire-and-forget calls with no retry, no dedupe key and no "
                     "reconciliation — silent data drift."),
    dict(area="Solution Architecture", level="expert",
         keys=["data model", "master data", "schema", "relationships", "multi-company",
               "multi company", "chart of accounts", "coa", "hierarchy"],
         skill="Data model & master-data design",
         expert="Design master data once — products, partners, CoA, analytic structure, "
                "warehouses, companies — so it serves finance, ops and reporting together. "
                "Get the analytic/dimensional model right early; it is expensive to "
                "retrofit after go-live.",
         heuristic="Reporting you will want in year two is decided by the master-data "
                   "structure you set in week two.",
         antipattern="Letting each department model its own codes, then discovering "
                     "consolidated reporting is impossible."),
    dict(area="Solution Architecture", level="expert",
         keys=["performance", "scale", "volume", "slow", "batch", "index", "load"],
         skill="Performance & scalability",
         expert="Size for realistic peak volumes. Prefer stored computes and read_group "
                "over Python loops, batch ORM writes, add indexes on searched fields, and "
                "move heavy work to scheduled/queue jobs. Test with production-scale data, "
                "not ten demo records.",
         heuristic="It works on 10 rows means nothing; profile against a year of real "
                   "transactions.",
         antipattern="N+1 ORM calls in a loop and unstored computes on list views that "
                     "melt under real volume."),

    # ---- Data migration ---------------------------------------------------- #
    dict(area="Data Migration", level="expert",
         keys=["migration", "migrate", "data load", "etl", "cutover", "opening balance",
               "legacy", "cleansing", "reconcil"],
         skill="Migration & cutover mastery",
         expert="Run extract → cleanse → map → load → reconcile in mock cycles before the "
                "real cutover. Migrate master data first, then open items and balances. "
                "Reconcile every load to source control totals (AR/AP/stock/GL) and get "
                "sign-off. Rehearse the cutover on a timeline with a rollback point.",
         heuristic="No balance is migrated until it reconciles to the source to the "
                   "penny and someone signs it.",
         antipattern="A single big-bang load on go-live night with no mock run and no "
                     "reconciliation — the classic go-live killer."),

    # ---- Requirements engineering / BA ------------------------------------ #
    dict(area="Business Analysis", level="expert",
         keys=["requirement", "elicit", "discovery", "workshop", "interview", "user story",
               "acceptance", "traceability", "moscow", "backlog"],
         skill="Requirements engineering",
         expert="Elicit with process walk-throughs and 5-Whys, not feature wish-lists. "
                "Write each requirement with a testable acceptance criterion, prioritise "
                "with MoSCoW, and keep a traceability matrix requirement → design → test "
                "→ sign-off. Separate the real business outcome from the stated solution.",
         heuristic="Ask for the outcome and the exception, not the screen they think they "
                   "want.",
         antipattern="Transcribing 'make it like our old system' as a spec instead of "
                     "questioning the underlying need."),
    dict(area="Business Analysis", level="expert",
         keys=["process", "as-is", "to-be", "bpmn", "swimlane", "handoff", "bottleneck",
               "waste"],
         skill="Process analysis & redesign",
         expert="Map as-is with swimlanes and metrics (cycle time, handoffs, rework), "
                "find the constraint, then design a to-be that removes non-value-add steps "
                "and automates handoffs — mapped onto standard Odoo flows, not the old way "
                "re-implemented.",
         heuristic="Automate the redesigned process, never the current mess.",
         antipattern="Digitising the existing broken workflow one-for-one, baking the "
                     "waste into the system."),

    # ---- Estimation & delivery management ---------------------------------- #
    dict(area="Delivery Management", level="expert",
         keys=["estimate", "estimation", "sizing", "effort", "timeline", "plan",
               "critical path", "dependency", "wbs"],
         skill="Estimation & planning",
         expert="Estimate bottom-up from a work-breakdown, three-point (optimistic/likely/"
                "pessimistic) with explicit contingency for integration, migration and "
                "UAT rework. Sequence by the critical path and hard dependencies; put the "
                "riskiest, most uncertain work first to retire risk early.",
         heuristic="Add contingency to the integration and data work — that is where "
                   "estimates die, not the config.",
         antipattern="Single-point 'happy path' estimates with no contingency, then "
                     "surprise slippage in the last mile."),
    dict(area="Delivery Management", level="expert",
         keys=["risk", "issue", "raid", "mitigation", "contingency", "assumption",
               "dependency register"],
         skill="Risk & issue management",
         expert="Keep a live RAID log. Score risks impact × likelihood, assign an owner "
                "and a dated mitigation, and review it every week. Convert realised risks "
                "into issues with an action and a decision. Surface bad news early — it is "
                "cheapest when small.",
         heuristic="A risk without an owner and a date is a wish, not a mitigation.",
         antipattern="A risk register written once at kickoff and never reopened until it "
                     "becomes a crisis."),
    dict(area="Delivery Management", level="expert",
         keys=["scope", "change request", "change order", "creep", "baseline", "variation"],
         skill="Scope & change control",
         expert="Baseline scope in the SOW, then run every new ask through a change "
                "request with impact on cost, timeline and risk. Protect the critical path; "
                "trade scope in/out visibly. Say yes to change — priced and scheduled — "
                "not yes to silent creep.",
         heuristic="Every 'small extra' has a price and a place in the plan; make both "
                   "explicit before you build it.",
         antipattern="Absorbing 'quick favours' until the margin and the timeline are "
                     "gone."),

    # ---- Stakeholder & executive management -------------------------------- #
    dict(area="Stakeholder Leadership", level="expert",
         keys=["stakeholder", "executive", "sponsor", "steering", "governance",
               "expectation", "escalation", "c-level", "board"],
         skill="Executive stakeholder management",
         expert="Map stakeholders by power × interest and tailor the message to each. Run "
                "a steering committee on outcomes and decisions, not status theatre. Manage "
                "expectations proactively, escalate with options not just problems, and "
                "keep the sponsor bought-in and unblocking.",
         heuristic="Bring decisions and options to the steerco, not a list of things that "
                   "went wrong.",
         antipattern="Reporting green until the week it slips; ambushing the sponsor with "
                     "problems and no recommendation."),
    dict(area="Stakeholder Leadership", level="expert",
         keys=["facilitation", "workshop", "decision", "alignment", "consensus",
               "conflict"],
         skill="Facilitation & decision-making",
         expert="Run workshops with a clear objective, pre-read, timebox and a decision "
                "log. Draw out the quiet expert, park tangents, force a decision or a named "
                "owner and date. Leave every session with actions, not just discussion.",
         heuristic="A workshop that ends without a decision or an owner was a meeting, not "
                   "a workshop.",
         antipattern="Open-ended sessions that reopen settled decisions and never "
                     "converge."),

    # ---- Change & adoption ------------------------------------------------- #
    dict(area="Change & Adoption", level="expert",
         keys=["change management", "adoption", "training", "super-user", "super user",
               "resistance", "hypercare", "go-live", "rollout"],
         skill="Change & adoption leadership",
         expert="Drive adoption with ADKAR: awareness → desire → knowledge → ability → "
                "reinforcement. Build a super-user network, train by role on real data, "
                "communicate the why, and staff hypercare hard for the first weeks. Measure "
                "adoption, not just training attendance.",
         heuristic="Go-live is the start of adoption, not the finish line — resource "
                   "hypercare accordingly.",
         antipattern="A one-off training the week before go-live and no reinforcement, so "
                     "users quietly revert to spreadsheets."),

    # ---- Commercial & negotiation ------------------------------------------ #
    dict(area="Commercial", level="expert",
         keys=["pricing", "margin", "commercial", "profitability", "package", "discount",
               "value", "roi", "business case", "tco"],
         skill="Commercial acumen",
         expert="Price to value and outcome, not hours. Protect margin by controlling "
                "scope and reuse; know the cost-to-serve of every line. Build the client's "
                "business case (ROI, payback, TCO) so the investment is self-justifying and "
                "discount pressure drops.",
         heuristic="Anchor on the value delivered and the cost of the status quo, then the "
                   "price is a rounding error.",
         antipattern="Defending a day-rate line-by-line instead of the outcome, and "
                     "discounting scope away to win."),
    dict(area="Commercial", level="expert",
         keys=["negotiation", "close", "closing", "procurement", "objection", "meddic",
               "mutual action", "terms", "concession"],
         skill="Negotiation & closing",
         expert="Qualify with MEDDIC (metrics, economic buyer, decision criteria/process, "
                "pain, champion). Drive to a mutual action plan with dates. Trade, never "
                "just give — every concession buys something back. Handle procurement on "
                "value and total cost, protecting price with scope and terms.",
         heuristic="Never concede without a trade, and never negotiate against yourself.",
         antipattern="Cutting price to 'get it over the line' before value and the "
                     "economic buyer are established."),
    dict(area="Commercial", level="expert",
         keys=["consultative", "spin", "challenger", "value selling", "discovery call",
               "qualify", "presales"],
         skill="Consultative discovery",
         expert="Sell by diagnosing. Use SPIN (situation → problem → implication → "
                "need-payoff) to make the cost of the status quo vivid before proposing. "
                "Bring an insight that reframes the problem (challenger), quantify the pain, "
                "and let the client conclude they need to act.",
         heuristic="Make the pain of doing nothing bigger than the effort of change — then "
                   "you are guiding, not pushing.",
         antipattern="Pitching features in the first meeting before understanding the "
                     "business pain and its cost."),

    # ---- Communication ----------------------------------------------------- #
    dict(area="Communication", level="expert",
         keys=["communication", "storytelling", "report", "presentation", "executive "
               "summary", "pyramid", "so what", "narrative"],
         skill="Executive communication",
         expert="Lead with the answer (Pyramid Principle): recommendation first, then the "
                "few reasons, then the detail on demand. Every chart earns a 'so-what' "
                "takeaway. Write for the busiest reader in the room and make the decision "
                "you want obvious.",
         heuristic="If the reader stops after the first line, they should still have the "
                   "decision.",
         antipattern="Building to a conclusion over 20 slides of context the executive "
                     "will never reach."),

    # ---- Quality & engineering craft --------------------------------------- #
    dict(area="Quality & Governance", level="expert",
         keys=["quality", "definition of done", "review", "uat", "test", "code review",
               "gate", "sign-off", "acceptance criteria"],
         skill="Quality gates & definition of done",
         expert="Define 'done' up front — built, peer-reviewed, tested against acceptance "
                "criteria, documented and demoed. Gate each phase on evidence, not opinion. "
                "UAT runs to scripts derived from the requirements with real users on real "
                "data, and sign-off is explicit.",
         heuristic="Done means someone other than the builder verified it against the "
                   "acceptance criteria.",
         antipattern="'It works on my machine' demos and UAT that is really the first time "
                     "anyone tested it."),
]

# --------------------------------------------------------------------------- #
# Which senior skills each delivery role leans on most.
# --------------------------------------------------------------------------- #
ROLE_SKILLS = {
    "functional": ["Standard-first fit-gap", "Data model & master-data design",
                   "Process analysis & redesign", "Quality gates & definition of done"],
    "developer": ["Integration architecture", "Performance & scalability",
                  "Standard-first fit-gap", "Quality gates & definition of done"],
    "ba": ["Requirements engineering", "Process analysis & redesign",
           "Facilitation & decision-making", "Executive communication"],
    "ba_discovery": ["Requirements engineering", "Process analysis & redesign",
                     "Facilitation & decision-making"],
    "proposal": ["Commercial acumen", "Consultative discovery", "Estimation & planning",
                 "Executive communication"],
    "presales": ["Consultative discovery", "Negotiation & closing", "Commercial acumen",
                 "Executive communication"],
    "pm": ["Estimation & planning", "Risk & issue management", "Scope & change control",
           "Executive stakeholder management", "Change & adoption leadership"],
    "project": ["Estimation & planning", "Risk & issue management", "Scope & change control",
                "Executive stakeholder management"],
    "director": ["Executive stakeholder management", "Commercial acumen",
                 "Executive communication", "Risk & issue management"],
    "config": ["Standard-first fit-gap", "Data model & master-data design"],
    "docwriter": ["Executive communication", "Requirements engineering",
                  "Quality gates & definition of done"],
    "prospect": ["Consultative discovery", "Commercial acumen"],
    "outreach": ["Consultative discovery", "Executive communication"],
    "comms": ["Executive communication", "Consultative discovery"],
    "research": ["Consultative discovery", "Executive communication"],
}

# --------------------------------------------------------------------------- #
# Cross-cutting operating principles a senior applies on every engagement.
# --------------------------------------------------------------------------- #
SENIOR_PRINCIPLES = [
    "Standard-first, always: config → native automation → Studio → custom-on-top "
    "(inherit, never fork).",
    "Retire the biggest risk first — integration, migration and adoption fail projects, "
    "not configuration.",
    "Quantify everything: no pain, benefit or option without a number and a source.",
    "Decisions, owners and dates — every meeting and every risk ends with all three.",
    "Protect the baseline: welcome change, but priced, scheduled and signed.",
    "Surface bad news early and small, with options, not late and large, with excuses.",
    "Design master data and reporting on day one; it is the most expensive thing to "
    "retrofit.",
    "'Done' is verified by someone other than the builder against acceptance criteria.",
    "Sell and deliver the outcome, not the hours; anchor on the cost of the status quo.",
    "Transfer knowledge as you go — the goal is a client who can run it without you.",
]

# --------------------------------------------------------------------------- #
# The junior → senior maturity ladder (how the same task is done at each level).
# --------------------------------------------------------------------------- #
MATURITY = [
    ("Junior", "Executes tasks as told; takes requirements literally; single-point "
               "estimates; reports status."),
    ("Consultant", "Questions the need; maps to standard Odoo; estimates with "
                   "contingency; manages a workstream."),
    ("Senior", "Owns the solution design and the risk; controls scope; manages "
               "stakeholders; coaches the team."),
    ("Principal", "Owns the outcome and the commercials; reframes the client's problem; "
                  "trusted by the sponsor to advise, not just deliver."),
]


# --------------------------------------------------------------------------- #
# Accessors
# --------------------------------------------------------------------------- #
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())


def skills_for(text: str, limit: int = 6) -> list[dict]:
    """Return the senior skills whose keywords match the requirement text,
    ranked by number of matched keywords."""
    t = _norm(text)
    scored = []
    for sk in SKILLS:
        hits = sum(1 for k in sk["keys"] if k in t)
        if hits:
            scored.append((hits, sk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:limit]]


def for_role(role: str) -> list[dict]:
    """The senior skill set a given delivery role leans on."""
    names = ROLE_SKILLS.get(role, [])
    by_name = {s["skill"]: s for s in SKILLS}
    return [by_name[n] for n in names if n in by_name]


def areas() -> list[str]:
    seen, out = set(), []
    for s in SKILLS:
        if s["area"] not in seen:
            seen.add(s["area"])
            out.append(s["area"])
    return out


def advise(requirement: str) -> Optional[dict]:
    """Senior-skill guidance for one requirement (heuristics + anti-patterns)."""
    matched = skills_for(requirement, limit=4)
    if not matched:
        return None
    return {
        "skills": [s["skill"] for s in matched],
        "how": [s["expert"] for s in matched],
        "heuristics": [s["heuristic"] for s in matched],
        "avoid": [s["antipattern"] for s in matched],
    }


def digest() -> str:
    """A compact senior-practitioner overlay to embed in an agent's prompt."""
    principles = "\n".join("- " + p for p in SENIOR_PRINCIPLES)
    heur = "; ".join(f"{s['skill']}: {s['heuristic']}" for s in SKILLS)
    return ("SENIOR-PRACTITIONER SKILLS (operate at principal level; these override "
            "generic habits).\n"
            "Operating principles:\n" + principles + "\n"
            "Skill reflexes: " + heur + "\n"
            "Maturity target: " + " → ".join(m[0] for m in MATURITY) +
            " — own the outcome, the design and the risk, not just the task.")
