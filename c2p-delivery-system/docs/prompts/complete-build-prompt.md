# C2P Agency OS — Complete Build Prompt

> A complete, executable brief for **Claude Code** to build the entire C2P Agency
> OS on top of the existing backbone in this repo. Build in phases; each phase
> ships and is testable on its own; never break what already works. Reuse the
> backbone — do not start over.

---

## Context — what already exists

This repo (`c2p-agency-os`) already contains a working foundation:

- `api/` — a FastAPI service (`delivery-api`) with **five agents** wired as
  endpoints: presales, proposal, project, functional, developer. It has a shared
  **engagement** object, a durable **SQLite store** (`store.py`), **Odoo
  write-back** (`sync.py`: lead → quotation → project + JSON attachments), and an
  **XML-RPC bridge** (`odoo.py`: introspection + record creation). Agent system
  prompts live in `api/prompts.py`.
- `console/` — a single-page operator UI for the five-stage pipeline.
- `deploy/` — installer, systemd, nginx.
- `docs/` — vision, architecture, the master build brief, and the productization
  plan. **Read `docs/00`–`docs/03` and all of `api/` before writing code.**

You are extending this into the complete product defined in `docs/02` and `docs/03`.

## Global rules (apply to every phase)

1. **Reuse, don't rebuild.** Extend `main.py`, `prompts.py`, `store.py`,
   `sync.py`, `odoo.py`. Keep every existing endpoint working.
2. **Odoo is the system of record.** Every business object mirrors to Odoo (lead,
   quotation, project, attachments, chatter). Agents augment standard Odoo; never
   rebuild standard functionality — prefer config, escalate to custom only when
   proven.
3. **Every agent** = a system prompt in `prompts.py` + an endpoint + a strict
   **JSON contract** + persisted to the store + logged to the account.
4. **Approval gates are core.** Any action that is client-facing, costs money, or
   is irreversible goes through the approval layer (Phase 2) — never bypass it.
5. **Client knowledge compounds.** Every client-touching agent loads the account's
   knowledge slice before acting and writes learnings back after.
6. **Secrets never in code or git.** They live only in server-side config /
   per-tenant config. When you need a key or connection, **ask the user**.
7. **Tests + docs.** Write `pytest` acceptance tests per phase; keep existing
   tests green. After each phase, record decisions in `docs/` so the repo stays
   the source of truth.
8. **Structured everywhere.** Agents return only JSON; parse defensively; on bad
   output, fail soft and surface the error.
9. **Own the knowledge.** Route every model call through one abstraction layer so
   the model is swappable, and capture every agent input/output and every approval
   decision as owned, labelled data from Phase 1. See "Knowledge & Independence".

---

## Phase 1 — Top of funnel + client knowledge

1. **Data model.** Add `Account` (1:1 with an Odoo partner; owns knowledge) and
   `KnowledgeEntry`. Link `Engagement` to an `Account`. Extend `store.py` with the
   tables and CRUD.
2. **Client Knowledge service** (`knowledge.py`): `read_slice(account, topic)` and
   `write_entry(account, kind, content)`. Start with keyword retrieval; leave a
   seam for vector search. Endpoints: `GET/POST /accounts/{id}/knowledge`.
3. **Prospector agent**: prompt + `POST /prospect` — ICP in, ranked prospect list
   out (firmographics + signals). Enable web search.
4. **Researcher agent**: prompt + `POST /accounts/{id}/research` — deep dossier
   written into the knowledge base.
5. **Retrofit** the existing presales/functional agents to load the account's
   knowledge slice before running and append learnings after.

**Acceptance:** an ICP yields ranked prospects; research writes a dossier;
qualifier/functional output visibly reflects stored knowledge.

## Phase 2 — Outreach + the approval layer

1. **Approval model + queue.** `Approval` (payload, requesting agent, status,
   decision, reason, author, timestamps). Endpoints: `GET /approvals` (the queue),
   `POST /approvals/{id}/decide`.
2. **Autonomy policy.** A config map of `action → level`
   (auto / approval-required), and an enforcement helper every gated action calls:
   it creates an `Approval` and withholds the action until a human decides.
3. **Outreach (SDR) agent**: prompt + `POST /accounts/{id}/outreach` — personalised
   first-touch + follow-up across email / LinkedIn / WhatsApp. **Sending is gated.**
4. **Channel adapters.** Email + WhatsApp send behind a clean interface (provider
   creds via config). On send, log to Odoo chatter + knowledge base.
5. **Cockpit (approval queue).** Add an approval queue to the console:
   approve / edit / reject + reason; notify the owner via WhatsApp/email.

**Acceptance:** an outreach send creates an approval; approve → it "sends" and is
logged; reject → nothing sends; every decision is audited and attributed.

## Phase 3 — Branded proposals

1. **Renderer.** Turn the proposal agent's JSON into a **branded** proposal
   (HTML → PDF) using the account/tenant brand (logo, colours, fonts).
2. **Brand config** per tenant/account.
3. **Gated send.** Proposal send goes through approval; on approve, attach the PDF
   to the `sale.order` and (optionally) email the client; log everything.

**Acceptance:** the proposal renders in-brand; send is gated; an approved proposal
lands on the Odoo quotation and the comms log.

## Phase 4 — Delivery in the loop

1. **Live grounding.** The functional agent auto-reads the account's installed
   modules and schema (via `odoo.py`) before analysing.
2. **Gated deploy.** On a Custom verdict, the developer agent generates the module;
   **deploying it is approval-required**; on approve, push to the account's addons
   repo (git) so Odoo.sh builds it.
