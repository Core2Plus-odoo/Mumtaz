# 04 — Security Audit

**Method:** static analysis, configuration reading, dependency and history review. No exploit testing, no login attempts, no scanning, no requests that reached a production host. Secret values are never reproduced; where a credential-like value exists, only its location and category are given.

**Status words:** *Confirmed* — the code or configuration does this as written (verified in the repository). *Reported* — recorded in repository documents from owner-run server output; not re-verified. *Suspected* — depends on server state or framework behaviour that could not be checked.

**Finding IDs:** `F-` infrastructure and operations (ranked in `10_RISK_REGISTER.md`); `ODOO-`, `C2P-`, `APP-` code-level findings from the three code reviews.

---

## Part A — Findings that need attention first

### A1. Odoo application ports reachable from the internet; a client ledger served over plain HTTP — **Critical, Reported** (F-01)

- The IG2 instance (`odoo3`) listens on `0.0.0.0:8071`; the firewall rule for 8071 was added by hand and "re-added" after an update; users reach it at `http://<IP>:8071` with no TLS. Passwords and accounting data cross the network in clear text. Source: `docs/erp/00-current-system-audit.md` on branch `claude/resume-help-95ne9v`, dated 2026-11-20.
- A demo script on the same branch tells the presenter to record on that URL.
- Six pages of the public marketing site in `apps/website/` link "Platform Login" to `http://<IP>:8069/` (APP-12), which implies the main Odoo port is also reachable directly.
- An earlier audit on branch `claude/gifted-turing-jjdsb2` states that the firewall permits inbound access to the Odoo ports from any address and that one reachable instance is "still protected only by a default-strength administrator credential", reported in three earlier sessions and not fixed.
- No Odoo vhost in the repository blocks `/web/database` (APP-13).

**Not verified this session.** If the V-pack confirms it, this is the single most urgent item. Remediation is batch 2C (and 2A for the credential).

### A2. No verified backup of any production data — **Critical, Confirmed for the repository; server state Not Verified** (F-02)

See `09_BACKUP_AND_RECOVERY_AUDIT.md`. The one scheduled backup job has never executed.

### A3. The repository is public and describes how to reach these systems — **Critical, Confirmed** (F-03)

Readable by anyone today, across `main` and the open branches:

| Category | Where (examples) |
|---|---|
| Production IP address | 20 occurrences in 8+ files, e.g. `CLAUDE.md`, `c2p-delivery-system/deploy/finish.sh:5`, `deploy/jewel-staging/README.md`, `apps/website/*.html` |
| Port-per-tenant map, unit names, config paths, on-disk layout | `docs/pharma/DEPLOY_LOG.md` (branch), `c2p-delivery-system/scripts/collect_production_addons.sh`, `addons/c2p_project_tracker/scripts/backup_and_install.md` |
| Database names (eight), Odoo build, user/lead/module counts | `c2p-delivery-system/docs/05-build-log.md:973-991`, `delivery_api/README.md` |
| A client's legal name, sister company, customer list, named finance staff | `docs/erp/00-current-system-audit.md` (branch `claude/resume-help-95ne9v`) |
| Staff names, role mailbox, bot user and its privilege level | `c2p-delivery-system/docs/05-build-log.md:1214-1217`, `RUNBOOK.md`, `CLAUDE-CODE-PROMPT.md` |
| Owner's name and admin login email | `platform/ops/install/00-foundation.sh:96`, `apps/platform/setup_master_admin.sh:22` |
| Statement that a reachable instance has a weak administrator credential | `docs/project/01-AS-IS-AUDIT.md` §3.6 (branch `claude/gifted-turing-jjdsb2`) |
| Internal CRM automation rules | `c2p-delivery-system/docs/07-mumtaz-c2p-crm-findings.md` |
| Literal fallback credentials in scripts | `apps/platform/setup_master_admin.sh:141`, `apps/erp/deploy.sh:30-31` (APP-11) |

Combined with A1 this is a map plus a hint. Making the repository private stops further disclosure; it does not undo what has already been cloned or indexed, so the weak credential and the open ports must be fixed regardless.

