# C2P Agency OS — Master Build Brief

> A development brief for building the C2P autonomous delivery agency: an
> AI-operated professional-services firm that runs the entire Odoo-delivery
> lifecycle — from lead generation to live project delivery — with specialist
> agents, human approval at the moments that matter, and Odoo as the system of
> record. Hand this to Claude Code (or a build team) and execute in the phases
> defined at the end. Reuse the existing `delivery-api` backbone; do not start over.

---

## 1. North star

Turn C2P Consultants into an **automated agency**: leads are found, qualified,
and engaged; branded proposals are drafted and sent after a human says yes;
projects are planned and delivered; Odoo functional and technical work is done by
specialist agents that *remember every client*; and clients are communicated with
across channels — all orchestrated, logged, and supervised by a human owner who
approves the few decisions that carry money, reputation, or code into production.

The measure of success is not "no humans" — it is **leverage**: one founder runs
the throughput of a 15-person agency, with quality held at Big-4 standard and
nothing client-facing or irreversible happening without an approval.

## 2. Non-negotiable design principles

1. **Odoo is the system of record.** Every business object lives in Odoo's native
   pipeline (CRM lead → Sales order → Project). Agents augment Odoo; they never
   rebuild standard functionality. (This is the same rule the functional agent
   already enforces — apply it system-wide.)
2. **Human-in-the-loop at the right gates.** Outbound to a client, pricing,
   contracts, and deploying code are *approval-required*. Everything internal and
   reversible can run autonomously. The approval layer is core architecture, not a
   feature bolted on later.
3. **Client knowledge compounds.** Every client has a persistent knowledge base
   that every agent reads before acting and writes to after. The agency gets
   smarter about each account over time.
4. **Everything is structured, logged, and traceable.** Every agent returns
   structured data, every action is recorded against the account, every decision
   has an author (agent or human).
5. **Build on the backbone.** The existing `delivery-api` (FastAPI) already runs
   five agents over a shared engagement with Odoo write-back and a durable store.
   Extend that spine — new agents, the approval layer, the knowledge base, and the
   communication layer all attach to it.
6. **C2P brand and standard throughout.** Teal `#00B3B3` / Deep Teal `#008080` /
   Charcoal `#2E2E2E`; Space Grotesk + Inter; every client-facing artifact is
   production-ready on the first pass.

## 3. The agent roster

Each agent is a system-prompted Claude call behind a `delivery-api` endpoint,
returning structured JSON, consuming the account's knowledge base and prior-stage
outputs. Defined below as: **mission · trigger · consumes · produces · Odoo
touchpoint · autonomy.**

**A. Prospector** (extends C2P Pathfinder)
Find ICP-fit companies. · Trigger: scheduled / on-demand. · Consumes: ICP
definition, exclusion list. · Produces: ranked prospect list with firmographics
and signals. · Odoo: none (pre-CRM). · Autonomy: **auto**, results queued.

**B. Researcher / Enricher**
Deep-research a prospect: structure, stack, pains, stakeholders, triggers. ·
Consumes: prospect. · Produces: an enrichment dossier into the knowledge base. ·
Odoo: none. · Autonomy: **auto**.

**C. Qualifier** (the existing Presales agent)
Score ICP fit; turn pains into candidate requirements; name Odoo modules in play;
recommend pursue / nurture / pass. · Produces: qualification + candidate
requirements. · Odoo: creates the `crm.lead`. · Autonomy: **auto**, but "pursue"
opens an outreach draft that is gated.

**D. Outreach (SDR)**
Draft and run first-touch and follow-up sequences across email / LinkedIn /
WhatsApp, personalised from the dossier. · Produces: channel-ready messages +
sequence plan. · Odoo: logs to lead chatter. · Autonomy: **approval-required to
send** (configurable per channel; nurture follow-ups can be auto once a template
is approved).

**E. Proposal** (the existing Proposal agent, upgraded to branded output)
Turn discovery into a **branded** proposal: solution, scope, phased plan, effort
estimate, AED pricing (+VAT), assumptions, timeline, success criteria — rendered
in the C2P template as a shareable document/PDF. · Odoo: creates the `sale.order`
(quotation). · Autonomy: **approval-required before it reaches the client.**

