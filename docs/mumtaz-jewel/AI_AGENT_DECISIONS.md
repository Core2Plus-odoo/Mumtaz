# Mumtaz Intelligence — decisions

The running record of decisions on the AI workstream: what was decided, when,
and what followed from it. One entry per decision. Open questions sit at the
bottom until they are answered.

---

## D1 — The agent roster is Zayan, Amara, Noor, Rayan and Layla

**Decided:** 2026-11-10, by the owner.
**Supersedes:** the four agents named in `IMPLEMENTATION_ROADMAP.md` Slice 5 —
Memory, Stylist, Relationship and Owner analyst.
**Resolves:** conflict #5 in `AI_AGENT_PHASE1_ASSESSMENT.md` §2.1.

### Why this needed deciding

Two rosters existed, doing overlapping work. The roadmap's four were organised
around the client relationship; the spec's five are organised around business
functions. Building both would have produced two agents drafting the same
follow-up with different names.

### Where the old four's work goes

Nothing is dropped. Each of the four maps onto the new cast, and two of them
turn out to be the same job.

| Retired | Goes to | Note |
| --- | --- | --- |
| **Memory** | **Not an agent — a platform service** | "Keep the client file current from what happened" is something every agent reads, not a character with a personality. It becomes the memory and context service (`ai_memory_records`, `ai_context_snapshots`). Making it an agent was the weaker design |
| **Stylist** | **Layla**, with **Noor** | "Recommend suitable products", "identify cross-selling opportunities", customer 360. Noor supplies the product knowledge Layla reasons over |
| **Relationship** | **Layla** | "Suggest customer follow-ups", "customer communication drafting", "prepare customer engagement recommendations". Stylist and Relationship were always one job split in two |
| **Owner analyst** | **Zayan**, with **Amara** | "Prepare executive summaries", "understand overall business performance", "decision support". Amara supplies the financial content; Zayan speaks it |

### What the new roster adds

- **Amara** — finance. The old four had no financial agent at all.
- **Rayan** — pricing analysis. Also new, and see the caution below.

### Caution carried forward from the assessment

**Rayan does not compute prices.** The spec's responsibility list reads as if he
does. The pricing engine is a pure library with 19 unit tests and no Odoo
imports; only a deterministic function can honour the spec's own requirement to
preserve rate, currency, unit, purity, timestamp, rule version and calculation
breakdown. Rayan's job is to *call* the engine, interpret the result, compare
scenarios, find inconsistencies and recommend. This is a review gate, not a
preference.

### What changed because of this decision

- `website/jewel/index.html` — the AI section now shows the five.
- `website/jewel/preview/index.html` — the AI layer screen shows the five; the
  Stylist screen is attributed to Layla.
- `website/jewel/intelligence/` — already built on the five; now the only
  roster, not an alternative.
- `IMPLEMENTATION_ROADMAP.md` Slice 5 — renamed.
- Backlog items 7–10 in `AI_AGENT_PHASE1_ASSESSMENT.md` §8 stand as written.

### Still true regardless of the roster

Autonomy A–E, the cap on Private and Royal clients, "a number is read and never
produced", and "an agent runs as the invoking user" are platform rules. They
bind whichever agents exist.

---

## Open questions

Carried from `AI_AGENT_PHASE1_ASSESSMENT.md`. Backlog item 1 needs Q4 at
minimum; the rest can follow.

| # | Question | Blocks |
| --- | --- | --- |
| Q1 | **Urdu** — in scope for Jewel, or only the wider platform? It changes voice, fonts and RTL testing | Prompts, voice, Command Centre |
| Q2 | **Palette** — emerald/charcoal/champagne gold as the spec says, or the current indigo? Two live side by side today | Command Centre screens |
| Q3 | **Frontend** — OWL inside Odoo, or a separate application? The spec prefers Next.js "if not established", but it *is* established and is not Next.js | Backlog item 12 |
| Q4 | **AI provider and account** — both `mumtaz_ai` providers are unconfigured. Which provider, whose account, what budget per tenant? | Backlog item 2 |
| Q5 | **Deployment target** for the first agent service — development, staging, or the jewel staging host | Backlog item 2 |
| Q6 | **Autonomy thresholds** — the financial limits above which approval is required. A finance decision, not a development one, and the same rule applies as to VAT and AML values: configuration for a named person to confirm, never invented here | Backlog item 3 |
| Q7 | **Character artwork** — five portraits were generated and committed to `website/jewel/site/img/agents/`. Confirm these, or supply the intended ones | Command Centre |
