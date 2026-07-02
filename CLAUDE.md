# Mumtaz repo — working knowledge

Two products live here:

- **`c2p-delivery-system/`** — the C2P Agency OS: an AI-run Odoo delivery agency
  (FastAPI backend + single-file console). This is where most work happens.
- **`addons/`** — Odoo custom addons for the Mumtaz marketplace (separate product).

Production: Hostinger VPS `187.77.128.199`, repo checked out at `/opt/mumtaz`,
console at `https://delivery.mumtaz.digital`. **Deploys go to `main`** — the VPS
pulls main; feature branches never reach production.

## Deploying

One command on the VPS (pull → relink console → restart API → health):

```bash
bash /opt/mumtaz/c2p-delivery-system/deploy/update.sh
```

Gotchas learned the hard way:
- nginx serves `web/index.html` which MUST be a **symlink** to
  `console/c2p-delivery-console.html` (update.sh enforces it). A plain copy goes
  stale silently — console changes then never appear.
- The service env file is **`delivery_api/.env`** (not the repo root). Reference:
  `delivery_api/.env.example` documents every knob.
- Browser caches the console hard — always hard-refresh after deploy.

## C2P Agency OS — system map

`delivery_api/main.py` (~2.5k lines) is the FastAPI app; everything else is a
focused module. The architecture is **LLM-first with a local fallback at every
stage**: each endpoint tries the model (via `llm.run_json`) and, when the
provider is unavailable or `C2P_LLM_PROVIDER=none`, falls back to deterministic
generators — so the whole pipeline completes with zero API.

Knowledge stack (deterministic, embedded into agent prompts via `prompts.py`):
- `odoo_standard.py` — per-app catalog of standard Odoo functionality (v17–19);
  `covered_by()` proves a standard path per requirement.
- `odoo_knowledge.py` — ~40 classification rules → verdict
  standard/configurable/studio/custom; `classify()` is the functional stage's
  local-first path.
- `odoo_automation.py` — native no-code toolkit (Automation Rules, Server/
  Scheduled Actions, templates, activities, approvals, sequences) + standard
  O2C/P2P/Make chains; `suggest()` builds trigger→action designs.
- `agent_brain.py` — post-analysis smart pass: self-corrects over-eager
  custom/studio verdicts (standard-first enforcement), decomposes compound
  requirements, reuses similar prior analyses.
- `finance_knowledge.py` — CA brain: GCC/PK tax regimes, IFRS treatments,
  finance-process→Odoo mappings; `advise()` enriches finance requirements.
- `pm_knowledge.py` — estimator (`estimate()`), 7-phase implementation
  methodology, risk register, governance; `build_project_plan()`,
  `build_status()`.
- `ba_knowledge.py` — per-area discovery framework (questions/data/pains/KPIs);
  `build_discovery()`.
- `local_agents.py` — local presales / requirements-catalog / proposal
  generators (schema-compatible with the LLM outputs).
- `doc_templates.py` — assembles BRD/FRS/Charter/SOW/TechDesign from structured
  data; `proposal_render.py` renders branded HTML/PDF (WeasyPrint optional,
  browser print fallback).
- `config_knowledge.py` (human config plan) + `config_ops.py` (executable,
  idempotent Odoo operations — `ensure` = create-if-missing) → applied to live
  Odoo by `_execute_config_apply`.

Execution & plumbing:
- `llm.py` — provider abstraction: `anthropic` | `openai`-compatible
  (Ollama/Groq/…) | `none`. Retry/backoff, prompt caching, per-task model
  routing, run logging (`log_local` records offline generations as successes).
- `odoo.py` — XML-RPC bridge (per-db client, `CONN_PROVIDER` reads the
  encrypted console connection first, env second).
- `github.py` — pushes generated modules to the addons repo (token encrypted,
  scrubbed from errors); `deploy.py` is the legacy staged/local-checkout path.
- `policy.py` — approval gates (`config_apply`, `code_deploy`,
  `proposal_send`, …). Live writes stay gated.
- `store.py` — SQLite (WAL + busy_timeout; engagements/leads/approvals/
  knowledge/agent_runs). `tenancy.py` — admin login (JWT) + optional
  multi-tenant mode. `knowledge.py` — per-account compounding knowledge.

Pipeline order (autopilot + PM delivery drive it): presales → BA discovery →
BA requirements → estimate → proposal → project → functional (per requirement)
→ developer (customs only) → documents → config → deploy. `m.STAGES` in
`models.py` is the canonical 5-stage list used for progress.

## Console (`console/c2p-delivery-console.html`)

ONE self-contained file (~2.4k lines): CSS design system in layered passes
(base → v2 polish → v3 alignment → v4 teal theme → v5 vibrant/segments — later
layers override earlier; append, don't restructure), then all views as
`render*()` functions dispatched by `renderView()`; nav built by
`navBtn/stageBtn/navSec` in business-flow order.

Conventions / pitfalls:
- Single global scope — **duplicate function names silently override** (an
  `openDoc` clash once broke the Documents preview; renamed to `openStageDoc`).
  Check: declared functions must be unique.
- Verify with `node -e 'new Function(js)'` syntax check + Playwright headless
  render (executablePath `/opt/pw-browsers/chromium-*/chrome-linux/chrome`,
  mock `window.fetch`, `--force-prefers-reduced-motion`) before committing.
- API base is `/api` (nginx proxies to uvicorn on 127.0.0.1:8800); auth token
  in localStorage `c2p_token` sent as Bearer.

## Working agreements

- Standard-first is the product's core discipline: standard config → native
  automation → Studio → custom-on-top (inherit, never recreate). Any new agent
  capability should respect and reinforce the ladder.
- Every new stage/feature gets: LLM path + local fallback + `llm.log_local`,
  compile check (`python3 -m py_compile`, `pyflakes`), console JS check +
  headless render, an entry in `docs/05-build-log.md`, then commit to `main`
  with a descriptive message and push (retry w/ backoff).
- Secrets never in git: `.env`, `*.db`, `web/` are gitignored; tokens/keys are
  encrypted at rest via `C2P_SECRET_KEY` (Fernet) and never echoed back.
- `docs/05-build-log.md` is the chronological build record; keep appending.