**F. Approval Orchestrator**
Route every gated action to the human owner, capture approve / edit / reject with
a reason, and release or revise the action. · Produces: decisions + audit trail. ·
Odoo: none (operates over the engagement). · Autonomy: **human**; this is the gate.

**G. Project Planner** (existing Project agent)
Won proposal → implementation plan (phases, milestones, tasks, RAID, governance).
· Odoo: creates `project.project` + `project.task`. · Autonomy: **auto** on win,
plan reviewable.

**H. Functional Consultant — Odoo** (built)
Requirement → standard/config/studio/custom verdict + spec, grounded in the
client's live installed modules. · Odoo: reads schema; attaches the spec. ·
Autonomy: **auto**.

**I. Technical / Developer — Odoo** (built)
Custom-verdict spec → installable module (version-correct). · Odoo: the generated
module deploys via the client's addons repo / Odoo.sh. · Autonomy: **auto to
generate; approval-required to deploy** to a client environment.

**J. Account Memory / Client Knowledge**
Own the per-client knowledge base: read the relevant slice for any agent before it
acts, write back what was learned after. · Autonomy: **auto** (the memory layer).

**K. Communications**
Handle ongoing client conversation across email / WhatsApp / Odoo chatter: triage
inbound, draft replies, escalate. · Odoo: logs all comms to the partner/lead/
project chatter. · Autonomy: **approval-required by sensitivity** (status updates
auto; anything touching scope, money, or commitments gated).

**L. Agency Supervisor (orchestrator)**
The meta-agent: move work between agents, advance the pipeline, and surface to the
owner exactly what needs a human decision. · Produces: the daily "what needs you"
queue. · Autonomy: **auto** routing; never overrides a gate.

*Optional later:* **Delivery/QA** (review deliverables before client-facing),
**Finance/Billing** (Odoo invoicing + dunning), **Voice** (Zaki-style spoken
briefings to the owner).

## 4. Client knowledge base (the memory that compounds)

A persistent per-account store, keyed to the Odoo partner, holding: company
profile, stakeholders and roles, current systems and **live Odoo configuration**,
decision log, requirement history, every deliverable, full communication history,
stated preferences, and open risks. Implemented as structured records plus a
retrievable text index (Postgres + a vector column, or equivalent). **Contract:**
every client-touching agent loads the relevant slice as context before acting and
appends what it learned afterward. This is what makes the agency feel like it has
worked with the client for years.

## 5. Approval layer (the trust spine)

A policy that maps each action type to an autonomy level. The Approval
Orchestrator enforces it; the owner sees a single approval queue (in the console
and pushed via WhatsApp/email) with approve / edit / reject + reason, all audited.

| Action | Default autonomy |
|---|---|
| Prospect, research, qualify, plan, analyse, generate code | Auto |
| Internal status updates, logging to Odoo | Auto |
| First-touch / any outbound to a prospect or client | Approval required |
| Proposal or quotation sent to client | Approval required |
| Pricing or discount beyond a set threshold | Approval required |
| Contract / commercial commitment | Approval required |
| Deploying custom code to a client environment | Approval required |
| Client communication touching scope, money, or commitments | Approval required |

Every threshold is configurable. Nothing irreversible or client-facing ships
without a recorded human decision.

## 6. Communication layer

Channels: **email** (provider or SMTP/IMAP), **WhatsApp** (Business API — already
in your Mumtaz nurture stack), and **Odoo chatter** as the canonical log. Inbound
is triaged and routed to the right agent/account; outbound is drafted by the
Communications agent, gated by the policy above, then sent and logged. Every
message, in or out, lands on the account's knowledge base and the Odoo record.

## 7. Data model

Extend the existing engagement spine:
- **Account** — the client (1:1 with an Odoo partner); owns the knowledge base.
- **Engagement** — a deal/project through the lifecycle (existing object).
- **StageOutput** — structured output per agent run (existing).
- **Approval** — a gated action: payload, requester agent, decision, reason,
  timestamp, author.
