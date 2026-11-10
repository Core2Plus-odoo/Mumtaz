# Mumtaz Intelligence — Phase 1: repository discovery

Date: 2026-11-10. This is the deliverable the master instruction's Part 14
Phase 1 asks for, produced before any implementation, and it stops for review
as that part requires. Everything below was read from the repository in this
session, not recalled.

**The headline finding: this is not a greenfield build.** Roughly half of Part
4's architecture already exists in some form, and one component — the per-tenant
subscription and feature-entitlement engine — is more complete than the
instruction assumes. The risk in this workstream is not writing the agents. It
is rebuilding, in a new service, five subsystems that are already here.

---

## 1. AS-IS architecture

### 1.1 What the repository actually is

Three products share one repository.

| Area | What it is | Size |
| --- | --- | --- |
| `addons/` | 42 Odoo 19 modules — the Mumtaz platform and the jewellery product | 4.9 MB, 608 files |
| `c2p-delivery-system/` | A separate FastAPI product (C2P Agency OS) with its own AI stack | 1.5 MB, 76 files |
| `apps/`, `platform/` | Node services, including `zaki-ai` (Express + Anthropic SDK) | 2.0 MB |
| `website/jewel/` | The Mumtaz Jewel marketing site and the interface prototype | 2.6 MB |

Languages: **421 Python, 212 XML, 22 JavaScript, 41 HTML, 0 TypeScript.**

### 1.2 Odoo

- **Version 19**, confirmed from `Dockerfile` (`FROM odoo:19`) and
  `deploy/jewel-staging/docker-compose.yml` (`image: odoo:19`).
- **Community only.** `web_studio`, `whatsapp`, `documents`, `sign`,
  `approvals`, `iot` and `pos_iot` are Enterprise and are not available — this
  was verified against the Odoo 19.0 Community source, and it constrains the
  design (see `ARCHITECTURE_REVIEW.md`).
- PostgreSQL via `postgres:16-alpine`. Docker throughout; three compose files
  (root, `.staging`, `.production`) plus the jewel staging stack.

### 1.3 The jewellery product (built and tested)

| Module | Models |
| --- | --- |
| `mumtaz_jewellery` | `gold_rate`, `old_gold`, `product`, `stock_lot` |
| `mumtaz_jewellery_vip` | `partner`, `occasion`, `memo`, `offer`, `access_log` |
| `mumtaz_jewellery_owner` | `card` |
| `mumtaz_jewellery_demo` | synthetic seed, via the real approval path |

Six test files: `test_pricing`, `test_gold_rate_approval`, `test_old_gold`,
`test_piece`, `test_vip_rate_approval`, `test_nbo`. 73 tests run on a clean
database.

This is the ground the agents stand on, and it already enforces the two rules
the instruction cares most about: a price derives only from an approved rate,
and the rate needs two different people. Both are guarded in `create` and
`write`, so they hold against sudo and against any service calling the ORM.

### 1.4 Existing AI and platform code — the part that changes the plan

**Nothing in `addons/` is named "agent" or "orchestrator".** But five modules
already implement pieces of Part 4:

| Module | LOC | What it already does | Part 4 item |
| --- | --- | --- | --- |
| `mumtaz_ai` | 450 | Provider abstraction (`base`/`openai`/`anthropic` as abstract models), `mumtaz.ai.session` and `mumtaz.ai.message` with `token_usage`, `model_used`, `execution_status`, intent detection and routing | 3, 4, 15 |
| `mumtaz_api_gateway` | 338 | `mumtaz.api.key` (hashed, prefix, per-tenant, `rate_limit_per_minute`, expiry), `mumtaz.api.usage.log` (request_id, endpoint, status, duration, sizes), `mumtaz.async.job` (states, payload, job_type) | gateway, 9, 13 |
| `mumtaz_control_plane` | 1,934 | Plans, subscriptions, features, `tenant_feature`, **`feature_access_service.resolve_feature_access`** with quota, usage metrics, billing records, lifecycle and notification logs | 2, 11, 15 |
| `mumtaz_tenant_manager` | 899 | `mumtaz.tenant`, module bundles, tenant provisioning | tenant isolation |
| `mumtaz_voice` | 662 | Voice sessions and messages over `mumtaz_ai`, for finance queries | Part 10 §3 voice |

**`mumtaz_control_plane` is the single most valuable find.** The per-agent
subscription model proposed on `website/jewel/intelligence/` does not need a
new billing system — it needs each agent registered as a `feature`, and
`resolve_feature_access(tenant, feature)` already answers "is this tenant
entitled, and what is the quota".

### 1.5 The second AI stack — `c2p-delivery-system/delivery_api`

