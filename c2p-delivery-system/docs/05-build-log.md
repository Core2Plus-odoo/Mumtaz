# C2P Agency OS — Build Log

The repo is the source of truth. Each phase records what shipped and the
decisions taken, so the next phase builds on solid ground.

## Where it lives
Built **in place** on the deployed backbone at `c2p-delivery-system/delivery_api/`
inside the Mumtaz repo (the only path that reaches the production VPS via
`git pull`). The `api/` in the original `c2p-agency-os` zip is byte-identical to
this `delivery_api/`, so nothing was migrated — only extended.

Deploy after a backend change:
```bash
cd /opt/mumtaz/c2p-delivery-system && git pull origin main \
  && sudo cp console/c2p-delivery-console.html web/index.html \
  && sudo systemctl restart delivery-api
```

---

## Phase 1 — Top of funnel + client knowledge ✅

**Shipped**
- **Data model** (`models.py`): `Account` (1:1 with an Odoo partner, owns the
  knowledge base), `KnowledgeEntry`; `Engagement` now carries `account_id`.
- **Store** (`store.py`): `accounts`, `knowledge_entries`, `agent_runs` tables +
  an idempotent migration adding `engagements.account_id`. CRUD for accounts and
  knowledge; keyword `search_knowledge`; `log_run`/`list_runs`.
- **Knowledge service** (`knowledge.py`): `read_slice`, `write_entry`,
  `context_block` — agents load the account slice before acting and append
  learnings after.
- **Model-abstraction layer** (`llm.py`): the single place that calls a model.
  Provider + model are config (`C2P_LLM_PROVIDER`, `C2P_MODEL`, per-task
  `C2P_MODEL_<TASK>`). Every run is logged to `agent_runs` as owned data
  (inputs, outputs, model, tokens, latency, errors).
- **Agents**: `Prospector` (`POST /prospect`, web-search grounded) and
  `Researcher` (`POST /accounts/{id}/research`, writes a dossier into the
  knowledge base). Prompts in `prompts.py`.
- **Retrofit**: `presales` and `functional` now load the account knowledge slice
  before running and write a learning entry after.
- **Endpoints added**: `POST/GET /accounts`, `GET /accounts/{id}`,
  `GET/POST /accounts/{id}/knowledge`, `POST /prospect`,
  `POST /accounts/{id}/research`, `GET /runs`. Every existing endpoint unchanged.
- **Tests**: `delivery_api/tests/test_phase1.py` (mock the LLM — no key/network).

**Decisions**
- **Web search = Anthropic's native server-side tool** (`web_search_20250305`),
  gated by `C2P_WEB_SEARCH` (default on). No third-party provider/keys. If a
  model/account lacks the tool, set `C2P_WEB_SEARCH=0` and agents reason
  un-grounded.
- **Retrieval = SQLite keyword** now; `store.search_knowledge` is the seam to
  swap for vectors (pgvector) later without changing callers.
- **Owned data from day one**: `agent_runs` captures every call; approval-edit
  capture comes with the approval layer in Phase 2.

**Acceptance**
- ICP → ranked prospects (`/prospect`); research writes a dossier
  (`/accounts/{id}/research` → knowledge base); presales/functional output
  reflects stored knowledge via `context_block`. Verified by `test_phase1.py`
  (logic + endpoint wiring) and `py_compile` of all modules.

**Run the tests on the server**
```bash
cd /opt/mumtaz/c2p-delivery-system/delivery_api
/opt/mumtaz/c2p-delivery-system/delivery_api/.venv/bin/pip install -r requirements-dev.txt
/opt/mumtaz/c2p-delivery-system/delivery_api/.venv/bin/python -m pytest -q
```

### Add-on: System Administrator (Infrastructure Advisor) agent ✅
- New agent `sysadmin` (`prompts.py`) + `POST /infra/recommend` (`InfraIn`).
- Chooses the Odoo hosting/deployment topology — **Odoo Online / Odoo.sh /
  self-hosted VPS (e.g. Hostinger, Community or Enterprise) / on-prem** — and the
  edition, with rationale, alternatives-and-why-not, cost band, data-residency
  fit, ops burden, migration path, and revisit triggers.
- Loads the account knowledge slice when `account_id` is given and writes an
  `infra_recommendation` knowledge entry back.

### Add-on: Industry playbook library ✅
- `data/industry_playbooks.json` — 11 GCC-relevant industries (manufacturing,
  trading/distribution, retail/e-commerce, FMCG, food & beverage, construction/
  contracting, healthcare, professional services, automotive, logistics/3PL,
  real estate). Each: key processes, common pains, **required Odoo modules
  (core/recommended/optional)**, GCC localisation (VAT/ZATCA/WPS), KPIs, and
  common customizations. Open, portable JSON — owned deterministic knowledge.
