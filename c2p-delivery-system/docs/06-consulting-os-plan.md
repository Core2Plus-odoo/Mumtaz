# Consulting OS — approved plan (next build)

Status: **designed, awaiting/starting implementation**. Analysis + design were
approved in chat (Jul 2026). Extend, never replace, the existing Agency OS.

## Goal
Generalise the C2P Agency OS into a multi-tenant CONSULTANT-FIRST platform:
each tenant is a consultant/firm who selects **roles** (Odoo partner,
bookkeeper, chartered accountant, management consultant) × **client types**
(trading, manufacturing, ecommerce/retail, services, finance, enterprise) ×
**services** — and the system generates their workflows, agents and templates.

## Phase-1 analysis (key facts)
- Tenancy already fits: `tenancy.py` MULTITENANT=1 → tenant = consultant firm
  (control DB, JWT, per-tenant SQLite, Fernet secrets, Stripe).
- Agents already JSON-strict with local fallbacks; orchestration (autopilot /
  pm-deliver) is HARDCODED, not config-driven.
- No event bus (all synchronous). No vector search / versioning / graph in
  knowledge. No role/client-type/service model or onboarding wizard (only
  signup). Odoo/GitHub integrations solid. main.py is a 2.6k-line monolith —
  new features go in routers, not main.py.

## Approved design (short)
1. **consultant_profile**: `{roles[], client_types[], services[], templates,
   branding}` per tenant. `SERVICE_CATALOG[role]` + `SUGGEST[(role,client)]`.
2. **Wizard** (5 steps): identity → roles (multi) → client types (multi) →
   services (auto-suggested, editable) → output config (templates/branding).
   Emits `wizard.completed`.
3. **Intelligence engine**: profile → workflow definitions + agent set +
   document templates.
4. **Workflow engine**: workflows as DATA
   `{key, steps:[{key, agents[], documents[], gate, emits, done_when}]}`;
   generator composes from a step library (lead→qualification→proposal→BRD→
   delivery→QA→reporting; shorter chains for compliance services). Runner =
   generalised autopilot_step. Existing Odoo pipeline = built-in
   `erp_implementation` workflow (backward compatible).
5. **Agent activation matrix**: `ACTIVATION[(role, client_type, service)] →
   [agent_keys]`, resolved as a union at runtime. Map requested agents to
   existing ones: BRD≈ba+docwriter, Proposal≈proposal, Estimation≈pm_knowledge,
   QA_UAT≈director, ERPImplementation≈functional+config, Reporting≈pm status,
   DeliveryBreakdown≈pm deliver, ContextBuilder≈knowledge.context_block,
   AccountingCompliance≈finance_knowledge(+new prompts), NEW: ProcessMapping,
   SOPGenerator (management-consultant role).
6. **Event bus**: SQLite/PG outbox table + in-process dispatcher (no broker —
   self-hosted rule). Events: wizard.completed, consultant.profile.created,
   workflow.generated, agent.executed, proposal.generated, brd.generated,
   project.created → handlers reuse sync.py for Odoo.
7. **Knowledge Hub v2**: entries + versions + links + embeddings
   (pgvector when Postgres configured, local TF-IDF fallback). Adds estimation
   knowledge (planned vs actual) and agent-performance feedback.
8. **Folder structure** (additive):
   `delivery_api/routers/{onboarding,workflows,hub,events}.py`,
   `delivery_api/consulting/{consultant_profile,service_catalog,activation,
   intelligence_engine,workflow_engine,step_library}.py`,
   `delivery_api/hub/{hub_store,embeddings}.py`,
   `delivery_api/events/{bus,handlers}.py`. main.py gains only
   include_router lines.

## Rules
Self-hosted (no new SaaS/broker), multi-tenant, extend-not-replace,
production-grade, strict JSON agent contracts, agents never write DB directly
(orchestrator/events do), hub read-before / write-after each agent run.

## Build order
profile + catalog + wizard → intelligence/workflow engine → activation matrix
→ event bus → hub v2 → new role prompts (bookkeeper/CA/management consultant).