A different product, but it is a **working prototype of Parts 4, 6, 9 and 12**:

- `llm.py` — provider abstraction (`anthropic` | OpenAI-compatible incl.
  Ollama/Groq/OpenRouter | `none`), retry with backoff, prompt caching,
  **per-task model routing** (`model_for(task)`), run logging, and a local
  fallback at every stage so the pipeline completes with no provider at all.
- `policy.py` — the autonomy seam. `AUTONOMY` maps action → `auto` or
  `approval`; `gate()` creates a pending approval and withholds the action.
  Per-tenant override lives in settings, so policy changes without code.
- `tenancy.py` — JWT, Fernet encryption at rest for secrets, multi-tenant
  `ControlStore`.
- `store.py` — tables including `approvals`, `agent_runs`, `knowledge_entries`.
- A five-stage pipeline (`STAGES`) with an `agent_brain.py` self-correction pass.

**Its limits, stated plainly:** it is SQLite, not PostgreSQL. Its autonomy model
has two levels, not five. Its orchestration is a fixed pipeline, not a
delegating orchestrator — there is no "pick the right specialist and consolidate".
It belongs to another product and must not simply be imported.

### 1.6 Authentication and permissions

Two unrelated schemes: Odoo's own users, groups, ACLs and record rules
(`ir.model.access.csv`, `ir.rule`) across `addons/`; and JWT + API keys in the
FastAPI and gateway layers. Any agent service must authenticate into Odoo as a
**real Odoo user** so record rules apply, rather than holding a superuser
connection — this is what makes "an agent runs as you" true rather than
aspirational.

---

## 2. Gap analysis

Against the instruction, component by component.

| Part 4 component | Status | Where |
| --- | --- | --- |
| Agent orchestration | **Gap** | Pipeline exists in c2p; delegating orchestrator does not |
| Agent configuration | **Gap** | — |
| System prompt management | **Partial** | Prompts exist in `prompts.py`; no versioning, no tenant layer |
| Model routing | **Built, wrong place** | `llm.model_for(task)` and `mumtaz_ai/providers/` |
| Tool registry | **Gap** | No registry, no permission-checked tool layer |
| Business context retrieval | **Partial** | `odoo.py` XML-RPC bridge; `knowledge.py` |
| Knowledge base | **Partial** | `knowledge_entries`, no chunking, no embeddings, no retrieval log |
| Memory management | **Gap** | — |
| Task management | **Partial** | `mumtaz.async.job` has states and payloads; no dependencies |
| Inter-agent communication | **Gap** | No message contract, no schema validation |
| Approval management | **Partial** | `policy.gate()` and `approvals`; 2 levels not 5 |
| Execution control | **Gap** | No idempotency, no circuit breaker, no timeout |
| Audit logging | **Partial** | `api.usage.log`, `agent_runs`, VIP `access_log` |
| Agent evaluation | **Gap** | — |
| Usage and cost tracking | **Partial** | `token_usage` and `model_used` per message; `usage_metric` per tenant |

Against the five agents: **all five are specified, none implemented.** Zayan
exists only as a public-website conversational agent (ElevenLabs,
`agent_6701m73daeyhessvnqrt4szvbtzh`), which holds no business data and has no
tools — it is a product guide, not the orchestrator.

Against Part 7's 37 tables: **none exist.** The nearest equivalents are the
seven models in §1.4 and eight SQLite tables in c2p.

### 2.1 Where the instruction conflicts with the repository

These need a decision; I have not resolved any of them.

| # | Instruction says | Repository says | Note |
| --- | --- | --- | --- |
| 1 | Frontend: "prefer Next.js/TypeScript **if not established**" | **It is established, and it is not Next.js.** 0 TypeScript files; Odoo QWeb XML and plain HTML | Adding Next.js contradicts Part 16 rule 3, "do not introduce unnecessary frameworks". Recommend OWL inside Odoo for internal screens |
| 2 | Database: PostgreSQL | Odoo is PostgreSQL; the c2p AI stack is **SQLite** | New AI services should be PostgreSQL. Do not migrate c2p as part of this |
| 3 | Additional languages: **Arabic and Urdu** | All jewel work to date assumes Arabic and English | Urdu is new. It changes voice, fonts and RTL testing. Confirm it is wanted for Jewel |
| 4 | Theme: emerald, charcoal, **champagne gold** | The site is indigo, after an explicit instruction to remove the gold | Two palettes now live side by side. One must give way |
| 5 | Five agents: Zayan, Amara, Noor, Rayan, Layla | `IMPLEMENTATION_ROADMAP.md` Slice 5 names Memory, Stylist, Relationship, Owner analyst | **Two rosters doing overlapping work.** Layla ≈ Stylist + Relationship; Rayan ≈ the pricing engine, which is deterministic code and should stay so |
| 6 | "Never allow AI agents to write directly to Odoo's PostgreSQL" | Agreed, and already true — `odoo.py` uses XML-RPC | No change needed; worth keeping as a review gate |
| 7 | Autonomy A–E | `policy.py` has two levels | Extend, do not replace. `docs/mumtaz-jewel/CLAUDE.md` already mandates A–E |