- `industry.py`: `match_industry`, `playbook_block`, `list_industries`, `get`.
- Wired into **presales, proposal, project, functional** — each injects the
  matched industry playbook so proposals name the right modules and project
  plans are grounded. Industry resolves from the request, the presales profile,
  or the linked account.
- Endpoints: `GET /industries`, `GET /industries/{key}`. Tests added.

## Phase 2 — Outreach + the approval layer ✅

**Shipped**
- **Approval model + queue** (`models.Approval`, `store` approvals table): payload,
  requester agent, status, decided_by/at, reason, result. Endpoints
  `GET /approvals`, `GET /approvals/count`, `POST /approvals/{id}/decide`.
- **Autonomy policy** (`policy.py`): `action → level` map (auto | approval), with
  a per-tenant override in `app_settings('autonomy')`. `gate()` creates a pending
  Approval for any gated action and withholds it until a human decides. Client-
  facing/money/code actions are gated; internal reasoning runs auto.
- **Outreach (SDR) agent** (`outreach` prompt, `POST /accounts/{id}/outreach`):
  drafts a personalised email/WhatsApp/LinkedIn sequence (auto). **Sending the
  first touch is gated** — it creates a pending Approval.
- **Channel adapters** (`channels.py`): one `send()` for email (SMTP) + WhatsApp
  (Meta Cloud) + LinkedIn, **dry-run by default** (logs, nothing leaves) and
  live when provider creds are set in the env. On approve, the send runs and is
  logged to the account knowledge + Odoo chatter (`odoo.message_post`, best-effort).
- **Decision capture as owned data**: approve/edit/reject + the human's edited
  payload are stored on the Approval — the correction signal for future evals.
- **Cockpit UI**: new **Accounts** view (list/create, per-account Research /
  Outreach / Infra-advisor, knowledge browser) and **Approvals** queue
  (edit message, Approve & send / Reject + reason, pending badge in the nav).
- Tests added: policy gating, settings override, decide round-trip, channels
  dry-run, and an end-to-end outreach→approval→decide→send endpoint test.

**Decisions**
- Sends **dry-run by default** — no provider creds, nothing actually leaves;
  set `SMTP_*` / `WHATSAPP_*` in `.env` to go live, call sites unchanged.
- Gated actions today: `outreach_send` (others — `proposal_send`, `code_deploy`,
  etc. — are policy-listed and wire in as their phases land).

**Acceptance**: an outreach send creates an approval; approve → it "sends"
(dry-run) and is logged; reject → nothing sends; every decision is attributed
and audited. Verified by tests + headless cockpit render.

## Phase 3 — Branded proposals ✅

**Shipped**
- **`proposal_render.py`** — turns the proposal agent's JSON into a client-ready,
  in-brand document. `brand(store)` pulls the tenant's saved branding (white-label)
  over C2P defaults; `render_html()` builds a branded cover + sections (summary,
  scope, phases, effort table + total, commercial, timeline, assumptions, success
  criteria); `to_pdf()` uses WeasyPrint if available, else returns None (caller
  attaches HTML) so PDF is optional, never a hard dependency.
- **Preview** — `GET /engagements/{id}/proposal/preview` returns the branded HTML
  for in-browser preview / print-to-PDF.
- **Gated send** — `POST /engagements/{id}/proposal/send` creates a
  `proposal_send` approval. On approve, `_execute_proposal_send` renders the
  proposal, ensures the Odoo quotation (creates `sale.order` from the lead's
  partner if needed), **attaches the PDF/HTML to the quotation**, logs to chatter,
  optionally emails the client (gated channel), and writes a `deliverable`
  knowledge entry. `odoo.attach_bytes` added for binary attachments.
- **Console** — proposal output gains **Preview branded proposal** + **Issue
  proposal to client (needs approval)**; proposal approvals show a **Preview**
  button in the cockpit.
- Tests: branded render (in-brand, AED total) + gated send→approve→execute.

**Acceptance**: proposal renders in-brand (verified by headless render); send is
gated; an approved proposal attaches to the Odoo quotation + logs to chatter and
the account's knowledge.

## Phase 4 — Delivery in the loop ✅

**Shipped**
- **Live grounding** (already from Phase 1): the functional agent auto-reads the
  account's live installed modules via `odoo.py` (`_maybe_modules`) before
  analysing, alongside the industry playbook — so verdicts reflect the real
  tenant. (Schema is also available on demand via the Odoo Explorer endpoints.)