### A4. One shared secret lets any tenant administrator log in to any other tenant — **Critical, Confirmed in code; live exposure depends on which modules are installed** (ODOO-01)

`addons/mumtaz_tenant_manager/services/provisioning.py:295-297` copies a single environment secret into every tenant database. `addons/mumtaz_sso/controllers/main.py:35-93` (`auth="none"`, CSRF off) accepts a token naming **any database and any login**, checks it against that database's copy of the secret, and opens a session as that user. A tenant's own administrator can read the secret from their database and so mint a valid token for another tenant. The token rides in the URL, has no nonce and no lifetime cap, and bypasses two-factor authentication (ODOO-11).

Fix: per-tenant secrets (or asymmetric signing where tenants hold only a public key), bind tokens to the request host, single-use nonce, short TTL. Until fixed, `mumtaz_sso` should not be installed on any database that shares a server with another tenant.

### A5. Identity documents readable by every portal user — **High, Confirmed on the branch Faizy production runs** (ODOO-06)

`faizy_core/security/ir.model.access.csv:43` grants the portal group read on `faizy.document` (CNICs, passports). `faizy_security.xml` has record rules for orders, family members and subscriptions but none for documents, and the attachment field has no group. Any signed-in customer can read every family's documents through the standard RPC interface. Fix is one record rule: `[('partner_id','=',user.partner_id.id)]`.

### A6. Financial data exposed to any logged-in user, across companies — **High, Confirmed** (ODOO-04, ODOO-05)

- `/zaki/api/snapshot` runs the finance connector under `sudo()` with no company filter: revenue, cash, receivables, top overdue debtors, payroll — for all companies — to any session user including portal users.
- `/app*` in `mumtaz_app_portal` reads invoices, bank balances, sales, purchases, stock and CRM under `sudo()` behind a check that only excludes anonymous users and platform admins.

### A7. Any logged-in user can rewrite everyone's permissions, or drive the Stripe key — **High, Confirmed** (ODOO-02, ODOO-03)

Public `@api.model` methods on ACL-free abstract models are callable over RPC by any authenticated user, portal included: `mumtaz.erp.module.access.set_module_access` and `mumtaz.marketplace.access.set_access` add or remove all internal users from accounting/stock/sales/HR groups under `sudo()`; three Stripe client methods create customers and payment intents with the platform's secret key. Fix: underscore-prefix the methods and check a platform-admin group.

### A8. C2P Agency OS: open by default, and can be made to hand over its stored credentials — **High (Critical if production runs with no auth mode), Confirmed in code** (C2P-01 … C2P-05)

- With neither `C2P_ADMIN_AUTH=1` nor `MULTITENANT=1`, the middleware is a no-op and all 97 routes are open at application level; only nginx basic auth stands in front. A flag value such as `true` silently leaves it open. `enable-admin-login.sh` removes basic auth — so a half-applied switch leaves nothing.
- Anyone with API access can change the stored Odoo URL or GitHub repository **while the stored key or token is kept**, then trigger a test call: the admin-grade Odoo key or the GitHub token is sent to a host they choose (C2P-02). A git timeout returns the tokenised URL in the response (C2P-03).
- The GitHub `subdir` setting is not checked for `..`: generated files can be written outside the clone as the service user, which is probably `root` (C2P-04, C2P-15).
- Branding fields are written unescaped into proposal HTML: stored XSS on the console's origin, where the 7-day token sits in `localStorage`; with WeasyPrint installed, a route to server-side file reads (C2P-05).

**Which mode production runs in is Not Verified** (V-12).

### A9. ZAKI FastAPI backend has no authentication — **Critical in code; Not Verified whether deployed** (APP-01, APP-02, APP-09, APP-10)

