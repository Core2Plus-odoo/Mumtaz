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

**Next:** Phase 2 — outreach + the approval layer (no client-facing send exists
until the approval gate does).