- **`deploy.py`** — writes a generated module to the account's addons repo.
  **Staged by default** (writes to a staging dir, nothing pushed); **live git
  add/commit/push** when `C2P_ADDONS_DIR` + `C2P_DEPLOY_LIVE=1` are set, so
  Odoo.sh builds it. Path-traversal-safe file writes.
- **Gated deploy** — `POST /engagements/{id}/deploy` creates a `code_deploy`
  approval. On approve, `_execute_deploy` writes/pushes the module, logs a
  `deliverable` knowledge entry and Odoo chatter note.
- **Console** — the developer output gains **Deploy to addons repo (needs
  approval)**; deploy approvals appear in the cockpit like any other.
- Tests: staged deploy + traversal guard; gated deploy→approve→execute.

**Decisions**
- Deploy is **staged by default** — no repo/creds means the module is written to
  a staging directory and reported; configure `C2P_ADDONS_DIR` (a checked-out
  addons repo with push rights) + `C2P_DEPLOY_LIVE=1` to push for real.

**Acceptance**: functional reflects live modules; a Custom requirement produces a
module (developer stage); deploying it requires approval; on approve it's written
to the addons repo (pushed when live).

## Phase 5 — Communications ✅

**Shipped**
- **`Communication` model + store** (inbound/outbound, channel, parties, status,
  sensitivity, approval link). `store.find_account_by_name` for routing.
- **Comms agent** (`comms` prompt): triages an inbound message — intent,
  sensitivity (approval for scope/money/commitment/legal; auto for routine),
  matched company for routing, and a drafted reply.
- **Inbound** — `POST /comms/inbound`: routes to the right account (by id or the
  agent's matched_company), logs the inbound, then **auto-sends routine replies**
  (dry-run channel) or **queues sensitive ones for approval**
  (`client_comms_sensitive`). Everything logged to the account knowledge.
- **Outbound on approve** — `_execute_action` handles `client_comms_sensitive`
  (send + log). `GET /comms` lists communications.
- **Console** — new **Communications** view: paste an inbound message → see the
  triage (intent, sensitivity, matched account, drafted reply) and whether it
  auto-sent or was queued; plus a recent-comms list.
- **Developer docs** — the developer agent now always ships a `README.md`
  (technical documentation) inside the generated module.
- Tests: routing + auto-vs-gated sensitivity + comms logging.

**Acceptance**: an inbound message routes to the correct account; outbound
touching scope/money is gated; all comms are logged on the account (and to Odoo
chatter on send). Verified by tests.

**Where functional/developer work + docs live**: the Functional and Developer
stage views (analysis, verdict, gap, options / module, files, install steps),
the per-stage **📄 Document** (branded Functional Specification / Technical Build
Note), the full **Generate Document** dossier, the **Agent Activity** log, and
the per-account **Knowledge** entries.

## Phase 6 — Supervisor + Agency Cockpit + metrics ✅

**Shipped**
- **Metrics** — `GET /metrics`: accounts, engagements, pipeline value (Σ proposal
  estimate_aed), by-stage counts, win rate (to-project / with-proposal), pending
  approvals, communications, agent runs.
- **Supervisor agent** (`supervisor` prompt) — `POST /supervisor/brief`: builds
  an agency snapshot (metrics + pending approvals + recent comms) and produces a
  "what needs you today" briefing (headline, prioritised actions, risks).
- **Agency Cockpit** (console) — agency-wide top-nav view: KPI cards, the daily
  briefing (generate on demand), pipeline-by-stage, and a pending-approvals panel
  linking to the queue.
- Tests: metrics computation + supervisor briefing.

**Acceptance**: the cockpit shows pipeline + approvals + KPIs across all
accounts; the Supervisor briefing generates from the live snapshot.

### Add-on: Leads CRM ✅
- `Lead` model + store (leads table) with source (prospector/inbound/manual),
  fit score, signals, status (new→contacted→qualified→converted/disqualified),
  account link, Odoo crm.lead id.
- Endpoints: `POST/GET /leads`, `GET /leads/{id}`, `POST /leads/{id}/update`
  (status/notes), `POST /leads/bulk` (save Prospector results), `POST
  /leads/{id}/convert` (→ Account), `POST /leads/{id}/sync` (→ Odoo crm.lead;
  db from body or `C2P_CRM_DB`).
- Console **Leads CRM** view: prospector runner (ICP → ranked prospects → Save
  all as leads), leads table with inline status, Convert-to-account, and
  push-to-Odoo. Tests: CRUD + bulk + convert.

## Phase 7 — Multi-tenant product (foundation) ✅ (additive, default OFF)

Decisions: **additive auth (default OFF)** so the live console is untouched;
**separate SQLite DB per tenant** (strong isolation) + shared control DB;
**full Stripe billing**.

**Shipped**
- **`tenancy.py`** control plane — `ControlStore` (tenants + users), stdlib
  **pbkdf2** password hashing, stdlib **HS256 JWT**, optional **Fernet** secret
  encryption (`C2P_SECRET_KEY`), per-tenant store registry (one SQLite file per
  tenant under `C2P_TENANT_DIR`), and a **`StoreProxy`** that routes every
  `store.*` call to the current tenant's DB (or the default when off).
- **Middleware** — when `MULTITENANT=1`, non-public routes require a JWT and are
  routed to the tenant's store; OFF = no-op (single store, nginx basic-auth).
- **Auth** — `POST /auth/signup` (creates tenant + owner + Stripe customer + JWT),
  `POST /auth/login`, `GET /auth/me`.
- **Per-tenant config** — `GET /tenant` (incl. usage), `PUT /tenant/config`
  (merge config + encrypt secrets: AI key, Odoo password, channel tokens).
- **Stripe billing** (`stripe_billing.py`) — customer + Checkout Session
  (subscription) + signed webhook → updates tenant edition/status.
- **Edition gating** — `delivery < growth < agency`; prospect/outreach/proposal
  send need Growth, comms/supervisor need Agency (enforced only when on).
- **Isolation** verified by tests: two tenants' data never crosses; proxy routing;
  password/JWT; signup→login→me end-to-end.

**Defaults & safety**
- `MULTITENANT` defaults **off** → zero change to the running console.
- Secrets only in env / encrypted per-tenant config; `control.db`, `tenants/`,
  `*.db` are git-ignored.

**To switch on (later)**: set `MULTITENANT=1`, `C2P_JWT_SECRET`, `C2P_SECRET_KEY`,
`STRIPE_SECRET_KEY` + `STRIPE_PRICE_DELIVERY/GROWTH/AGENCY` +
`STRIPE_WEBHOOK_SECRET` in `.env`, restart, and point the console at the login.

### Phase 7 — onboarding UI + per-tenant keys ✅
- **Login/Signup gate** (console): when `/health` reports `multitenant: true` and
  there's no token, a branded login/sign-up card gates the app; the JWT is stored
  and sent as `Authorization: Bearer` on every call; 401 → back to login. Off =
  no gate (single-tenant unchanged).
- **Per-tenant AI key**: middleware loads the tenant's decrypted secrets into a
  context; `llm._anthropic()` uses the tenant's own `anthropic_key` (cached per
  key) when present, else the env key — so each tenant bills/iso­lates their own
  model account.