- **KnowledgeEntry** — a fact/dossier/decision/comm on an account, retrievable.
- **Communication** — an inbound/outbound message with channel, status, links.
- **Deliverable** — proposal, spec, module, plan — versioned, linked to Odoo.

All business objects mirror to Odoo (partner, lead, sale.order, project,
attachments, chatter); the app DB holds working state, the approval queue, and the
knowledge index.

## 8. Tech stack (consistent with C2P)

- **Backbone:** extend `delivery-api` (FastAPI) — one service, agent endpoints,
  orchestration, approval queue, knowledge API.
- **Agents:** Claude (current Sonnet) with structured-JSON contracts; web search
  for prospecting/research; per-agent system prompts as the IP.
- **Odoo:** Odoo 19 / Odoo.sh + tenant DBs over XML-RPC (introspection + writes).
- **App state & knowledge:** Postgres (+ vector) — graduate from the current SQLite.
- **Comms:** WhatsApp Business API, email provider; Odoo chatter as log.
- **Frontends:** static HTML consoles (the existing design system) on Nginx /
  Hostinger VPS, under `*.mumtaz.digital` subdomains; one **Agency Cockpit** for
  the owner (pipeline + approval queue + per-account knowledge), plus the existing
  five-stage delivery console.
- **Optional voice:** ElevenLabs for spoken owner briefings (Zaki pattern).

## 9. The owner's surface — Agency Cockpit

One screen the founder lives in: the pipeline across all accounts; the **approval
queue** (the only thing demanding attention); each account's knowledge base and
live status; and a daily Supervisor briefing of "what needs you today." Everything
else runs underneath.

## 10. Guardrails

- The autonomy policy (§5) is enforced centrally; no agent can bypass a gate.
- Every action is attributed and logged; the owner can audit any decision.
- Agents never invent client facts — unknowns are flagged, not assumed.
- Don't-overbuild rule applies everywhere: prefer standard Odoo; escalate to
  custom only when proven necessary.
- Secrets (API keys, client credentials) live only in server-side config, never
  in code, logs, or client-facing output.

## 11. Build phases

- **Phase 0 — Foundation (done).** `delivery-api` backbone, five stage agents,
  unified console, durable store, Odoo write-back.
- **Phase 1 — Top of funnel + memory.** Prospector, Researcher, the client
  knowledge base, and the Account Memory contract wired into existing agents.
- **Phase 2 — Outreach + approval layer.** SDR agent, Approval Orchestrator,
  approval queue in the cockpit, WhatsApp/email send paths (gated).
- **Phase 3 — Branded proposals.** Proposal agent → C2P-templated PDF; gated send;
  quotation in Odoo.
- **Phase 4 — Delivery in the loop.** Functional + Developer agents consuming live
  client config; gated code deploy to client Odoo / addons repo.
- **Phase 5 — Communications.** Inbound triage, drafted+gated outbound, full
  chatter logging on every account.
- **Phase 6 — Cockpit + Supervisor.** Agency Cockpit, daily briefing, autonomy
  tuning, metrics (pipeline value, win rate, cycle time, utilisation).

Each phase ships independently and is usable on its own. Build in order; do not
skip the approval layer (Phase 2) before sending anything to a client.

## 12. Definition of done (system level)

A prospect can be found, researched, qualified, and (after the owner approves)
contacted; a branded proposal can be produced and (after approval) sent and
recorded in Odoo; a won deal becomes a planned Odoo project; requirements are
analysed and, where custom, built and (after approval) deployed; the client is
communicated with across channels; and **every account accumulates knowledge that
makes the next interaction sharper** — with the owner approving only money,
reputation, and production-code decisions from a single cockpit.

---

### How to use this brief

Feed it to Claude Code as the founding spec, then build **Phase 1** first against
the existing `delivery-api`. Ask for the per-phase build prompt when you reach each
phase — each one expands into its own detailed task list (endpoints, prompts, data
model changes, and acceptance tests).
