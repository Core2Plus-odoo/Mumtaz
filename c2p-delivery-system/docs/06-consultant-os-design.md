# Consultant Operating System — design & handoff

Status: **approved design, not yet coded.** Extends the existing C2P Agency OS
into a multi-tenant, AI-native **consultant-first** platform. Each tenant is a
CONSULTANT / consulting firm (not a client company). Build is **additive** — new
modules + routers, no rewrites of existing endpoints.

---

## 1. What exists today (reuse, don't rebuild)

- **Backend:** FastAPI monolith `delivery_api/main.py` (~2.6k lines) + ~25 focused
  modules. uvicorn behind nginx, systemd on the VPS. Deploys to `main`.
- **Frontend:** one static file `console/c2p-delivery-console.html` (Bearer auth).
- **DB:** SQLite (WAL) via `store.py` — engagements, accounts, leads, approvals,
  communications, knowledge_entries, agent_runs, app_settings.
- **Tenancy (`tenancy.py`):** already multi-tenant (`MULTITENANT=1`): control DB
  (tenants/users, pbkdf2, HS256 JWT), per-tenant SQLite via a contextvar
  StoreProxy, Fernet-encrypted secrets, Stripe billing. Single-admin JWT mode too.
  → **tenant already = consultant firm.** ✅
- **Agents:** 20+ JSON-contract agents via `llm.run_json` (provider =
  anthropic / openai-compatible / none; self-heal retry; prompt cache). Every
  agent has a **deterministic local fallback**. Orchestration = Autopilot +
  PM-deliver loops (currently a **hardcoded** pipeline).
- **Knowledge stack (all local, embedded in prompts):** odoo_standard,
  odoo_knowledge, odoo_automation, agent_brain (self-correct), ba_knowledge,
  pm_knowledge (estimator + methodology), finance_knowledge (CA), sales_knowledge,
  tech_knowledge, vertical_playbooks (11 industries), industry.py + JSON.
- **Integrations:** Odoo XML-RPC (read schema; write lead/SO/project/task/config
  ops, gated), GitHub module push, SMTP/WhatsApp (dry-run), Stripe. **No queue /
  event bus — all synchronous.**

## 2. Gaps vs. target

1. Consultant **role / client-type / service** model + wizard (steps 2–5).
2. **Intelligence engine**: profile → workflows + agent set + templates.
3. **Dynamic agent activation** (today static).
4. **Workflow-as-data engine** (today hardcoded).
5. **Event bus** (none).
6. **Knowledge Hub v2**: semantic search, versioning, linking graph, Postgres option.
7. Non-Odoo role catalogs (bookkeeper / CA / management-consultant); finance_knowledge
   partially covers CA.

## 3. Target architecture (additive layer)

```
Console (wizard + views)
  │ REST
FastAPI ── routers/: onboarding · workflows · hub · events        (NEW)
  │
Intelligence Engine (NEW): profile → workflow defs + agent set + templates
  │
Agent Orchestrator (generalize autopilot): run workflow steps → agents
  │            agents = existing prompts/local generators; JSON only;
  │            NO direct DB writes; read Hub before, write learnings after
Event Bus (NEW): outbox table + in-process dispatcher (no broker dependency)
  │
Knowledge Hub v2 (NEW): entries + versions + links + embeddings (pgvector | local TF-IDF)
  │
Store (SQLite default / Postgres switch) · Odoo XML-RPC · GitHub · Policy gates
```

## 4. Role → Client → Service model

```json
consultant_profile {
  tenant_id,
  roles:        ["odoo_partner","bookkeeper","chartered_accountant","management_consultant"],
  client_types: ["trading","manufacturing","ecommerce_retail","services","finance","enterprise"],
  services:     ["erp_implementation", ...],
  templates:    { proposal, brd, sop, workflow },
  branding:     { ... }
}
```
- `SERVICE_CATALOG[role] -> services`
  - odoo_partner: erp_implementation, customization, integration, training
  - bookkeeper: bookkeeping, vat_filing, financial_reporting
  - chartered_accountant: compliance, audit_prep, advisory, financial_reporting
  - management_consultant: sop_design, bpr, strategy
- `SUGGEST[(role, client_type)] -> default services` (auto-fill wizard step 4).

## 5. Wizard (5 steps)

1. Identity — name, email, company, country.
2. Roles (multi-select).
3. Client types (multi-select).
4. Services — auto-suggested from role×client, editable.
5. Output config — workflow/proposal/BRD/SOP templates + branding.

Emits `wizard.completed` → builds `consultant_profile` → `consultant.profile.created`.