- **Workspace panel** (Settings, multi-tenant only): set the tenant's Anthropic
  key + Odoo URL/user/password (secrets encrypted via `PUT /tenant/config`),
  shows the plan badge, and **Upgrade** buttons → Stripe Checkout.
- **Sidebar**: tenant name + edition + **Sign out**.

Remaining niceties (optional): per-tenant Odoo creds wired into `get_client`
(today the AI key is per-tenant; Odoo still uses env/shared unless extended),
and an onboarding wizard flow. The platform is otherwise complete and sellable.

All 7 phases now have a working spine; this is the platform layer that makes it
sellable.

### Add-on: Project Manager (owns the whole project) ✅
- **`pm` agent** + `POST /engagements/{id}/pm` — assembles the FULL scope (stages
  done, candidate requirements, functional verdicts, proposal value + phases,
  project plan, developer module, pending approvals for the engagement, open
  Odoo `project.task` count) and returns a management report: RAG, completion %,
  workstreams (status/owner), in-progress/blockers, next actions (with owner),
  and a client-ready status update.
- **Console Project Manager view** (top nav): the PM persona, "Assess project
  status" → the live report, a Scope panel (stage completion + Odoo link), and a
  Manage panel (Delegate, Configure Odoo, Generate dossier, Open approvals).

### Add-on: secure Odoo Connection panel ✅
- A console **Odoo Connection** view (Grounding) to set the instance URL, DB, bot
  user and **API key** — the key is **encrypted at rest** via `tenancy.enc_secret`
  (Fernet when `C2P_SECRET_KEY` is set, else base64) and **never returned** by the
  API (GET exposes only url/user/db + has_key + encrypted flag).
- `odoo.OdooClient` resolves creds through `odoo.CONN_PROVIDER` (set in main to
  read the encrypted store, falling back to env), so **every agent** uses the
  stored connection; `get_client.cache_clear()` on save.
