# Mumtaz AI architecture (ZAKI)

Evaluated 21 Nov 2026 against `main` at `2c2939a`. Read-only: nothing was installed, started or fetched, and no Odoo test was executed for this document.

## 1. Conclusion

ZAKI should run **inside each tenant's Odoo**: the `mumtaz_zaki` addon on top of one shared, governed AI core lifted from `mumtaz_jewellery_ai`, with `zaki.mumtaz.digital` as a thin client of the same endpoints. Odoo already holds the data and is the identity authority, so every tool can run as the signed-in user through the ORM and the server enforces access rights, record rules and company scope. No service account or administrator credential is needed.

No current implementation is safe to expose as it stands. The three `zaki.mumtaz.digital` codebases either depend on a backend that was deleted from the repository (`zaki-server`) or use one shared Odoo administrator for every tenant with no authentication. Inside Odoo, the only code with real governance (policy levels, grounding, a run log, approvals, tests) is the Jawhar AI module; the best read-only finance data layer is split between `mumtaz_voice` and `mumtaz_financial_reports`; and `mumtaz_zaki` itself reports cash as zero and sums every company in the database.

## 2. Status legend

| Tag | Meaning |
|---|---|
| **VERIFIED** | Read in code at the cited path. Not executed unless stated. |
| **REPORTED** | From a repository document or the earlier audit; not re-checked here. |
| **PROPOSED** | Design. Not built. |
| **UNKNOWN** | Needs evidence from the server. |

Paths are relative to the repository root. No secret values appear in this document.

Related documents (not repeated here):

- `docs/infrastructure-audit/04_SECURITY_AUDIT.md` — findings APP-01, APP-02 (unauthenticated `platform/zaki` backend), APP-05, APP-08, ODOO-04 (finance snapshot).
- `docs/jawhar/AI_AGENT_ARCHITECTURE.md` — the governed agent design that the shared core is taken from.
- `docs/erp/project/DECISION_REGISTER.md` — D-03 (one AI provider layer) and D-10 (canonical ZAKI application). Section 8 below is the input for both.

## 3. Current state

### 3.1 Comparison

Every row is VERIFIED in code unless a cell says otherwise. Whether any of the three standalone applications is deployed is UNKNOWN.

| Implementation | Real Odoo data? | Whose credentials | Auth / isolation | LLM | Guardrails / audit / metering | Dead dependencies | Tests / CI | Last real change |
|---|---|---|---|---|---|---|---|---|
| Static page `sites/zaki.mumtaz.digital/static` | No (browser storage, demo data) | User's own model key, held in the browser | None | Direct call from the browser | None | `zaki-server` | 0 / none | 2026-05-15 |
| Node app `sites/zaki.mumtaz.digital/node-app` | Yes (JSON-RPC reads) | End user's own Odoo session | Bearer token checked by the deleted service; SSRF | Tool use; model reported as retiring 2026-11-30 (REPORTED) | Read-only tools; no audit | `zaki-server` | 0 / `npm audit` only | 2026-06-13 (code) |
| FastAPI `platform/zaki` | Yes (one snapshot call) | One shared Odoo admin for all tenants | None; tenant chosen by an integer | Plain prompt | None; knowledge-base injection path | Control panel that is not in the repo | 0 / none | 2026-06-13 |
| `addons/mumtaz_zaki` | Yes (ORM); cash always 0 | User, then `sudo()` | Accounting group; cross-company under `sudo()` | None | n/a | None | 2 / platform CI | 2026-11-21 |
| `addons/mumtaz_ai` | Cash only | User | Company and own-record rules | Providers unreachable from its own flow | Log of prompt and response | None | 0 | 2026-04-04 |
| `addons/mumtaz_voice` | Yes (ORM, company-scoped) | User | Company and own-record rules; TTS open to portal users | Through `mumtaz_ai` providers, plain prompt | Prompt-only; quota never fed | None | 0 | 2026-06-14 |
| `addons/mumtaz_cfo_*` | CSV shadow ledger | User | Company rules; manager implies system admin | None | Review queue | None | 0 | 2026-07-06 |
| `addons/mumtaz_financial_reports` | Yes (ledger, by account type) | User, no `sudo()` | Accounting access rights, company | None | n/a | None | 0 | 2026-07-07 |
| `addons/mumtaz_ceo_dashboard` | Sample data unless media-buying answers | User | — | None | n/a | None | 0 | 2026-07-06 |
| `addons/mumtaz_core` (AI settings) | Settings only | — | Keys in plain columns, system group | Key store, connection test | Editable log; limits not enforced | Control panel that is not in the repo | 0 | 2026-11-21 |
| `addons/mumtaz_jewellery_ai` | Yes (tools as user) | User | Record rules; restricted client tiers excluded | Key from the environment only | Levels, grounding, run log, approvals, pause; no quota | None | 23 / Jawhar CI | 2026-11-21 |
| `c2p-delivery-system/delivery_api/llm.py` | n/a | n/a | n/a | Multi-provider, per-task routing | Run log, token cap | None | Not assessed | 2026-07-01 |

