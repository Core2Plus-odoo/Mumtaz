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

## D2 — Anthropic is the default model provider, on the owner's account

**Decided:** 2026-11-10, by the owner.
**Answers:** Q4.

Default provider for Mumtaz Intelligence is Anthropic, billed to the owner's
own account.

### What this does not mean

The spec's Part 4 says "do not make the entire product dependent on one AI
provider", and that still holds. Anthropic is the **default**, not the only
path. `mumtaz_ai` already has `openai_provider` and `anthropic_provider` behind
a `base_provider` abstraction, and the c2p stack already routes to
OpenAI-compatible endpoints including Ollama. Choosing a default is a
configuration decision; removing the abstraction would be an architectural one,
and is not authorised by this.

### What it unblocks and what it still needs

Backlog item 2 (model routing and provider abstraction) is unblocked except for
the key itself. **The key never travels through chat.** It belongs in the
environment's secret store, and on the Odoo side in the existing settings
field, which is already write-only in the form.

### Two things found while checking the existing provider

1. **`addons/mumtaz_ai/providers/anthropic_provider.py` pins
   `_DEFAULT_MODEL = "claude-haiku-4-5-20251001"`.** That is a dated snapshot of
   an older generation. Current models are the Claude 5 family. Worth updating
   deliberately, with a note that pinning a dated snapshot is the right habit —
   the problem is the age, not the pinning.
2. **`max_tokens` defaults to 600.** Fine for a chat reply, too small for an
   agent returning a structured analysis. Per-task limits belong with per-task
   model routing.

### Per-task routing

Follow the pattern already proven in `llm.model_for(task)`: a cheaper, faster
model for classification, routing and short drafts; a stronger one for
analysis, consolidation and anything a person will act on. Set per task, not
globally, and per tenant where the control plane meters it.

Cost tracking already has somewhere to live: `token_usage` and `model_used` are
on `mumtaz.ai.message`, and `usage_metric` is on the control plane. Part 12's
model usage budgets attach there rather than needing new machinery.

---

## Open questions

Carried from `AI_AGENT_PHASE1_ASSESSMENT.md`. Backlog item 1 needs Q4 at
minimum; the rest can follow.

| # | Question | Blocks |
| --- | --- | --- |
| Q1 | **Urdu** — in scope for Jewel, or only the wider platform? It changes voice, fonts and RTL testing | Prompts, voice, Command Centre |
| Q2 | **Palette** — emerald/charcoal/champagne gold as the spec says, or the current indigo? Two live side by side today | Command Centre screens |
| Q3 | **Frontend** — OWL inside Odoo, or a separate application? The spec prefers Next.js "if not established", but it *is* established and is not Next.js | Backlog item 12 |
| ~~Q4~~ | ~~AI provider and account~~ **Answered 2026-11-10: Anthropic, owner's account (D2).** The per-tenant budget is still unset | — |
| Q5 | **Deployment target** for the first agent service — development, staging, or the jewel staging host | Backlog item 2 |
| Q6 | **Autonomy thresholds** — the financial limits above which approval is required. A finance decision, not a development one, and the same rule applies as to VAT and AML values: configuration for a named person to confirm, never invented here | Backlog item 3 |
| Q7 | **Character artwork** — five portraits were generated and committed to `website/jewel/site/img/agents/`. Confirm these, or supply the intended ones | Command Centre |