- Endpoints: `GET/POST /odoo/connection`, `POST /odoo/connection/test`
  (authenticates + returns installed-module count). Encryption status badge in
  the UI nudges setting `C2P_SECRET_KEY`.

### Add-on: agents manage the Odoo implementation ✅
Decisions: **gated Odoo writes**; deploy to a **staging branch first**.
- **Config-Apply agent** (`config` prompt) — turns requirements + live installed
  modules + industry playbook into an Odoo **configuration recipe** (create/write
  ops on real models: tax/`l10n_ae`, products, CRM stages, analytic tags, …).
  `POST /engagements/{id}/config` runs it and creates a **`config_apply`**
  approval; on approve, `_execute_config_apply` applies it to the client's Odoo
  via the API (create/write only, per-op results, chatter + knowledge log).
- **PM dispatcher** (`dispatch` prompt) — `POST /engagements/{id}/dispatch`: the
  Delivery Lead allocates each requirement to config / functional / developer /
  manual, with autonomy + priority + sequence (full liberty over who does what).
- **Console** — Project output gains **PM: delegate the work** (shows the
  delegation) and **Configure Odoo from requirements (gated)**.
- **Live deploy to Odoo.sh staging**: set `C2P_ADDONS_DIR` + `C2P_DEPLOY_LIVE=1`
  + `C2P_DEPLOY_BRANCH=staging` in `.env`; approved modules push to the staging
  branch for a test build before production.
- Odoo connection: set `ODOO_URL` / `ODOO_USER` (bot email) / `ODOO_PASSWORD`
  (bot API key) / `C2P_CRM_DB` in `.env`, and link engagements to the DB, so
  functional reads live modules and writes hit the real Odoo. Test added for the
  gated config-apply path.

### Super agent: Autopilot orchestrator ✅
One super-agent that runs the whole engagement pipeline, chaining every
specialist and pausing only at approval gates, with a live run log.
- **Backend** (`main.py`): `_autopilot_decide(eng)` inspects stage state and
  returns the next step — presales → proposal → project → functional (one per
  outstanding candidate requirement) → developer (when any requirement is
  `custom`) → config (when the engagement has an Odoo DB) → deploy (when a
  module was built). `POST /engagements/{id}/autopilot/step` runs that single
  step and reports `status`: `running` (ran a specialist), `needs_input`
  (presales requires operator input), `blocked` (hit a `config_apply` /
  `code_deploy` approval gate, returns the approval), `done` (nothing left),
  or `error`. Stepwise so the orchestrator always stops cleanly at gates and
  the operator stays in control.
- **Console** (Overview hero): **🤖 Run Autopilot** button drives a loop that
  calls `/autopilot/step` until `done` / `needs_input` / `blocked` / `error`,
  refetching the engagement between steps and streaming each result into a
  colour-coded, monospace **Autopilot run log** (with a Stop control). Approval
  gates link straight to the Approvals view.
- Honours the same policy/gate layer as manual runs — Autopilot never bypasses
  an approval; it surfaces it and waits.

### Super agents II: Delivery Director QA + self-authoring documents + client Q&A ✅
Three layers that make the agency supervise itself, write its own deliverables,
and check in with the client.
- **Delivery Director (QA brain)** — a `director` agent scores every specialist's
  output (specificity / completeness / correctness / grounding / risk) against a
  house bar (`C2P_QA_BAR`, default 75). `_run_with_qa` runs a specialist, scores
  it, and if it misses the bar re-runs it ONCE (`C2P_QA_MAX_REVISIONS`) with the
  Director's critique injected via a `_qa_feedback` contextvar. Autopilot now
  reports each step's QA score and revision count in the live run log.
- **Self-healing developer** — generated modules pass `_validate_module_files`
  (manifest present, Python compiles, XML well-formed) before QA; build errors
  force a revision with the errors fed back to the developer agent.
- **Self-authored documents** — a `docwriter` agent produces real, branded client
  deliverables (BRD, FRS, Gap-Fit, Project Charter, Status Report, Technical
  Design, SOW) from the engagement's stage outputs; the Director QA-scores each.
  `proposal_render.render_document_html` renders them in-brand (with a tiny
  dependency-free Markdown→HTML converter). Console **Documents** view: author /
  re-author / open, with QA badges. Autopilot auto-authors BRD/FRS/Charter/Tech
  Design as their inputs become available.
- **Client Q&A loop (PM-compiled RFI)** — agents surface open questions; the
  `clarifier` (PM) consolidates them into one deduplicated, client-ready RFI
  (`POST …/clarifications/compile`). The PM/client records answers
  (`…/clarifications/answer`), which flow back into every later stage via
  `_client_answers_block` (and account knowledge), so agents work from confirmed
  answers, not assumptions. Console **Client Q&A** view with an open-items badge.