`platform/zaki/backend/main.py`: the only gate is off by default and, when on, merely checks that a header exists. Any caller can read any tenant's financial snapshot by integer id, and write or delete entries in any tenant's knowledge base (which is concatenated into that tenant's system prompt). The service uses one Odoo administrator login for every tenant database and a PostgreSQL role created as `SUPERUSER`. If this service is listening on the VPS and proxied, it is the most exploitable code in the repository; if not, it must simply never be deployed as written.

### A10. Shared database role and cross-database behaviour — **High, Reported** (F-06, F-07)

One PostgreSQL role for the C2P CRM, the platform ERP, the client's ledger and a staging tenant; two production processes whose cron workers open every database on the server. A compromise of, or a bug in, any one Odoo instance reaches all of them. Detail in `05_DATABASE_AUDIT.md`.

---

## Part B — Application security by area

### B1. Odoo addons (53 modules on `main`; 2 Faizy modules)

Positive results worth stating: every non-abstract model has an ACL row; all three raw SQL statements are parameterised; no `eval`/`exec`/`pickle`/`subprocess`/`verify=False`; every outbound request sets a timeout; no core files are modified; the Stripe webhook verifies signatures correctly; Jewel's public tray and kiosk endpoints are properly scoped; no keys or passwords in data files.

| ID | Sev | Status | Finding | Location | Fix |
|---|---|---|---|---|---|
| ODOO-01 | **Critical** | Confirmed | Shared SSO secret → cross-tenant login | `mumtaz_tenant_manager/services/provisioning.py:295`; `mumtaz_sso/controllers/main.py:35-93` | Per-tenant or asymmetric secret; bind to host |
| ODOO-02 | High | Confirmed | Group rewrite callable by any user via RPC | `mumtaz_control_plane/models/erp_module_access.py:25`; `mumtaz_marketplace/models/marketplace_access.py:15` | Private methods + admin group check |
| ODOO-03 | High | Confirmed | Stripe client methods RPC-callable | `mumtaz_billing_stripe/models/stripe_client.py:92-121` | Same |
| ODOO-04 | High | Confirmed | All-company finance snapshot to any session user | `mumtaz_zaki/controllers/zaki_api.py:13`; `models/zaki_connector.py:23` | Remove `sudo()`, add company domain + group |
| ODOO-05 | High | Confirmed | `/app*` and portal routing read finance/CRM under `sudo()` | `mumtaz_app_portal/controllers/app.py:29-351`; `mumtaz_portal_routing/controllers/routing.py:311` | Same |
| ODOO-06 | High | Confirmed | Faizy documents readable by all portal users | `faizy_core/security/ir.model.access.csv:43` | Record rule |
| ODOO-07 | High | Confirmed, conditional | Demo module makes client sign-in code public | `mumtaz_jewellery_demo/hooks.py:631`; `mumtaz_jewellery_client/models/session.py:70` | Never install demo on a reachable DB; remove echo |
| ODOO-08 | High | Confirmed | Marketplace listings writable across companies | `mumtaz_marketplace/security/mumtaz_marketplace_rules.xml:4` | Separate write rule |
| ODOO-09 | Medium | Confirmed | Anonymous lead-creation API, CORS `*`, no throttle, returns ids and exception text | `mumtaz_api/controllers/api_v1.py:81-140` | Rate limit, captcha, origin list |
| ODOO-10 | Medium | Confirmed | Anonymous organisation signup without throttle | `mumtaz_org_config/controllers/signup.py:26-109` | Captcha, email confirmation |
| ODOO-11 | Medium | Confirmed | SSO token in URL, replayable, no TTL cap, loads registry before verifying | `mumtaz_sso/controllers/main.py:37-93` | POST + nonce + TTL |
| ODOO-12 | Medium | Confirmed | Provisioning wizard ignores `dry_run`; tenant admin password stored in plaintext field; DB created without master-password check | `mumtaz_tenant_manager/wizards/provision_wizard.py:44-96`; `models/mumtaz_tenant.py:90` | Honour flag; transient field |
| ODOO-13 | Medium | Confirmed | Process-wide `db_filter` monkeypatch with uncached SQL per request; unknown hosts fall through | `mumtaz_subdomain_routing/patch.py:65-104` | Cache; deny unknown; prefer proxy routing |
| ODOO-14 | Medium | Confirmed | 65 of 100 models have no record rule; applicant PII and all organisations readable by every internal user; non-public organisations readable by the public group | `mumtaz_org_config`, `mumtaz_organization` ACL files | Company rules |
| ODOO-15 | Medium | Confirmed | Vendor portal lets the vendor overwrite RFQ prices and create draft bills under `sudo()`; upload checked by extension only | `mumtaz_vendor_portal/controllers/vendor_portal.py:264-429` | Quote model + approval |
| ODOO-16 | Medium | Confirmed | Faizy workers can write any order field incl. fees | `faizy_core/security/faizy_security.xml:84` | Action methods only |
| ODOO-17 | Medium | Confirmed | Faizy anonymous signup attaches records to existing partners by phone; honeypot only | `faizy_website/controllers/main.py:187-375` | Verification + rate limit |
| ODOO-18 | Medium | Confirmed | Stripe webhook swallows processing errors with 200; amount not checked against event; zero-decimal currencies over-scaled ×100 | `mumtaz_billing_stripe/controllers/stripe_webhook.py:38-125`; `models/subscription.py:60` | Retry queue; verify amount/currency |
| ODOO-19 | Medium | Confirmed | E-invoice cron marks anything older than 24 h "rejected" without asking the tax authority, then resubmits; sandbox default marks invoices "accepted" with no call | `mumtaz_einvoicing/data/mumtaz_einvoice_data.xml:21,50`; `models/mumtaz_einvoice_config.py:63` | Query real status; mark simulation clearly |
| ODOO-20 | Medium | Confirmed | API gateway key lookup can never succeed (no ACL for public user); raw key never shown; empty pepper default; anonymous calls grow the log table | `mumtaz_api_gateway/services/auth_service.py:18`; `models/api_key.py:9-45` | Fix or remove the module |
| ODOO-21 | Medium | Confirmed | SSRF: scraper fetches any URL with redirects; platform URL receives a bearer token | `mumtaz_lead_scraper/services/fetcher.py:68`; `mumtaz_core/models/mumtaz_core_settings.py:230` | Block private ranges; pin host |
| ODOO-22 | Medium | Suspected | Login-redirect override may skip the 2FA step | `mumtaz_portal_routing/controllers/routing.py:74` | Call `super()` first |
| ODOO-23 | Medium | Confirmed | `push-credentials` endpoint (`auth=none`) compares a plaintext token by DB search; payload replaces provider keys | `mumtaz_core/controllers/platform_controller.py:16-42` | Hash + constant-time + throttle |
| ODOO-24 | Medium | Confirmed | Missing hard dependencies (`jewellery_sale` → `jewellery_vip`; `c2p_project_tracker` → `sale`) | cited in `06` | Declare them |
| ODOO-25 … 35 | Low | Mostly confirmed | CSRF disabled on session-authenticated POSTs (e-invoice submit/cancel — fix exists on an unmerged branch); internal error text returned; TTS credits spendable by any user; Odoo 19 API drift; HTML built by interpolation; three inert record rules; provider tokens and a tax-authority private key stored in plaintext DB fields; unbounded scraper loops; 6-digit client code without per-IP throttle; dead middleware; Enterprise module named in bundles | see `06_ODOO_INSTANCES_AUDIT.md` | — |

### B2. C2P Agency OS (`c2p-delivery-system/`)

Positive results: every SQL statement parameterised; subprocess calls are list-form without a shell; proposal body content is escaped; Stripe webhook is sound; no credentials in the tree or its history; console has no duplicate function names; gates default to "approval".

| ID | Sev | Status | Finding | Location | Fix |
|---|---|---|---|---|---|
| C2P-01 | **Critical/High** | Confirmed (code) | Auth opt-in and fail-open | `delivery_api/main.py:143-158`; `tenancy.py:28,37` | Refuse to start without an auth mode |
| C2P-02 | High | Confirmed | Stored Odoo key / GitHub token sent to caller-chosen host | `main.py:667-673,703,725-759,788-794`; `github.py:39-47,87` | Drop stored secret on any URL/repo change |
| C2P-03 | High | Confirmed | Token leaks in response and DB on git timeout; token in process argv | `github.py:58-63,87,106`; `main.py:803,2160` | Catch + scrub; `GIT_ASKPASS` |
| C2P-04 | High | Confirmed (write) / Suspected (code execution) | Path traversal via `subdir` | `github.py:100,108-109` | `_safe_join(work, subdir)` |
| C2P-05 | High | Confirmed (injection) / Suspected (file read) | Unescaped branding in rendered HTML/PDF | `proposal_render.py:45-52,79-105,220-273`; `main.py:2500` | Validate colours/logos; restricted URL fetcher |
| C2P-06 | High | Confirmed, multi-tenant mode only | Odoo client cached by db name only; tenants fall back to the operator's env credentials | `odoo.py:148-152`; `main.py:87-115` | Key cache by tenant; no env fallback |
| C2P-07 | High | Confirmed, multi-tenant mode only | Caller picks own edition; suspended tenants keep access; no signup throttle | `main.py:2545,2674-2683` | Server-side edition; enforce status |
| C2P-08 | Med-High | Confirmed sinks | Console `esc()` does not escape quotes yet is used in attributes and inline handlers; token in `localStorage`; CDN scripts without SRI; no CSP | `console/c2p-delivery-console.html:1080` and 12 call sites | Escape quotes; SRI; CSP; httpOnly cookie |
| C2P-09 | Medium | Confirmed | SSRF — no scheme/host/private-range checks on any user-supplied URL | `main.py:716-769`; `odoo.py:140` | Allow-list or block private ranges |
| C2P-10 | Medium | Confirmed | No login rate limit; username timing oracle; plaintext admin password option; 7-day non-revocable JWT | `main.py:2560-2596`; `tenancy.py:39,76-118` | nginx `limit_req`; shorter TTL |
| C2P-11 | Medium | Mostly confirmed | Prompt-injection-to-action gaps: auto-sent replies decided by the model; ungated Odoo write-back per stage; config `write` with empty domain updates every record; approval payload replaceable; non-atomic approval executes twice under concurrency | `main.py:2187-2404`; `sync.py:21-63` | Field allow-lists; atomic state change; untrusted-content guardrails in prompts |
| C2P-12 | Medium | Confirmed | `cryptography` missing from requirements → saving a connection 500s → operators pushed toward the plaintext flag; decrypt failure silently falls back to env/default credentials | `requirements.txt`; `tenancy.py:128-167` | Add dependency; fail loudly |
| C2P-13 | Medium | Confirmed (code) | Hardcoded default Odoo URL, user and well-known default password used when nothing is configured | `odoo.py:21-23` | No defaults |
| C2P-14 | Medium | Confirmed | No backup of the SQLite stores | `deploy/`, `update.sh` | See `09` |
| C2P-15 | Medium | Suspected | Service likely runs as root, no unit hardening | `deploy/setup.sh:21` | Dedicated user |
| C2P-16 | Medium | Confirmed | nginx template: port 80 until certbot; no HSTS/CSP/limits; body limit smaller than allowed logo | `deploy/nginx-delivery.conf.tmpl` | Shared hardening snippet |
| C2P-17 | Medium | Confirmed | Production details in a public repo | see A3 | Private repo |
| C2P-18 … 25 | Low | Confirmed/Suspected | No tests in CI; CORS `*`; exception text reflected; prompts and outputs kept forever; SMTP STARTTLS without certificate verification; previews likely 401 under auth; documented demo password; caller-supplied Stripe return URLs | — | — |

### B3. Other applications and scripts

| ID | Sev | Status | Finding | Location |
|---|---|---|---|---|
| APP-01, -02 | **Critical** (if deployed) | Confirmed in code | Unauthenticated cross-tenant finance read and knowledge-base write/delete | `platform/zaki/backend/main.py:179-317` |
| APP-03 | High | Confirmed | Faizy installer exposes a fresh Odoo on plain HTTP :8080 with the default administrator login until changed | `faizy/odoo/deploy/install.sh:293-370` |
| APP-04 | High | Confirmed (by design) | WordPress installer leaves `/wp-admin/install.php` unclaimed and public — first visitor becomes admin with PHP execution on the shared host | `wordpress-sites/deploy/setup-lemp.sh:16-17,298-308` |
| APP-05 | High | Confirmed | SSRF in `zaki-ai` (`/erp/connect` to any URL; error text as a port-scan oracle; open registration proxy) | `apps/zaki-ai/server.js:90-136,196-330` |
| APP-06, -07, -08 | High | Sinks confirmed | Stored XSS in the portal admin console, the ERP SPA (57 `innerHTML` sinks, no escaping) and both ZAKI SPAs; tokens — and in ZAKI, the user's own Anthropic and ElevenLabs keys — in `localStorage` | `apps/portal/admin.html:290-378`; `apps/erp/static/index.html`; `apps/zaki-ai/public/index.html:3382-3410` |
| APP-09, -10 | High | Confirmed | Application PostgreSQL role created `SUPERUSER`; one Odoo admin login for all tenant DBs | `platform/ops/install/00-foundation.sh:71`; `platform/zaki/backend/main.py:36-79` |
| APP-11 | High | Confirmed | Literal DB password and fallback signing secret in scripts, then written into a world-readable unit file | `apps/platform/setup_master_admin.sh:141`; `apps/erp/deploy.sh:30-31,97-98` |
| APP-12 | High | Link confirmed; exposure suspected | Public pages link to `http://<IP>:8069/` | `apps/website/{about,demo,docs,solutions,blog,platform}.html` |
| APP-13 | High | Suspected | DB manager not blocked in any vhost; one deploy script writes `dbfilter = .*` | `apps/addons/deploy.sh:54-57`; nginx files |
| APP-14 … 29 | Medium | Confirmed | Unauthenticated TTS proxy; CORS `*` with credentials; services running as root; unencrypted same-host dumps; no rate limits on `zaki-ai`; pass-through proxy to the auth server; browser-held provider keys; kiosk body measurements sent with name and phone while the screen says "nothing is sent" (APP-22); client one-time code echoed in demo mode (APP-23); LEMP installer hardening gaps; an `rsync --delete` that can remove the repo checkout (APP-25); a cutover script that deletes then aborts (APP-26); nginx header and TLS gaps; scraper ignores robots.txt and harvests contact data (APP-29) | see reviewer table in `13` |
| APP-30 … 39 | Low | Mixed | Third-party voice-agent ids on public pages; dependency age; scraper code defects; owner's name/email hardcoded; nullable tenant keys in the platform schema; a contact form that discards leads | — |

WordPress themes themselves are clean (guards, no request-variable use, no AJAX handlers).

---

## Part C — Infrastructure security

| Area | Finding | Status |
|---|---|---|
| Network exposure | Application ports open to the internet (8071 recorded; 8069 implied; 8080 opened by the Faizy installer) | Reported — verify with V-02 |
| Firewall | `ufw` managed by hand; rules lost and re-added during an update; no provider-level firewall recorded | Reported |
| Reverse proxy | Competing vhost definitions; no shared security headers; `add_header` in nested locations cancels server-level headers; no rate limits; no `/web/database` block | Confirmed in repo |
| TLS | certbot per host. Protocol/cipher settings, HSTS and expiry dates **Not Verified** except `pharma.` (expires 2027-02-16) | Mixed |
| SSH | Root is used for every documented procedure. Key-only login, `PermitRootLogin`, and who holds keys are **Not Verified** | NV |
| Database ports | No evidence 5432/3306 are exposed. **Not Verified** | NV |
| Containers | One compose project, ports bound to loopback, addons mounted read-only. Sound | Confirmed in repo |
| File permissions | `.env` for the Agency OS created 600; SQLite stores have default permissions; several scripts write secrets into unit files (world-readable); Faizy credentials file is root-only | Confirmed in repo |
| Service accounts | Five Odoo services share OS user `odoo`; two FastAPI services and pm2 apps run as root by template | Confirmed in repo / Reported |
| Administrative access | One GitHub account performs all pushes and merges; Hostinger and registrar access holders unknown | NV |
| Secrets management | Plaintext files on the host; one DB password copied across instance configs; no inventory, no rotation record; provider tokens stored unencrypted in Odoo fields | Confirmed in repo / Reported |
| Logging and monitoring | Local logs only; no alerting of any kind | Confirmed absent in repo |
| Patching | Odoo from the nightly package repository (version moves on `apt upgrade`); one installer runs unattended `apt-get upgrade -y` on the shared host; no patch calendar | Confirmed in repo / Reported |
| Third-party code | Cybrosys accounting kit installed for the client; two issues found in it during the Pharma review and hardened **there only** (F-15) | Reported |

## Part D — Credential exposure register (no values)

| # | Location | Category | Exposure | Severity | Remediation |
|---|---|---|---|---|---|
| 1 | `apps/platform/setup_master_admin.sh:141` | Database password literal | Public repo | High | Remove; rotate if ever used |
| 2 | `apps/erp/deploy.sh:30-31` | Fallback DB password and signing secret | Public repo; written to unit file | High | Require env; rotate if ever used |
| 3 | `c2p-delivery-system/delivery_api/odoo.py:21-23` | Default Odoo user + well-known default password | Public repo; used as silent fallback | Medium | Remove defaults |
| 4 | `.env.example:7,13,15` | Weak placeholder defaults (`admin`/`odoo` class) | Public repo; copy-paste risk | Low | Replace with `CHANGE-ME` markers |
| 5 | `c2p-delivery-system/scripts/provision_demo_db.py:1888`; `docs/08-enquiry-to-cash-demo.md` | Documented demo role password | Public repo | Low (demo DBs) | Argument, not constant |
| 6 | Server: `/etc/odoo*.conf` | DB password (shared), master passwords | Readable by OS user `odoo` across tenants | High | Per-instance roles and file ownership |
| 7 | Server: a reachable Odoo instance | Default-strength administrator login | Internet-facing (Reported) | **Critical** | Change now (batch 2A) |
| 8 | Odoo DB fields (`mumtaz_core`, `mumtaz_lead_nurture`, `mumtaz_einvoicing`, `mumtaz_tenant_manager`) | AI/TTS keys, WhatsApp/Twilio tokens, tax-authority private key, tenant admin password | Plaintext at rest; in every dump | Medium | Field groups; encrypt or move to env |
| 9 | GitHub Actions secrets | Production SSH key, host, user | Used by workflows that currently cannot run | Medium | Restrict key; environment reviewers |
| 10 | Browser `localStorage` (ZAKI, portal, ERP SPA, console) | Session tokens; user's own provider API keys (ZAKI) | Readable by any script on the page | Medium–High | httpOnly cookies; no keys in browser |
| 11 | Git history (all branches) | — | Pattern scan of 1,089 commits found no live-format provider key, private key or token | — | Re-scan with a dedicated tool after going private |

**No credential has been rotated or revoked.** Rotation touches running services and is scheduled in batches 2A/2D and Phase 4.

## Part E — Dependencies

| Component | State |
|---|---|
| Odoo | 19.0 Community, nightly package (build 20260719 recorded) — current major; pin the package version so upgrades are deliberate |
| C2P Agency OS (Python) | Lower-bound pins only, no lockfile; `cryptography` missing; pip-audit passes on whatever is latest |
| `apps/zaki-ai` (Node) | Express 4.22, Anthropic SDK 0.37 (old); `npm audit` job passes in CI |
| `apps/jawhar-web` | Vite 5.4.11, React 18.3, vitest 2.1.8 — several have later patch releases with security fixes (mostly dev-server); CI installs with `--no-audit` |
| Console CDN scripts | pdf.js 3.11.174 (predates a 2024 advisory fixed in 4.2), jszip 3.10.1; no SRI |
| Platform ZAKI backend, scraper | Fully unpinned |
| WordPress | Latest at install time; no update policy |

No package was upgraded. Upgrade recommendations are in the backlog (A-15) and each needs a compatibility check first.

## Part F — What was not tested

Authentication strength, session handling at runtime, real TLS configuration, actual port exposure, live nginx behaviour, real module install sets, and every "Suspected" item. Active testing of any of these requires separate written authorisation and a defined scope.