3. Link every deliverable (spec, module, plan) to the Odoo project/lead.

**Acceptance:** functional reflects live modules; a custom requirement produces a
module; deploy requires approval; on approve it's pushed to the addons repo.

## Phase 5 — Communications

1. **Inbound.** Ingest email/WhatsApp, triage to the right account/agent, and
   create tasks or approvals as needed.
2. **Outbound.** A Communications agent drafts replies, gated by sensitivity
   (status updates auto; scope/money/commitments require approval); on send, log
   to chatter + knowledge.

**Acceptance:** an inbound message routes to the correct account; outbound touching
scope/money is gated; all comms are logged on the account and in Odoo.

## Phase 6 — Cockpit + Supervisor + metrics

1. **Supervisor agent**: a daily "what needs you today" briefing — pipeline state,
   pending approvals, risks.
2. **Agency Cockpit UI**: pipeline across all accounts, the approval queue,
   per-account knowledge, and the daily briefing.
3. **Metrics**: pipeline value, win rate, cycle time, utilisation.

**Acceptance:** the cockpit shows pipeline + approvals + per-account knowledge;
the Supervisor briefing generates.

## Phase 7 — Multi-tenant product (the sellable layer)

1. **Tenancy + isolation.** Scope every Account / Engagement / Knowledge / Approval
   to a `tenant_id`. Use **per-tenant data isolation** for client knowledge
   (separate DB or schema) over a **shared control plane** (auth, billing, the
   agent engine).
2. **Auth.** Real tenant users and roles; replace the basic-auth gate with proper
   login.
3. **Per-tenant config.** ICP, autonomy policy, approval thresholds, **brand
   (white-label)**, Odoo connection(s), comms channels, and AI key — all per tenant.
4. **Onboarding.** Sign up → connect Odoo → set brand → set autonomy policy.
5. **Billing/metering.** Subscription + usage (per engagement / agent runs);
   feature-gate the **Delivery / Growth / Agency** editions.
6. **Security.** Per-tenant secret encryption, full audit, data-deletion path.

**Acceptance:** two tenants run fully independently — each with its own brand,
Odoo, and policy; no client data leaks across tenants; usage is metered for
billing.

---

## Knowledge & Independence (cross-cutting — build from Phase 1)

Goal: own the knowledge and reduce model dependency over time. This is **not**
"remove the AI" — it's making the model a swappable part, letting C2P's
accumulated knowledge carry more of each task, and owning the data that gives
future optionality (cheaper models, self-hosting, even fine-tuning your own).
Build these from the start, woven through every phase — not bolted on at the end.

1. **Model-abstraction layer** (`api/llm.py`): a single adapter every agent calls;
   provider and model are **config, not hardcoded**. Support per-task routing
   (a cheap model for simple stages, a strong model for hard ones). No file
   outside this layer may name a specific model. Today it points at Claude;
   swapping it must be a one-line config change.

2. **Solutions library (retrieval-first).** Persist every solved case —
   requirement → verdict → solution → generated module — as a searchable record.
   Before an agent reasons from scratch, **retrieve the closest prior solution**
   and have the model adapt it. As the library grows, more answers come from your
   own knowledge and fewer from cold model reasoning.

3. **Owned datasets from day one.** Log every agent input/output, and every
   approval decision (approve / edit / reject **plus the human's edits**), as a
   labelled dataset in open formats you control. The approval edits are human
   corrections — your single most valuable training and evaluation data.

4. **Evaluation sets.** Curate golden examples per agent and run them on every
   prompt or model change, so quality is **measured and owned** and regressions
   are caught the moment you swap a model.

5. **Deterministic where you can.** Move stable logic out of prompts into code —
   scoring rubrics, validation, Odoo config recipes, a reusable-module registry.
   Use the model for judgement, not for what code does reliably. Fewer calls,
   lower cost, less dependency.

6. **Compounding governance.** Every engagement enriches the knowledge base; a
   human periodically curates the solutions library and the decisions log so
   quality compounds instead of drifting.

7. **No lock-in.** Keep all knowledge in open, portable formats (your DB,
   markdown, JSON) — never trapped in any vendor, including the model provider.

**Acceptance:** changing the model in `api/llm.py` config swaps the provider with
zero other code changes and still passes the eval sets; a repeat-type requirement
retrieves and adapts a prior solution instead of starting cold; and every approval
decision is captured as labelled data you own.

---

## How to work

- For anything you can't do yourself (DNS, Odoo bot users, provider sign-ups,
  brand assets), give the user precise instructions and wait for confirmation.
- Ask the user for each value as the phase needs it: Anthropic key, per-tenant
  Odoo connection(s), email/WhatsApp provider creds, brand assets, billing
  provider. Never hardcode or commit them.
- Ship one phase at a time, fully tested, before starting the next. Do not skip
  the approval layer (Phase 2) before any client-facing send exists.

## Definition of done (whole product)

A new agency signs up, connects its own Odoo and channels, sets its brand and
autonomy policy, and runs its full lead-to-delivery lifecycle on the platform —
prospect → research → qualify → (approved) outreach → (approved) branded proposal
→ won → planned Odoo project → functional analysis → (approved) custom build &
deploy → ongoing client comms — with its client data isolated, its team approving
only money/reputation/production-code decisions from one cockpit, and **every
account accumulating knowledge that sharpens the next interaction**. C2P
Consultants runs its own agency on the same system as customer #0.