### Business Analyst — deep requirements gathering ✅
A dedicated BA agent does the elicitation; the PM stays the client-facing owner.
- **Discovery** (`ba_discovery` agent, `POST …/ba/discovery`) — plans a thorough,
  industry-aware discovery across every relevant business area: questions to ask,
  data to collect, stakeholders to interview, documents to request, integrations
  and NFRs to scope. Its client-facing questions are auto-pushed into the
  **Client Q&A** RFI (`_merge_questions_into_rfi`) so the PM can ask them.
- **Requirements catalog** (`ba` agent, `POST …/ba/requirements`) — synthesises
  discovery + client answers + documents + prior stages + playbook into a
  MoSCoW-prioritised functional requirements catalog with an Odoo-fit verdict on
  every line, plus NFRs, data objects, integrations, process maps (current→future),
  open questions, assumptions and risks. Written back to account knowledge.
- The catalog becomes the authoritative requirements baseline: injected into
  Proposal, Project and Functional (`_ba_requirements_block`) and into the
  document source. Autopilot now runs BA discovery + requirements right after
  presales, and Functional analysis works the BA's requirement list when present
  (falling back to presales candidates).
- **Console**: new **Business Analyst** view (catalog with fit/MoSCoW badges,
  integrations, data objects, process maps, discovery plan); reachable from the
  PM's Manage panel ("Gather requirements"). Autopilot log shows BA steps and how
  many questions were queued for the client.

### PM delivery orchestrator — the PM gets it done ✅
The Project Manager no longer just reports/recommends — it owns delivery end to end.
- **Organise** (`POST …/pm/deliver/plan`) — builds a sequenced delivery plan of
  work packages from the BA requirements catalog (or presales candidates); the
  dispatch agent annotates who-does-what/order. Stored in `stages.delivery_plan`.
- **Deliver** (`POST …/pm/deliver/step`, looped by the console) — runs Functional
  analysis on each requirement, then a Technical build for anything that comes back
  custom, with Director QA + self-heal on every step. Tracks per-package status
  (pending → done, with the functional verdict) and overall progress.
- **Console**: a "Deliver the requirements" panel in the Project Manager view with
  an Organise & deliver button, a live per-requirement board (assignment + verdict
  + QA), and a run log. Reachable alongside the BA ("Gather requirements") and the
  existing Delegate/Configure actions — so the PM is the single owner who gathers
  (BA), organises, and executes through Functional and Technical.

### Design system v2 — professional polish pass ✅
A cohesive global polish layer (appended, so it refines without restructuring views):
- **Depth & elevation**: a layered shadow scale (xs/md/lg), softer hairline borders,
  an ambient teal/violet gradient app background.
- **Motion**: tactile button lift + gradient accents, hover lifts on KPIs/cards/doc
  cards, smoother nav transitions — all disabled under prefers-reduced-motion.
- **Focus & a11y**: visible focus rings on every control.
- **Sidebar/topbar**: subtle gradient sidebar, translucent blurred sticky topbar,
  glowing active-nav accent.
- **Run logs**: redesigned as a dark terminal (cyan/green/amber rows) for the
  Autopilot and PM delivery feeds.
- **Detail**: KPI gradient top-accents + tabular numerals, progress-ring glow,
  refined chips/badges, custom scrollbars, elevated glass toasts.

### Resilience + GitHub repo connection ✅
- **Rate-limit resilience** (`llm.py`): every model call now retries transient
  provider errors (429 / 5xx / overloaded) with exponential backoff honouring
  Retry-After. New `C2P_MAX_OUTPUT_TOKENS` caps per-request output so a single
  call can't exceed a low per-minute tier (set it below your Anthropic OTPM
  limit; 0 = no cap). `C2P_LLM_RETRIES` tunes attempts.
- **GitHub addons repo** (`github.py` + panel): a secure, encrypted connection
  (repo URL, branch, optional subdir, PAT) used by the Developer agent. On an
  approved `code_deploy`, `_execute_deploy` clones the branch, writes the module,
  commits and pushes — Odoo.sh then builds it. The token is encrypted at rest,
  never returned, and scrubbed from every error message. New console **GitHub
  Repo** panel with Save/Test (lists remote branches). Falls back to the staged
  on-disk/env-git path when no GitHub connection is set.