### 2.2 One technical caution on Rayan

The instruction gives Rayan "calculate purity-adjusted metal values",
"calculate proposed selling prices" and "decimal-safe arithmetic".

**A model must not do this arithmetic.** The pricing engine already exists as a
pure library with 19 unit tests and no Odoo imports. Rayan's correct job is to
*call* it, interpret the result, compare scenarios and recommend — never to
compute. This matches the instruction's own restriction ("every calculation must
preserve its input rate, currency, unit, purity, timestamp, rule version and
calculation breakdown"), which a deterministic function can guarantee and a
model cannot. Flagging it because the responsibility list reads as if Rayan
does the maths.

---

## 3. Proposed TO-BE architecture

Keeping the instruction's shape, placed against what exists.

```
Browser (OWL inside Odoo for internal; static for public)
        │
   mumtaz_api_gateway        ← EXISTS: api key, rate limit, usage log, async job
        │
   Mumtaz Intelligence service (new, FastAPI, PostgreSQL)
        │
   Zayan — orchestration engine (new)
        ├── Amara, Noor, Rayan, Layla (new)
        ├── Business context service  → Odoo XML-RPC, as the invoking user
        ├── Knowledge retrieval       (extend)
        ├── Tool execution service    (new, permission-checked)
        ├── Approval engine           ← EXTEND policy.gate() to A–E
        └── Audit + observability     ← EXTEND api.usage.log + agent_runs
        │
   Odoo 19 Community — system of record
        └── mumtaz_control_plane      ← EXISTS: entitlement per agent per tenant
```

Three structural decisions, for approval:

1. **One new service, not five.** The agents are configuration and prompts
   inside one orchestrator service, not five deployables. Five containers for
   five prompts is operational cost with no isolation benefit while they share
   one tool layer.
2. **Entitlement reuses the control plane.** Each agent becomes a `feature`;
   `resolve_feature_access` decides whether a tenant may invoke it, and
   `usage_metric` meters it. This is what makes the per-agent subscription real
   rather than a page.
3. **Odoo access as the invoking user.** The service holds no superuser
   connection. Record rules — including the Private/Royal restriction — then
   apply to agents for free, which is the only way "an agent cannot see a client
   you cannot" is enforceable rather than promised.

---

## 4. Reuse versus new development

| Capability | Decision | Basis |
| --- | --- | --- |
| API gateway, keys, rate limits, usage log | **Reuse** | `mumtaz_api_gateway`, complete enough |
| Tenant model, provisioning, bundles | **Reuse** | `mumtaz_tenant_manager` |
| Per-agent entitlement, quota, metering, billing | **Reuse** | `mumtaz_control_plane`, 1,934 LOC |
| Async job states | **Reuse and extend** | `mumtaz.async.job` + dependencies |
| Provider abstraction, model routing | **Port** | Pattern from `llm.py`; do not import across products |
| Autonomy gate | **Port and extend** | `policy.gate()`, 2 levels → 5 |
| Secret encryption at rest | **Port** | `tenancy.py` Fernet |
| Prompt storage | **New** | Versioning and a shared policy layer do not exist |
| Tool registry and permission checks | **New** | Nothing equivalent |
| Inter-agent message contract | **New** | Nothing equivalent |
| Memory, evaluation, guardrail events | **New** | Nothing equivalent |
| Pricing arithmetic | **Reuse, never regenerate** | Pure library, 19 tests |
| Gold rate approval | **Reuse, never bypass** | Guarded in the ORM |
| Voice | **Reuse the pattern** | `mumtaz_voice` already does sessions over `mumtaz_ai` |

**Roughly 40% of Part 4 is reuse or port. The genuinely new work is the tool
registry, the message contract, memory, evaluation and the orchestrator itself.**

---

## 5–7. Database, API and security

Not produced here, deliberately. Part 7 asks for complete migrations for 37
tables, Part 8 for fifteen-section prompts for five agents, Part 9 for a tool
registry — all of which depend on decisions 2.1 #1–#5 and §3's three structural
choices. Producing 37 migrations against an unsettled agent roster and an
unsettled frontend would be work thrown away.