**Revenue is defined four different ways** (VERIFIED): tax-inclusive invoice totals (`addons/mumtaz_zaki/models/zaki_connector.py:24-30`; node `server.js:284`), untaxed invoices (`agents/farid.js:268`), account-code prefixes (`agents/farid.js:278`), and income account-type balances (`addons/mumtaz_voice/services/cfo_service.py:98-103`; `addons/mumtaz_financial_reports/controllers/reports.py:25-29`). The same company would show a different revenue figure on each surface.

### 3.2 Static page — `sites/zaki.mumtaz.digital/static/index.html`

| Point | Finding | Status |
|---|---|---|
| What it is | Browser-only single page with about 26 panels (briefing, ledger, P&L, budgets, cash-flow forecast, feasibility, scenarios, IFRS, tax and others) | VERIFIED |
| Where figures come from | `localStorage` key `zaki_v3` (`:2900-2903`): manual entry, CSV import (`:4290`) or hard-coded demo data (`:3865-3890`). Nothing comes from Odoo unless `zaki-server` exists (`syncFromOdoo` → `POST /api/v1/zaki/sync-odoo`, `:4006`) | VERIFIED |
| Fixed content | IFRS, tax and investment content is hard-coded (`:2074`, `:2359`) | VERIFIED |
| Auth and tenancy | None. "Login" is a token from `zaki-server` kept in `localStorage` (`:3964-3975`) | VERIFIED |
| LLM | The browser calls the model provider directly with the user's own key from `localStorage`, plain prompt, 2,048 output tokens (`:3232-3245`). A voice provider is also called from the browser (`:3291`). No guardrails, audit or metering | VERIFIED |
| Server chat path | `streamZaki` (`:4073`) builds the system prompt into `msgs` (`:4077`) but sends only the last message (`:4085`), so the CFO context is dropped | VERIFIED |
| Dead dependencies | `/api/v1/auth/login`, `/api/v1/zaki/sync-odoo`, `/api/v1/ai/chat/stream` belong to `zaki-server`, deleted in `48a2cf9` (PR #124, 2026-07-06) | VERIFIED |
| Code health | 7,143 lines, 413 KB. `runScenario` is declared twice (`:6431`, `:6821`); the later one silently wins. 154 `innerHTML` uses | VERIFIED |
| XSS | Finding APP-08 | REPORTED |
| Tests / CI | None | VERIFIED |
| Overlap | Differs from `node-app/public/index.html` by 44 diff lines (fonts, a token check) | VERIFIED |

### 3.3 Node app — `sites/zaki.mumtaz.digital/node-app/`

| Point | Finding | Status |
|---|---|---|
| What it is | Express server with tool-use chat. A router (`agents/zaki.js:35-54`) picks a CFO agent (6 tools, `agents/farid.js:27-77`) or a commercial agent (4 tools) and runs a streaming tool loop capped at 8 iterations (`agents/zaki.js:60-170`) | VERIFIED |
| Where figures come from | Real Odoo reads through `/web/dataset/call_kw` `search_read` / `read_group` (`odoo/client.js:64-95`) on `account.move`, `account.move.line`, `account.account`, `res.currency` (`agents/farid.js:81-327`). `/api/dashboard`, `/api/financials`, `/api/company` are also real reads (`server.js:196-330`) | VERIFIED |
| Written for one named client | The prompts name one client (`agents/zaki.js:9,24`; `agents/farid.js:10`), bank account codes are fixed (`odoo/models.js:55`), and one tool targets a single supplier (`agents/farid.js:197-238`). It is not a multi-tenant product | VERIFIED |
| Figure quality | P&L is built from account-code prefixes `4` and `6` (`agents/farid.js:278,291`), which is chart-specific. `aed_equivalent` is just the balance, with no currency conversion (`agents/farid.js:108-109`) | VERIFIED |
| Unrelated route | `/api/seo` is a PageSpeed proxy (`server.js:333-379`) | VERIFIED |
| Credentials | Per user. The user supplies an Odoo URL, database, email and password; the server signs in as that user and holds the Odoo session id in an in-memory map keyed by email (`server.js:36,122-136`; `odoo/client.js:48-60`). This is the only standalone implementation where Odoo enforces the caller's own access rights and record rules. Sessions are lost on restart | VERIFIED |
| Auth | Every protected route validates the bearer token against `zaki-server` (`server.js:42-73`); login and register are proxied (`:76-102`); `/api/v1/*` is a pass-through proxy (`:395-417`) | VERIFIED |
| SSRF | `/erp/connect` accepts any URL (`server.js:122-136`); finding APP-05 | VERIFIED code, REPORTED finding |
| LLM | Vendor SDK, key in `.env`, model set at `agents/zaki.js:7`. Tools are read-only. No audit log, metering or rate limit; history is cut to 20 turns (`server.js:425-438`) | VERIFIED |
| Model retirement | The configured model is reported as deprecated and retiring on 2026-11-30. Source is a reference cached on 2026-11-03, not a live lookup. It matters only if this app is live | REPORTED; live status UNKNOWN |
| Latent bug | Chat with no Odoo connection passes `conn = null` into the tools (`server.js:164`), which would fail on `conn.baseUrl` | VERIFIED by reading |
| Dead dependencies | All auth depends on `zaki-server` on port 8002 (`server.js:14`, `ecosystem.config.js:18`). Without it every protected route returns 503 | VERIFIED |
| Tests / CI | No tests. CI runs only `npm audit` (`.github/workflows/ci.yml:262-278`) | VERIFIED |
| Deploy branch | `deploy.sh:12` and `update.sh:9` pull branch `claude/odoo-architecture-review-ujm0W`, not `main` | VERIFIED |
| Deploy hazard | `ops/deployment/deploy-website.sh:50,60` runs `rsync -a --delete` of the static page into `/var/www/zaki.mumtaz.digital`, the same directory the node app runs from and keeps its `.env` in (`ecosystem.config.js:9`, `deploy.sh:9,50-58`) | VERIFIED |
| Size | About 1,500 lines of server JavaScript plus `public/` (`app.js` 700, `chat.html` 621, `ceo.html` 504, `index.html` 7,171) | VERIFIED |

### 3.4 FastAPI — `platform/zaki/` and `platform/db/schema.sql`

| Point | Finding | Status |
|---|---|---|
| What it is | Endpoints for snapshot, streaming briefing and chat, a rule-based health score and opportunities, a voice proxy and a knowledge-base CRUD (`backend/main.py:192-317`) | VERIFIED |
| Where figures come from | One Odoo call, `zaki.connector.get_snapshot` over XML-RPC (`:70-81`). Any failure silently returns zeros (`:80-81`). Opportunities hard-code AED (`:272`) | VERIFIED |
| Credentials | One shared Odoo administrator for every tenant database (`:36-37,74-78`). The tenant database is looked up from `tenants.odoo_db` by an integer the caller supplies (`:62-67,84-90`) | VERIFIED |
| Auth | None. `GET /financials/{tenant_id}`, `/health-score/{id}`, `/opportunities/{id}`, `GET /kb/{id}`, `POST /kb/save`, `DELETE /kb/{entry_id}` and `/voice` have no check (`:192,250,269,293,303,313,233`). `_require` only checks that a bearer header exists when a flag is set; it never validates it (`:179-182`) | VERIFIED |
| Front end | Takes `tenant_id` from the URL or defaults to 1 and sends no auth header (`frontend/index.html:145,152,160,170`) | VERIFIED |
| CORS | Falls back to `*` with credentials (`backend/main.py:41-45`) | VERIFIED |
| Audit match | Matches APP-01, APP-02, APP-09, APP-10, APP-14 | REPORTED |
| LLM | Async vendor client, key from the server `.env`, plain prompt with the snapshot inserted (`:38,47,111-144`). No audit or metering | VERIFIED |
| Liability wording | The prompt tells the model never to refer the user to a professional (`:130`); nothing checks its figures | VERIFIED |
| Persistent injection path | Any chat message containing words such as "client" or "decided" is written to the knowledge base and re-injected into later prompts (`:216-225,93-104`), and the write is unauthenticated. Rows live in `zaki_kb` (`platform/db/schema.sql:104-115`) | VERIFIED |
| Dead dependencies | Needs the `tenants` table populated by a control panel that the README names but which is absent from `platform/` | VERIFIED |
| Tests / CI | None; `platform/` is outside every lint and test job | VERIFIED |
| Size | `main.py` 317 lines, `frontend/index.html` 361 lines; last change 2026-06-13 | VERIFIED |

### 3.5 `addons/mumtaz_zaki/`

| Point | Finding | Status |
|---|---|---|
| What it is | `zaki.connector.get_snapshot` (`models/zaki_connector.py:19-80`), an hourly-cron morning-briefing email (`models/zaki_briefing.py:44-93`, `data/zaki_cron.xml`), a board-pack PDF wizard (`models/zaki_board_pack.py`), and a JSON route `/zaki/api/snapshot` (`controllers/zaki_api.py:14`) | VERIFIED |
| LLM | None anywhere. The "briefing" is a fixed HTML template (`models/zaki_briefing.py:96-182`) | VERIFIED |
| Data | Real ORM reads of `account.move`, `account.move.line`, optional `crm.lead` and `hr.payslip` | VERIFIED |
| Defect: cash is always 0 | Cash sums `getattr(journal, "current_balance", 0.0)` (`models/zaki_connector.py:46-47`). In Odoo 19 that field is on `account.account`, not `account.journal`, and no addon adds it. Runway is therefore 0 days whenever there are expenses (`:63`) | VERIFIED by reading against an Odoo 19 checkout; not executed |
| Defect: revenue basis | Revenue is `amount_total_signed` of invoices, so tax-inclusive and not from the ledger (`:24-30`) | VERIFIED |
| Defect: no company scope | No company domain in any search (`:24-58`). Through the controller it runs under `sudo()` (`controllers/zaki_api.py:25`); the cron runs as the cron user with `with_company` (`models/zaki_briefing.py:53,58`). Record rules do not apply to the superuser, so both sum every company in the database | VERIFIED by reading |
| Auth | Since PR #175 the route refuses share users and users without `account.group_account_readonly` or `account.group_account_invoice` (`controllers/zaki_api.py:19-22`). This closes the "any signed-in user" half of ODOO-04 | VERIFIED |
| Remainder of ODOO-04 | The audit's other remedy ("remove `sudo()`, add company domain", `docs/infrastructure-audit/04_SECURITY_AUDIT.md:96`) is not done, while `docs/erp/architecture/SECURITY_MATRIX.md:81` lists REVIEW-03 as closed | REPORTED (documents); code state VERIFIED |
| Tests | 2 `HttpCase` tests (`tests/test_snapshot_access.py:30,37`), picked up by `scripts/platform_ci.sh` through `.github/workflows/platform-odoo-install.yml` | VERIFIED wiring |
| CI result | Whether the latest run is green | UNKNOWN |
| Size | 418 Python lines, 15 files | VERIFIED |

### 3.6 `addons/mumtaz_ai/`

| Point | Finding | Status |
|---|---|---|
| What it is | Session and message models plus a keyword intent router (`services/ai_service.py:64-72`) | VERIFIED |
| What actually reads data | Only `financial_query`: cash from `asset_cash` and `liability_credit_card` accounts, company-scoped (`:83-105`). CRM and sales handlers return a fixed sentence (`:107-121`) | VERIFIED |
| Model call | `general_query` calls `mumtaz.ai.provider.base`, which always answers "Provider not configured" and passes no key (`:123-130`; `providers/base_provider.py:8-22`). No model call is reachable from this module's own flow | VERIFIED |
| Providers | Two providers over raw HTTP (`providers/openai_provider.py:11`, `providers/anthropic_provider.py:12`), key passed in `context`. Used only by `mumtaz_voice` | VERIFIED |
| Auth | Company and own-record rules (`security/mumtaz_ai_security.xml`); checks that the session company is one of the user's companies (`services/ai_service.py:56-58`) | VERIFIED |
| Audit | `mumtaz.core.log` holds the full prompt and response (`services/ai_service.py:35-43`) | VERIFIED |
| Tests | 0. 450 Python lines; last change 2026-04-04 | VERIFIED |
| Overlap | Duplicates the Jawhar provider with weaker rules — decision D-03 (`docs/erp/project/DECISION_REGISTER.md:28`) | REPORTED |

### 3.7 `addons/mumtaz_voice/`

| Point | Finding | Status |
|---|---|---|
| What it is | Text or voice CFO questions inside Odoo, and the only Odoo path that reaches a model. Keyword intent (`services/cfo_service.py:10-30`) → deterministic context from account types: cash, P&L month and year to date, receivable and payable ageing, sales (`:32-181`) → one prompt (`services/voice_service.py:112-132`) | VERIFIED |
| No-provider path | Returns the raw figures (`services/voice_service.py:134-142`) | VERIFIED |
| Data | ORM as the signed-in user with `company_id = session.company_id` on every query (`services/cfo_service.py:67-163`). Chart-agnostic | VERIFIED |
| Auth | `auth="user"` routes with company and own-record rules | VERIFIED |
| Cost-abuse path | `/mumtaz/voice/tts` reads settings with `sudo()` and is open to any authenticated user including portal users, with no rate limit (`controllers/voice_controller.py:46-62`). Speech synthesis is proxied to an external provider (`:46-105`) | VERIFIED |
| Likely defect | The chat path reads `settings.api_key` without `sudo()` (`services/voice_service.py:122`) while the field is restricted to `base.group_system` (`addons/mumtaz_core/models/mumtaz_core_settings.py:41-44`), so non-administrators would get an access error | VERIFIED by reading; not executed |
| LLM | Through the `mumtaz_ai` providers; key and model from `mumtaz.core.settings`; no tool use. The prompt says "never fabricate figures" (`services/voice_service.py:13`) but nothing checks the output | VERIFIED |
| Quota | A check through `mumtaz.feature.access.service` exists (`services/voice_service.py:80-96`), but nothing in `addons/` creates `mumtaz.usage.metric` rows and no data file seeds feature `ai_access`, so the lookup fails open (`addons/mumtaz_control_plane/models/feature_access_service.py:73-83`). Effectively unmetered. `requests_per_minute_limit` is never read outside its own model | VERIFIED |
| Tests | 0. 665 Python lines | VERIFIED |
| Overlap | `cfo_service.py` recomputes what `mumtaz_financial_reports` computes; a third voice path | VERIFIED |

### 3.8 `addons/mumtaz_cfo_base`, `mumtaz_cfo_ingestion`, `mumtaz_cfo_transactions`, `mumtaz_cfo_toolkit`, `mumtaz_super_toolkit`

| Point | Finding | Status |
|---|---|---|
| What it is | A workspace, CSV upload, and a normalised shadow ledger `mumtaz.cfo.transaction` with duplicate hashing and a review queue (`mumtaz_cfo_transactions/services/ingestion_service.py:16-81`). CSV only; Excel is a stub message (`mumtaz_cfo_ingestion/models/cfo_upload_batch.py:82-95`). Unrelated to `account.move`; no AI | VERIFIED |
| Empty shells | `mumtaz_cfo_toolkit` and `mumtaz_super_toolkit` are installer manifests of 18 and 17 lines | VERIFIED |
| Consumers | Two duplicated portal pages, `/app/zaki` (`mumtaz_app_portal/controllers/app.py:392-456`) and `/mumtaz/portal/zaki` (`mumtaz_portal_routing/controllers/routing.py:409-477`), which total inflows and outflows | VERIFIED |
| Broken links | Their "Ask ZAKI" links go to `/mumtaz/ai`, a route no controller defines (14 XML references, 0 Python) | VERIFIED |
| Auth | Company rules; a portal rule by tenant (`mumtaz_cfo_base/security/cfo_workspace_tenant_rules.xml`) | VERIFIED |
| Privilege defect | `group_mumtaz_cfo_manager` implies `base.group_system` (`mumtaz_cfo_base/security/cfo_base_security.xml:10`), so a CFO manager is a full Odoo administrator | VERIFIED |
| Tests | 0 | VERIFIED |

### 3.9 `addons/mumtaz_financial_reports/`

| Point | Finding | Status |
|---|---|---|
| What it is | P&L, balance sheet, trial balance and aged partners from posted `account.move.line`, by account type, with drill-down (`controllers/reports.py:51-325`). No AI | VERIFIED |
| Data and auth | `request.env` as the user, no `sudo()` anywhere, `company_id = env.company.id` (`:53-56`); `auth="user"`; access rests on the accounting access rights | VERIFIED |
| Tests | 0. 371 Python lines | VERIFIED |
| Standing | The most rigorous figure engine in the repository; overlaps `mumtaz_voice/services/cfo_service.py` | VERIFIED |

### 3.10 `addons/mumtaz_ceo_dashboard/`

Not ZAKI. It is a dashboard for a media-buying business; its data route lives in `addons/mumtaz_media_buying/controllers/dashboard.py:40`, and otherwise it renders built-in sample data (`static/src/js/ceo_dashboard.js:133-141`). 0 tests. VERIFIED.

### 3.11 `addons/mumtaz_core/` (AI settings)

| Point | Finding | Status |
|---|---|---|
| Settings | Per-company `mumtaz.core.settings`: provider, model lists, feature toggles, token limit (`models/mumtaz_core_settings.py:33-163`) | VERIFIED |
| Key storage | Provider and voice keys are plain `Char` columns restricted to `base.group_system` (`:41-44,75-78`), not encrypted | VERIFIED |
| Key sync | Keys are pulled daily from the control-panel host (`:223-273,311-322`) and can be pushed through an `auth="none"` route authenticated by a stored platform token (`controllers/platform_controller.py:16-69`). The control-panel source that would serve these is not in the repository | VERIFIED |
| Audit table | `mumtaz.core.log`; managers can edit rows (`security/ir.model.access.csv:6`) | VERIFIED |
| Tests | 0. 664 Python lines | VERIFIED |

### 3.12 Governance reference — `addons/mumtaz_jewellery_ai/`

| Control | Where | Status |
|---|---|---|
| Provider: one function over raw HTTP; key only from the environment, never stored; refusals handled; returns token counts and duration | `services/provider.py:24-86` | VERIFIED |
| Policy: levels A–E and a tool registry with a level per tool; tools run as the signed-in user | `services/policy.py:6-42` | VERIFIED |
| Data exclusion: restricted clients never enter a model request | `services/policy.py:82-88` | VERIFIED |
| Grounding: any model sentence containing a number the tools did not supply is discarded | `services/policy.py:107-114` | VERIFIED |
| Audit: one `jewellery.ai.run` row per action including refusals, with level, model, tokens, payload digest, sources and policy version; read-only access rights | `models/ai_run.py`; `security/ir.model.access.csv` | VERIFIED |
| Approval: drafts are bound to a SHA-256 of the exact text; an edit resets approval; drafts expire; nothing sends | `models/ai_draft.py:86-113` | VERIFIED |
| Tenant pause switch; a local path when no key is set | `models/agents.py:46-56` | VERIFIED |
| Tests: 23, run by `scripts/jewel_ci.sh:32-34` and `jewel-odoo-tests.yml` | `tests/test_agents.py` | VERIFIED |
| Gaps: no cost budget or quota, no link to `mumtaz.usage.metric` | — | VERIFIED |
| Design description | `docs/jawhar/AI_AGENT_ARCHITECTURE.md` | REPORTED |

1,395 Python lines.

### 3.13 Comparison only — `c2p-delivery-system/delivery_api/llm.py`

276 lines: provider switch (`:24`), per-task model routing (`:70`), retry and backoff, an output-token ceiling, prompt caching (`:166-168`), every call logged to `agent_runs` with tokens (`:207-271`). No policy levels, approvals or tenant metering in this file. A different product and runtime. VERIFIED.

## 4. Verdicts

| Implementation | Verdict | Reason | Worth carrying forward |
|---|---|---|---|
| Static page | Reference, then retire | No server side; the user's model key sits in the browser; figures are local or demo; its backend is deleted | Panel layout and the calculators |
| Node app | Reference, then retire | Hard-coded to one client; auth depends on a deleted service; SSRF; configured model reported as retiring | The streaming tool loop and the per-user Odoo session pattern |
| `platform/zaki` backend and `zaki_kb` | **Retire** | No authentication, one shared admin across tenants, unauthenticated knowledge-base writes that feed prompts. **Do not run `platform/ops/install/05-cutover.sh`** (`:43-64` would deploy it) | The 361-line front end as UI reference only |
| `mumtaz_zaki` | **Keep — canonical ZAKI addon** | Right place, right name, already gated and tested | Must fix first: `sudo()`, company domain, cash field, revenue basis |
| `mumtaz_ai` | Retire (D-03) | Router with stubs; providers duplicate Jawhar's with weaker rules; no tests | — |
| `mumtaz_voice` | Reference; move `cfo_service.py` into `mumtaz_zaki`, then retire the module | Best company-scoped tool data layer | Voice UI can return later as an optional front end |
| `mumtaz_financial_reports` | **Keep** | Canonical deterministic statements; ZAKI tools should call its computation | Needs tests |
| `mumtaz_cfo_base` / `_ingestion` / `_transactions` | Keep as a separate optional product, not ZAKI core | A CSV ledger for businesses without Odoo accounting | Fix manager-implies-admin |
| `mumtaz_cfo_toolkit`, `mumtaz_super_toolkit` | Retire | Empty installer shells | — |
| `mumtaz_ceo_dashboard` | Out of scope | Media-buying vertical | — |
| `mumtaz_core` | Keep | Settings, toggles and tenant code | Move keys out of the database; drop the sync with an absent control panel |
| `mumtaz_jewellery_ai` | **Keep — canonical governance source** | The only code with levels, grounding, run log, approvals and tests | — |
| C2P `llm.py` | Keep in C2P; comparison only | Different product | Ideas only: routing, caching, retry, token cap |

"Retire" here is a code decision. Nothing may be removed from a server until section 9 has shown what is actually running.

## 5. Target architecture (PROPOSED)

### 5.1 Principle

ZAKI runs inside each tenant's Odoo. Odoo is already the identity authority (`docs/erp/architecture/SECURITY_MATRIX.md:11`, REPORTED) and holds the data. There is **one** shared, permission-aware AI layer; ZAKI, Jawhar's agents and any later edition are consumers of it.

### 5.2 Rules the layer enforces

| Rule | How |
|---|---|
| Tools run as the signed-in user | Every tool executes through the ORM as `request.env.user`. Access rights, record rules and company scope are enforced by the server. No `sudo()` on a read that returns business data |
| No administrator credential for agents | No shared Odoo admin, no service account that can read across tenants. The `platform/zaki` pattern is not repeated |
| No unrestricted SQL | Tools are named functions in a registry with typed arguments. There is no "run this query" or "call any model method" tool |
| Policy levels | Levels A–E per tool, as in Jawhar: read and explain at the low levels, drafting in the middle, anything that changes a record or leaves the system at the top |
| Human approval for consequential actions | The agent produces a draft. A named person approves the exact text (approval is bound to a digest; an edit resets it; drafts expire). Nothing posts, pays or sends by itself |
| Grounding | A model sentence containing a number the tools did not supply is discarded. With no provider key, the deterministic figures are returned without narration |
| Prompt-injection handling | Ledger text (partner names, descriptions, memo lines, uploaded files) is passed as data and marked as such; it is never treated as instructions. No free-text memory that users or documents can write into and that is re-injected later (the `zaki_kb` pattern) |
| Audit | One run-log row per action, including refusals: user, company, level, tools called, model, tokens, payload digest, sources, policy version. Read-only access rights; a company rule on the log |
| Metering and entitlement | One `mumtaz.usage.metric` row per run. Entitlement is resolved through `mumtaz.feature.access.service` and **fails closed** on paid plans: an unregistered feature or a missing subscription means no model call |
| Cost control | A per-tenant monthly budget in tokens or money; a hard stop when it is reached; a per-user rate limit |
| Pause | A tenant-level switch that stops all model calls and leaves the deterministic paths working |
| Keys | Provider key from the server environment, never stored in a tenant database and never sent to a browser |
| Banking pilots | Read-only. No tool that initiates or approves a payment, in any pilot |

### 5.3 Parts, and the existing code each is built from

| Part | Build from (existing) | New work |
|---|---|---|
| **AI core addon** — provider, policy levels A–E, tool registry, run log, drafts and approvals, pause | `addons/mumtaz_jewellery_ai/services/provider.py`, `services/policy.py` (generic parts), `models/ai_run.py`, `models/ai_draft.py`, pause in `models/agents.py:46-56` | Extract into a generic module: copy first, re-point Jawhar later, and keep the `jewellery.ai.*` model names where they are tested and audited. Parameterise the environment key and model. Add a company rule on the run log. This is the single provider abstraction and delivers D-03 |
| **ZAKI finance tools** — level A, read-only | `addons/mumtaz_voice/services/cfo_service.py`; `addons/mumtaz_financial_reports/controllers/reports.py:51-270`; the `mumtaz_zaki` briefing and board pack | Register the tools in the core registry. Fix `zaki_connector`: no `sudo()`, company domain, cash from `asset_cash` accounts, ledger-based revenue. One revenue definition for every surface |
| **Ask endpoint** in `mumtaz_zaki`, `auth="user"` | Intent keywords `cfo_service.py:10-30`; grounding `policy.py:107-114`; local fallback `voice_service.py:134-142` | `/zaki/api/ask`: classify → run tools as the user → the model narrates the facts only → grounding check → run-log row |
| **Consequential actions** — levels C and D | `ai_draft.py` digest-bound approval | Later slice: for example a dunning-email draft that a named person approves and sends |
| **Metering and entitlement** | `addons/mumtaz_control_plane/models/usage_metric.py` (already has `source_system = "ai"`), `feature_access_service.py`, token fields on the run log | Write a usage row per run. Seed the `ai_access` feature. Fail closed. Per-tenant monthly budget. Enforce or delete `requests_per_minute_limit`. With a database per tenant, the tenant does not hold the control plane's tables, so entitlement and usage cross an API (see `MUMTAZ_SAAS_CONTROL_PLANE.md`) |
| **Embedded mode** | `addons/mumtaz_voice/static/src/js/voice_assistant.js`; the `mumtaz_financial_reports` client action | One client action calling `/zaki/api/*` |
| **Standalone mode** — `zaki.mumtaz.digital` | Panels from the static page or `platform/zaki/frontend/index.html`; stream handling from `node-app/public/app.js` | A thin client that signs the user into their own tenant Odoo and calls the same `/zaki/api/*`. No model key in the browser and no separate data backend. If a streaming relay is ever needed, it forwards the user's credential only |
| **Edition mode** | Jawhar's tool-registry pattern | An edition registers extra tools with the core. `mumtaz_zaki` is not a hard dependency of any edition; the entitlement switches it on |

### 5.4 The three ZAKI modes

| Mode | What the user sees | What runs |
|---|---|---|
| Embedded in ERP | A ZAKI panel inside the tenant's Odoo | `mumtaz_zaki` + AI core in the tenant database |
| Standalone | `zaki.mumtaz.digital` | The same tenant endpoints behind a thin client. The subscriber still has a tenant database; whether that is a full ERP or only the CSV ledger is an owner decision (section 8) |
| Optional per edition | ZAKI appears in Jawhar, Pharma or another edition when the plan includes it | The edition registers its tools; the same core, log, budget and approvals apply |

## 6. Build order (PROPOSED)

### Slice 1 — ERP-embedded, read-only, no new website

| Step | Work | Acceptance test |
|---|---|---|
| 1 | Fix `zaki_connector`: remove `sudo()`, add the company domain, read cash from `asset_cash` accounts, take revenue from the ledger | Two companies in one database: each user's snapshot contains only their company's figures. A posted bank entry produces a non-zero cash figure equal to the ledger balance. The two existing access tests still pass |
| 2 | Create the AI core by copying provider, policy and run log from Jawhar | The Jawhar suite (23 tests) still passes unchanged; the core's own tests cover level enforcement and run-log writing |
| 3 | Add `/zaki/api/ask` at levels A and B with the grounding check and a run-log row carrying tokens | Portal user and non-accounting user are refused. A model reply containing a number the tools did not return is discarded. With no key set, the endpoint returns the deterministic figures. Every call, including a refusal, leaves exactly one run-log row |
| 4 | Add all of the above to `scripts/platform_ci.sh` | The suite runs on a fresh Odoo 19 database in CI |

### Later slices

| Slice | Work | Acceptance test |
|---|---|---|
| 2 — metering and entitlement | Usage row per run; `ai_access` feature seeded; fail closed; monthly budget; rate limit | No subscription → no model call. Budget reached → hard stop with a clear message; deterministic path still works. Usage total equals the sum of run-log tokens |
| 3 — standalone thin client | `zaki.mumtaz.digital` signs the user into their own tenant | No provider key and no Odoo password in browser storage. A user of tenant A cannot obtain any figure from tenant B |
| 4 — drafts and approvals | Level C/D actions through digest-bound drafts | An edited draft loses its approval. An expired draft cannot be sent. Nothing is sent without a named approver in the log |

Each slice is reversible: the module can be uninstalled, and no slice changes an existing table.

## 7. Risks if nothing is done

| # | Risk | Status |
|---|---|---|
| 1 | **Cross-tenant finance exposure.** Running `platform/ops/install/05-cutover.sh` would put an unauthenticated API with one Odoo administrator for all tenants on the public host | VERIFIED code; deployment UNKNOWN |
| 2 | **Imminent breakage.** Node-app chat stops when its configured model retires on 2026-11-30 | REPORTED (cached reference); relevant only if the app is live — UNKNOWN |
| 3 | **Wrong numbers to management.** Briefings and board packs from `mumtaz_zaki` show cash 0 and runway 0 days, and sum all companies | VERIFIED by reading |
| 4 | **Key exposure.** Users' own model and voice keys sit in browser storage beside 154 `innerHTML` sinks; tenant keys are plain text in the Odoo database and can be overwritten through a token-only route | VERIFIED; the XSS finding is REPORTED |
| 5 | **Uncapped spend.** The quota check exists but nothing feeds it; the speech proxy is open to portal users | VERIFIED |
| 6 | **Deploy accident.** `deploy-website.sh` with `--delete` can wipe the node app and its `.env` | VERIFIED |
| 7 | **Liability.** The `platform/zaki` prompt tells the model never to refer the user to a professional, with no grounding check on its figures | VERIFIED |
| 8 | **Client data in the repository.** One client's name and account structure are in the node-app prompts; the repository is described as public | VERIFIED; public status REPORTED |
| 9 | **Broken product surface.** Portal "Ask ZAKI" links go to a route that does not exist | VERIFIED |
| 10 | **Continued divergence.** Four revenue definitions, three user interfaces, three voice paths, two provider layers | VERIFIED |

## 8. Decisions needed from the owner

| # | Decision | Recommendation |
|---|---|---|
| 1 | Confirm the canonical ZAKI (D-10): `mumtaz_zaki` in the tenant's Odoo, with the three standalone codebases kept as reference and then retired | Yes, subject to the server check in section 9 |
| 2 | Confirm one AI provider and policy layer (D-03): the Jawhar policy, extracted into a shared core | Yes |
| 3 | Who pays for the model: platform-paid key in the server environment and metered, or a key supplied by each tenant and stored in their database? | Platform-paid and metered; it matches Jawhar and keeps keys out of tenant databases |
| 4 | Does a standalone ZAKI subscriber get a full tenant Odoo, or only the CSV ledger (`mumtaz_cfo_*`)? | Decide before slice 3 |
| 5 | One database per tenant, or companies in one database? `mumtaz.core.settings.tenant_code` is per company (VERIFIED) while `platform/README.md` and ADR-002 say database per tenant (REPORTED). This sets how the standalone client finds the tenant | Database per tenant (ADR-002) |
| 6 | Approval to remove the node app's client-specific prompts and account codes from the public repository | Yes |

## 9. Verify on the server before deciding

All UNKNOWN from git. Read-only commands; the owner runs them and pastes the output.

1. `nginx -T` for `zaki.mumtaz.digital`: which root and which upstream (3000, 8001 or 8002). The repository holds three definitions: `sites/zaki.mumtaz.digital/node-app/nginx.conf`, `platform/ops/nginx/zaki.mumtaz.digital.conf`, `ops/deployment/nginx-mumtaz-platform.conf:217-279`.
2. Process state: `pm2 ls`; `systemctl status zaki zaki-server mumtaz-platform`; listeners on 3000, 8001, 8002.
3. Contents of `/var/www/zaki.mumtaz.digital` (static file only, or `server.js` plus `.env`), `/opt/mumtaz/zaki`, `/opt/zaki-server`.
4. Whether the server `.env` holds an Odoo administrator password and the bearer-check flag (names only, not values); row counts in `tenants` and `zaki_kb`.
5. Per Odoo database: install state of `mumtaz_zaki`, `mumtaz_ai`, `mumtaz_voice`, `mumtaz_cfo_*`, `mumtaz_financial_reports`; row counts of `mumtaz_ai_message`, `mumtaz_voice_message`, `zaki_briefing_log`; the count (not the values) of settings rows with a key set.
6. Access-log traffic for the host, and model-provider usage per key, to see which code actually calls a model.
7. Which branch the server has checked out.

## 10. Could not determine

- Which implementation, if any, serves `zaki.mumtaz.digital`, and whether `zaki-server` still runs.
- Whether CI is currently green; no tests were run for this evaluation.
- Any Odoo runtime behaviour. The cash-field defect, the cross-company effect of `sudo()` and the `api_key` access error are from reading code (and an Odoo 19 checkout outside the repository), not from execution.
- Which modules are installed in which database; any real usage or spend.
- Whether a control-panel API exists on the server for the credential sync in `mumtaz_core`.
- Whether keys that were previously deployed have been rotated.
- The live status of model identifiers: it comes from a reference cached on 2026-11-03.
- What `zaki-server` did for `sync-odoo`; only its deletion was confirmed.
- The contents of PR #175 beyond the current file and the commit title.
- Tests for `c2p-delivery-system`.