### Proper admin login ✅
A branded single-admin login replaces the nginx Basic-Auth popup.
- **Backend**: `C2P_ADMIN_AUTH=1` turns it on (independent of MULTITENANT). The
  middleware requires a valid admin JWT on every API route except the public
  bootstrap set (`/health`, `/config`, `/auth/admin/login`). `verify_admin`
  checks the username + a pbkdf2 hash (`C2P_ADMIN_PASSWORD_HASH`) or a plaintext
  `C2P_ADMIN_PASSWORD`, constant-time. `/auth/admin/login` issues the JWT (needs
  `C2P_JWT_SECRET`); `/auth/admin/me` validates a session.
- **Console**: a branded full-screen Sign-in page (reuses the auth-gate), token
  stored and sent as a Bearer header, 401 → re-login, Sign-out in the sidebar.
- **Deploy**: `deploy/enable-admin-login.sh` sets the env (hashing the password,
  minting a JWT secret), strips the nginx Basic-Auth directives, and restarts.

### Built-in Odoo intelligence — local-first, less API-dependent ✅
The functional stage (the biggest call driver) now resolves routine requirements
from CURATED KNOWLEDGE with no API call.
- **`odoo_knowledge.py`**: a curated Odoo capability map (v17–v19) + ~30
  classification rules (CRM, Sales, Inventory, Purchase, Accounting/UAE VAT,
  multi-company, ZATCA, MRP, HR, Project, POS, eCommerce, loyalty incl. the
  tiered-loyalty=custom case, integrations=custom, approvals, reporting, …).
  `classify()` returns a full functional-stage object + a confidence.
- **Local-first wiring**: when confidence ≥ `C2P_LOCAL_CONFIDENCE` (0.8) the
  functional verdict/modules/options/risks come from knowledge — zero tokens.
  Ambiguous/novel requirements fall through to the model; and if the API is
  unavailable (no credits / rate-limited) it falls back to the built-in match so
  the agency keeps working. Toggle with `C2P_LOCAL_INTELLIGENCE`.
- On a real 30-requirement catalog ~70% classified locally — a matching cut in
  functional API calls (on top of cheap-model routing, QA toggle and prompt
  caching). The delivery log marks locally-resolved tasks "⚡ local · no API".

### Advanced built-in intelligence — Odoo + Chartered Accountant + PM ✅
Three professional knowledge brains, all local-first (no API for routine work):
- **Odoo** (`odoo_knowledge.py`, now 40 rules): added accounting-depth patterns —
  bank reconciliation, fixed assets/depreciation, analytic/cost-centres, budgets,
  multi-currency/FX, revenue recognition, withholding tax, landed costs,
  dropship, quality, and commission (correctly flagged custom).
- **Chartered Accountant** (`finance_knowledge.py`): GCC/Pakistan VAT regimes,
  an IFRS library (15/16/9, IAS 2/16/21/37, IFRS 10) and finance-process →
  Odoo mappings. `advise()` attaches the correct accounting treatment + Odoo
  modules + compliance notes to any finance requirement in the functional stage —
  no API. Rendered as an "Accounting treatment (Chartered Accountant)" panel.
- **Project Management** (`pm_knowledge.py`): a deterministic estimator — effort
  (man-days by Odoo-fit × area factor) + overhead workstreams → total md,
  duration, phased timeline, team, and an AED price band. New
  `POST /engagements/{id}/estimate` (0 tokens) and a PM-view "⚡ Estimate effort &
  price (instant)" panel; the estimate also grounds the proposal stage's pricing.

### Knowledge deployed into the agents ✅
The curated Odoo / Chartered-Accountant / PM knowledge is now embedded in the
agents' system prompts (not just the deterministic path), so every LLM agent
reasons from C2P house knowledge instead of generic training:
- `capability_digest()` / `digest()` produce compact references (~250/210/160
  tokens) from the same knowledge bases.
- `prompts.py` augments functional, ba, ba_discovery, developer, proposal,
  project, config, dispatch and presales with the relevant digests. Prompt
  caching makes this near-free after the first call. Toggle `C2P_EMBED_KNOWLEDGE`.

### Local document generation + durable persistence ✅
- **`doc_templates.py`**: assembles BRD / FRS / Charter / SOW / Tech-Design /
  Status documents from the structured engagement data (BA catalog, PM estimate,
  functional analyses incl. finance treatment) with NO API. `author_document`
  uses the docwriter agent when the API is available and falls back to the
  templater when it isn't — so a full Autopilot run completes end-to-end offline
  (templated prose, upgraded to LLM prose when credits exist).