What is settled and can be stated now:

- Every new table carries `tenant_id` and `company_id` from creation, with a
  company rule. `jewellery.owner.card` was written without `company_id` and is
  an open finding precisely because retrofitting is painful.
- UUID primary keys for AI tables; Odoo integer IDs stay in Odoo.
- Audit tables append-only at the application layer, with a periodic digest so
  tampering is detectable.
- Secrets via environment and Fernet at rest, never in a prompt — already the
  practice in `tenancy.py` and `github.py`.
- Retrieved documents, uploads and web content are untrusted input. They inform
  an answer; they never change a permission. This needs a test, not a sentence.

---

## 8. Implementation backlog

Dependency-ordered. Each item is a reviewable increment, per Part 16 rule 11.

| # | Item | Depends on | Acceptance |
| --- | --- | --- | --- |
| 0 | **Settle 2.1 #1–#5** | owner | Written decisions |
| 1 | Agent registry, configuration, versioned prompts, shared policy layer | 0 | A prompt change is a new version; tenant override cannot remove a platform restriction — tested |
| 2 | Model routing and provider abstraction, PostgreSQL | 1 | Provider swap by configuration; no provider lock-in — tested |
| 3 | Autonomy A–E on `policy.gate()` | 1 | Each level enforced per tenant/agent/tool/threshold — tested at every level |
| 4 | Tool registry with permission checks, tenant context, audit, idempotency | 1,3 | A tool invoked without permission fails closed and is logged |
| 5 | Business context service over XML-RPC **as the invoking user** | 4 | An agent acting for a non-VIP user cannot read a Private client — tested |
| 6 | Audit, guardrail events, token and cost tracking | 4 | Every consequential action reconstructable from the log |
| 7 | Zayan: classification, selection, delegation, consolidation, escalation | 1–6 | Workflow A end-to-end, approval enforced |
| 8 | Rayan — calls the pricing engine, never computes | 7 | Cannot publish a price without approval — tested |
| 9 | Amara, Noor | 7 | Cannot post an entry; distinguishes verified from estimated |
| 10 | Layla | 7,9 | Cannot send; Private/Royal blocked — tested |
| 11 | Agent entitlement as control-plane features | 7 | Unsubscribed agent is not invokable; usage metered |
| 12 | Command Centre screens | 7–11 | Per Part 10 |
| 13 | Evaluation and feedback | 12 | Feedback cannot alter permissions — tested |

Part 13's eighteen test areas attach to the items above rather than forming a
phase; the two that most need writing early are **tenant isolation** and
**prompt injection resistance**, because both get harder to add later.

---

## 9. Deployment impact

- One new service and one new PostgreSQL database per environment. The gateway
  fronts it; nothing is exposed directly.
- No change to the Odoo container or its database beyond new module installs.
- `mumtaz_control_plane` gains feature rows per agent — data, not schema.
- Outbound network to model providers must be allowlisted; today the sandbox
  blocks `unpkg.com`, which is a reminder that egress is restricted by default.
- **Production is not touched by this workstream.** `docs/mumtaz-jewel/CLAUDE.md`
  requires a named human approval in chat before any deploy, restart or config
  change, and `main` auto-deploys to the VPS.
- Rollback: the agents are additive. Disable the feature flags and the business
  keeps running, which is the test of whether §3's separation is real.

---

## Missing configuration — Part 1 asks that these not be assumed

1. **AI provider and credentials.** `mumtaz_ai` supports OpenAI and Anthropic
   and both are unconfigured. Which provider, whose account, and is there a
   budget per tenant?
2. **Urdu.** Confirm it is in scope for Jewel, or only for the wider platform.
3. **Agent roster.** Which of the two casts survives (2.1 #5).
4. **Palette.** Emerald/charcoal/champagne gold, or the current indigo (2.1 #4).
5. **Frontend.** OWL inside Odoo, or a separate application (2.1 #1).
6. **Character artwork.** Five portraits were generated in this session and
   committed to `website/jewel/site/img/agents/`. Confirm these are the assets,
   or supply the intended ones.
7. **Deployment environment** for the first agent service: development,
   staging, or the jewel staging host.
8. **Who approves what.** Part 6 makes autonomy configurable by role and
   financial threshold. Those thresholds are a finance decision, not a
   development one, and the same rule applies as to VAT and AML values: they are
   configuration for a named person to confirm, never invented here.

---

## Recommendation

Settle the eight questions above and the five conflicts in 2.1, then start at
backlog item 1. Do not start at Part 7 — writing 37 migrations before the agent
roster is settled would be the single most expensive mistake available here.

Per Part 14, this stops for review. No implementation has begun.
