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

**Next:** Phase 5 — communications (inbound triage to the right account/agent;
outbound replies gated by sensitivity; all comms logged to chatter + knowledge).