- **Persistence hardening** (`store.py`): SQLite now runs in WAL mode with a
  30s busy timeout and synchronous=NORMAL, so the rapid concurrent writes from
  the autopilot/delivery loop WAIT instead of failing with "database is locked"
  (which previously could silently drop a save). The store also ensures its
  directory exists and logs the absolute DB path on startup so it can be located
  and backed up.

### Local Odoo configuration plan — full offline pipeline ✅
`config_knowledge.py` turns the classified requirements into an actionable Odoo
configuration PLAN (GCC baseline + per-area setup steps + module list) with no
API. `config_apply` falls back to it when the model is unavailable and persists
the recipe/plan to `stages.config`; Autopilot tracks config completion by the
stored stage (no approval loop). Local plans carry no auto-executable operations
— live Odoo writes stay a deliberate gated action. With this, a full Autopilot
run completes END-TO-END with zero API: classification, estimate, documents and
config all local; only novel prose/code needs credit. Console renders the plan
(baseline, by-area steps, gated ops) in the PM view.

### Documents: PDF by default, aligned, interactive ✅
- **PDF by default**: `/document/{key}/pdf` and `/proposal/pdf` return a real PDF
  via WeasyPrint when installed, else the branded HTML that auto-opens the print
  dialog (Save as PDF) — so a PDF is one click either way. Console doc cards lead
  with **⬇ PDF**.
- **Alignment**: numeric table columns auto right-align (tabular figures), zebra
  rows, word-wrap safety, heavier header rule, and a "Page x of y" running footer.
- **Interactive**: each authored document opens an inline **Preview & refine**
  drawer — an instructions box regenerates the document with the operator's
  direction (interact with the docwriter agent), plus a one-click PDF.

### UI revamp — bold branded, teal-forward (v4) ✅
A comprehensive theme layer (appended CSS, no view markup changed) gives the
console a distinctive, on-brand identity:
- Teal gradient top strip; frosted teal topbar.
- Soft teal-washed sidebar with a vivid gradient active-nav pill (white text).
- Gradient hero wash + glowing progress ring.
- Colourful stat tiles — accent KPIs are full teal-gradient (white text), others
  carry a teal top-accent bar.
- Teal-tinted panel headers, gradient buttons, bolder chips/callouts, gradient
  persona avatars. Verified across Overview and the Business Analyst view; all
  other views inherit it automatically.

### Deeper agent brains — BA discovery framework + PM implementation methodology ✅
- **Business Analyst** (`ba_knowledge.py`): a full Odoo discovery framework — for
  every business area (Sales/CRM, Purchase, Inventory, Manufacturing, Finance, HR,
  Projects, POS, eCommerce) the questions, data, pains and KPIs a senior BA asks,
  plus cross-cutting reporting/integration/migration/security scope and standard
  stakeholders. `build_discovery()` assembles an industry-aware plan with no API;
  the BA discovery stage is now local-first (LLM when available, framework
  fallback). Framework embedded in the BA agent prompts.
- **Project Manager** (`pm_knowledge.py`): the complete **Odoo ERP Implementation
  methodology** — 7 phases (Discovery→Hypercare) each with objectives, activities,
  deliverables and exit criteria; an 8-item risk register with mitigations; and
  governance/change-control. `build_project_plan()` generates the full project
  stage (phases, tasks, RAID, governance) locally; the project stage is now
  local-first. Methodology embedded in the project/proposal/pm agent prompts.
- **Documents**: the Project Charter/SOW now include Delivery Methodology,
  Governance and Risks (RAID) pulled from the methodology.
- **Functional & Technical execute into the system**: config-apply writes master
  data / tax / stages to live Odoo (gated); deploy pushes modules to the GitHub
  addons repo (Odoo.sh builds) — both already wired and gated.

### Consultants EXECUTE, not just instruct ✅
- **`config_ops.py`**: a deterministic engine that parses the requirements and
  emits real, SAFE, IDEMPOTENT Odoo operations on self-contained models —
  CRM stages, lead sources (utm.source), sales teams, product/contact categories.
  e.g. "stages: New Enquiry → Qualified → Quoted → Won → Lost" becomes 5
  `crm.stage` records; the source picklist becomes `utm.source` records.
- **Execution**: `_execute_config_apply` gained an idempotent `ensure` method
  (create only if not present — safe to re-run). `config_apply` now merges the
  local ops with any the config agent produced, persists them, and either applies
  immediately (`apply:true`) or routes through the approval gate. New console
  **⚡ Apply these to Odoo now** button (with confirm) shows per-op results
  (created / exists / failed). The functional/technical consultants now DO the
  configuration in live Odoo, not just describe it. Developer deploy already
  pushes modules to the GitHub addons repo. Live writes remain gated/confirmed.