## 6. Workflow engine (workflow = data, not code)

```json
workflow { key, name, steps: [
  { key, name, agents:[...], documents:[...], gate:"none|approval",
    emits:"event", done_when:"stage|doc|approval" } ] }
```
- `workflow_engine.generate(profile, service)` composes steps from a **step
  library** (lead → qualification → proposal → BRD → delivery → QA → reporting;
  vat_filing gets a shorter compliance chain; sop_design a mapping→SOP chain).
- Runner = generalized `autopilot_step`: first incomplete step → run its agents →
  gate → emit event. The existing Odoo pipeline becomes the built-in
  `erp_implementation` workflow (backward compatible).

## 7. Agent activation matrix

`ACTIVATION[(role, client_type, service)] -> [agent_keys]`; orchestrator resolves
the union at run time. Map the 10 required agent types onto existing capability:

| Required agent | Backed by |
|---|---|
| ContextBuilderAgent | knowledge.context_block + Hub read |
| ProposalAgent | proposal (+ local_agents.build_proposal) |
| BRDAgent | ba + docwriter + doc_templates |
| SolutionArchitectureAgent | functional (Odoo architect) |
| EstimationEngineAgent | pm_knowledge.estimate |
| DeliveryBreakdownAgent | pm deliver loop |
| QA_UATAgent | director (QA) |
| ReportingAgent | pm build_status + docwriter |
| AccountingComplianceAgent | finance_knowledge + NEW prompts |
| ERPImplementationAgent | functional + config_ops |
| (NEW) ProcessMappingAgent, SOPGeneratorAgent, InventoryAgent, VATAgent | new prompts + existing knowledge |

Examples: Odoo×Trading → ERPImplementation, SolutionArchitecture, Inventory, VAT,
Estimation. Accountant×Finance → AccountingCompliance, Reporting, BRD.
Mgmt×Services → ProcessMapping, SOPGenerator, BRD.

**Agent contract (unchanged, enforced):** strict JSON in/out; never write DB
directly; operate via events; read Hub before, write learnings after.

## 8. Event-driven layer

Events: `wizard.completed`, `consultant.profile.created`, `workflow.generated`,
`agent.executed`, `proposal.generated`, `brd.generated`, `project.created`.
Impl: an **outbox table** + in-process dispatcher (no external broker → keeps the
self-hosted rule). Handlers reuse `sync.py` for Odoo sync (project/task/pipeline,
BRD → task conversion).

## 9. Knowledge Hub v2

Multi-tenant AI memory, not doc storage. Stores: consultant knowledge
(methodologies/SOPs/templates), client knowledge (history/patterns), project
knowledge (BRDs/proposals/delivery), estimation knowledge (planned vs actual,
pricing), agent knowledge (feedback loops). Requires: structured storage
(SQLite now / Postgres switch), semantic search (local TF-IDF now / pgvector
later), knowledge-linking graph (entry↔entry edges), versioning (append-only
versions + current pointer). Extends existing `knowledge.py`.

## 10. Folder structure (additive)

```
delivery_api/
  routers/       onboarding.py · workflows.py · hub.py · events.py
  consulting/    consultant_profile.py · service_catalog.py · activation.py
                 intelligence_engine.py · workflow_engine.py · step_library.py
  hub/           hub_store.py (entries+versions+links) · embeddings.py
  events/        bus.py (outbox + dispatcher) · handlers.py
  knowledge/     (existing knowledge modules — unchanged)
  main.py        (unchanged endpoints + include_router() only)
console/         wizard added as a view (or onboarding.html)
```

## 11. System rules (must hold)

Self-hosted (no SaaS/broker dependency added) · multi-tenant (existing tenancy) ·
preserve + **extend not replace** Mumtaz.digital · production-grade · strict JSON
contracts for all agents.

## 12. Suggested build order

1. consultant_profile + service_catalog + wizard (steps + `/onboarding` router).
2. intelligence_engine + workflow_engine + step_library (generate from profile).
3. activation matrix + generalize the orchestrator (autopilot → workflow runner).
4. event bus (outbox + dispatcher) + Odoo sync handlers.
5. Knowledge Hub v2 (versioning + links + local embeddings; Postgres switch later).
6. new role agents (ProcessMapping, SOPGenerator, AccountingCompliance prompts).

Each step: LLM path + local fallback + `llm.log_local`; compile + pyflakes +
console JS check + headless render; append to `docs/05-build-log.md`; commit to
`main`. See root `CLAUDE.md` for conventions & deploy workflow.
