# 06 — Odoo Instances Audit

Instance facts are **R-doc** (owner-run output recorded in repository documents, 2026-10-05 → 2026-11-20) unless marked; code facts are **V-repo**. No Odoo instance was contacted. Nothing was upgraded, installed, migrated or restarted.

## 1. Instances

| Instance | Unit / runtime | Version | Edition | Database | `dbfilter` | `db_name` | `list_db` | Bind | Proxy | Workers | Addons path | Filestore | Backup |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C2P CRM | `odoo4` — native package | 19.0-20260719 | Community | `Mumtaz_C2P` | NV | NV | NV | :8075, interface NV | nginx `core2plus.com` | NV | From `/etc/odoo4.conf`; **`/opt/mumtaz/addons` is not on it**; includes checkouts on a feature branch | under the `odoo` data dir, `filestore/Mumtaz_C2P` | none found |
| Main / ERP front | `odoo` — native package | 19.0-20260719 | Community | pinned to `Mumtaz_C2P` | `^Mumtaz` | `Mumtaz_C2P` | False | :8069 / :8072 | nginx (`erp.`/`admin.` — to confirm) | NV | `/etc/odoo/odoo.conf` | shared `odoo` data dir | none found |
| Platform ERP | `odoo2` — native package | 19.0 | Community | `Mumtaz_ERP` | set | **absent** | NV | :8070 | NV | NV | `/etc/odoo2.conf` | shared | none found |
| IG2 (client) | `odoo3` — native package | 19.0 | Community | `Mumtaz_IG2` | `^Mumtaz_IG2$` | **absent** | False | **`0.0.0.0:8071`** | **none — direct HTTP**; `ig2.` vhost has a dead websocket upstream (:8074) | NV | `/etc/odoo3.conf` | shared | none found |
| Faizy | `faizy-odoo` — source checkout + venv, user `faizy` | 19.0 branch head | Community | `faizy_prod` | `^faizy_prod$` | `faizy_prod` | False | `127.0.0.1:8079` / `:8078` | nginx `myfaizy.com` | per doc | `/opt/faizy/odoo/addons,/opt/faizy/src/faizy/odoo/addons` | `/opt/faizy/data` | NV |
| Pharma staging | `odoo-pharma` — native package | 19.0-20260719 | Community | `mumtaz_pharma` | `^mumtaz_%d$` | `mumtaz_pharma` | NV | `127.0.0.1:8076` / `:8077` | nginx `pharma.` + cert | 2 | staging checkout + `/opt/thirdparty` | shared | on-demand dumps, same disk |
| Jewel staging | Docker `odoo:19` | 19 | Community | `jewel_demo` | — | — | **True** (deliberate) | `127.0.0.1:8072` / `:8073` | nginx `jewel.`, allow-list or basic auth on Odoo prefixes | 2 | `addons/` mounted read-only | Docker volume | scripted |

Enterprise indicators: none. No manifest depends on an Enterprise module; one bundle data file *names* `account_accountant`, which the provisioning code silently skips when absent (ODOO-35).

### Instance-level risks

| # | Risk | Instance | Status |
|---|---|---|---|
| I-1 | Client database reachable on a public port over plain HTTP | IG2 | Reported |
| I-2 | Two servers bound to one database (`odoo` :8069 and `odoo4` :8075 → `Mumtaz_C2P`) with potentially different addons paths — duplicate crons, registry mismatches | C2P | Suspected — verify |
| I-3 | No `db_name` → cron workers open every database on the server | `odoo2`, `odoo3` | Reported (observed) |
| I-4 | `dbfilter = ^Mumtaz` is a prefix match covering four databases | `odoo` | Reported |
| I-5 | `erp.` vhost sends `/longpolling` to :8073 — the Jewel container's port. Odoo 19 uses `/websocket`; either way live-update traffic for the ERP is going to the wrong instance or nowhere | nginx | Reported |
| I-6 | Production addons come from a feature branch; duplicate checkouts shadow each other; one installed module (`c2p_master_agent`) has no source on any path; two more were untracked on the server | C2P | Reported |
| I-7 | 25 server actions on `crm.lead` hold business rules in the database only | C2P | Reported |
| I-8 | No staging copy; changes go straight to a client's live ledger | IG2 | Reported |
| I-9 | Third-party accounting kit installed without the hardening written for Pharma | IG2 | Reported |
| I-10 | Odoo installed from the **nightly** package repository — an `apt upgrade` moves every native instance to a new build at once, with no test | all native | Reported |
| I-11 | All native instances except Faizy share OS user `odoo` and one data directory | native | Reported |
| I-12 | No filestore backup anywhere; attachments (vouchers, invoices, ID documents) exist in one place only | all | Confirmed absent in repo |
| I-13 | Master password (`admin_passwd`) strength unknown; a default-strength administrator login is reported on one reachable instance | NV which | Reported |
| I-14 | `/web/database/*` not denied at the proxy on any vhost in the repository | all | Confirmed in repo |

## 2. Custom modules on `main`

53 modules: 37 platform (`mumtaz_*`), 14 jewellery (`mumtaz_jewellery*`), 2 C2P (`c2p_*`). Plus 2 Faizy modules under `faizy/`. All declare `19.0.x`, LGPL-3, installable. No dependency cycle. No core file is patched.

### 2.1 Quality snapshot

| Measure | Result |
|---|---|
| Models with an ACL row | 126 of 126 non-abstract |
| Models with a record rule | 35 of 100 that could need one |
| Modules with tests | 14 of 55 (`c2p_project_tracker` + 13 jewellery) |
| Tests executed by CI | Jewellery only (242 tests, green). PR #172 adds fresh-install CI for the other 39 and found four that could not install on a clean database |
| Raw SQL | 3 statements, all parameterised |
| `sudo()` call sites | ~196, concentrated in `mumtaz_app_portal`, `mumtaz_portal_routing`, `mumtaz_control_plane`, `mumtaz_billing_stripe` |
| Dangerous primitives (`eval`, `exec`, `pickle`, shell) | none |

The jewellery family is the quality bar in this repository: tested, CI-gated, scoped public endpoints, hashed tokens. The platform family has sound patterns but almost no executed evidence.

### 2.2 Module groups and what to do with each

| Group | Modules | Assessment | Recommendation |
|---|---|---|---|
| Tenancy and control plane | `mumtaz_tenant_manager`, `mumtaz_control_plane`, `mumtaz_subdomain_routing`, `mumtaz_sso`, `mumtaz_org_config`, `mumtaz_organization`, `mumtaz_sme_profile`, `mumtaz_onboarding` | Two tenancy models at once (database-per-tenant **and** company-per-organisation), four overlapping registries (`mumtaz.tenant`, `mumtaz.org`, `mumtaz.organization`, `mumtaz.sme.profile`); contains the Critical SSO flaw and the RPC group-rewrite flaw; none tested | **Repair before any further tenant is provisioned.** Pick one tenancy model (decision record) |
| Portals | `mumtaz_portal` (empty), `mumtaz_app_portal`, `mumtaz_portal_routing`, `mumtaz_customer_portal`, `mumtaz_vendor_portal` | Two modules carry near-identical query blocks under `sudo()`; one is a bare manifest | **Consolidate** to one portal module; remove `sudo()` reads |
| APIs | `mumtaz_api`, `mumtaz_api_gateway` | Four HTTP surfaces with four auth schemes across the repo; the gateway's key lookup cannot succeed | **Consolidate or retire** the gateway; throttle the anonymous lead API |
| Billing | `mumtaz_billing_stripe` | Webhook verification is sound; error handling and amount checks are not; RPC-callable Stripe methods | **Repair** before taking real payments |
| E-invoicing | `mumtaz_einvoicing` | 2,200 lines, three jurisdictions, no tests; a cron that fabricates "rejected" status; sandbox that fabricates "accepted" | **Repair + test** — regulatory exposure. Do not rely on it for filings until verified |
| Finance / CFO | `mumtaz_zaki`, `mumtaz_voice`, `mumtaz_ai`, `mumtaz_cfo_base`, `_ingestion`, `_transactions`, `_toolkit`, `mumtaz_financial_reports`, `mumtaz_ceo_dashboard` | Two parallel CFO stacks; cross-company leak in the snapshot; reports module in production use for the client | **Repair** the leak; **review** which stack survives |
| Growth | `mumtaz_lead_scraper`, `mumtaz_lead_nurture`, `mumtaz_marketplace`, `mumtaz_media_buying`, `mumtaz_crm_starter` | SSRF and unbounded loops in the scraper; cross-company write on listings; messaging tokens in plaintext fields | **Repair**; confirm lawful basis for scraped contacts (D-13) |
| Foundation / look | `mumtaz_core`, `mumtaz_base`, `mumtaz_branding`, `mumtaz_theme`, `mumtaz_website`, `mumtaz_super_toolkit` | Thin; `mumtaz_theme` injects Google Fonts into every backend page (third-party request from an ERP) | **Retain**; self-host fonts |
| Jewellery | 14 modules | Good. One conditional High: the demo module must never be installed where the client app is reachable | **Retain** |
| C2P | `c2p_project_tracker`, `c2p_command_center` | Tracker is tested (57 tests) but missed a `sale` dependency; three more C2P modules live only on a branch or only on the server | **Repair** — bring all C2P code into `main` |

Stub or near-empty modules that can be retired after confirming they are not installed anywhere: `mumtaz_portal`, `mumtaz_cfo_toolkit`, `mumtaz_super_toolkit` (meta-installers), and possibly `mumtaz_api_gateway`.

### 2.3 Public and unauthenticated endpoints (summary)

| Surface | Auth | Verdict |
|---|---|---|
| `/mumtaz/sso` | none | **Critical** (ODOO-01, -11) |
| `/mumtaz/platform/push-credentials` | none + bearer | Medium (ODOO-23) |
| `/mumtaz/stripe/webhook` | public + signature | Sound; robustness gaps (ODOO-18) |
| `/api/mumtaz/v1/{demo,contact}` | public, CORS `*` | Medium — unlimited CRM writes (ODOO-09) |
| `/mumtaz/org/{check,signup}`, `/org/<slug>/join`, `/org/register` | public | Medium — unthrottled record creation (ODOO-10) |
| `/api/v1/*` gateway pings | public | Low — log growth (ODOO-20) |
| `/jawhar/public/kiosk/*`, `/jawhar/public/tray/<token>`, `/jawhar/client/*` | public, scoped | Sound, except the demo-mode code echo (ODOO-07) |
| `/jawhar/v1/*` (97 routes) | session, enforced in a decorator | Sound; CSRF relies on SameSite only (ODOO-25) |
| Faizy `/start/submit`, `/join/submit` | public, CSRF on | Medium — unthrottled, attaches to existing partners (ODOO-17) |
| `/zaki/api/snapshot`, `/app*`, `/vendor/*` | user | **High** — `sudo()` behind a weak gate (ODOO-04, -05, -15) |

The full route table with file and line is in the Odoo reviewer's report, reproduced in `13_REMEDIATION_BACKLOG.md` references.

### 2.4 Customisations that override core behaviour

| Override | Module | Risk |
|---|---|---|
| `odoo.http.db_filter` replaced process-wide at `post_load` | `mumtaz_subdomain_routing` | Medium — affects every database served by that process; env-gated |
| `Home._login_redirect` | `mumtaz_portal_routing` | Medium — may skip the 2FA step (Suspected) |
| Session established by direct assignment | `mumtaz_sso` | Critical in combination with the shared secret |
| `account.move.action_post` does network I/O and swallows errors | `mumtaz_einvoicing` | Medium — posting an invoice can hang on a tax-authority outage |
| Global `ir.rule` on `res.partner` + read-logging overrides (`web_read`, `search_fetch`, `export_data`) | `mumtaz_jewellery_vip` | Low–Medium — performance on every partner read; affects every app in that database |
| `mail.message` create/write override for all messages | `mumtaz_lead_scraper` | Low |
| Adds `base.user_admin` to the manager group on every upgrade | `faizy_core` | Low |

### 2.5 Scheduled jobs (23 defined in code)

Jobs that reach outside or change money/state:

| Job | Interval | Why it matters |
|---|---|---|
| Stripe: charge due subscriptions | daily | Real charges; retries failing cards daily without a cap |
| Subscription lifecycle evaluation | daily | Can suspend tenants in one batch |
| E-invoice: sync submission status | 4 h | Marks invoices rejected without asking the authority |
| E-invoice: retry rejected | daily | Resubmits those, all companies, no batch limit |
| Process provisioning queue | 5 min | Creates databases in-process when enabled by env |
| ZAKI morning briefings | hourly | Emails all-company figures to each company |
| Sync credentials from platform | daily | Pulls API keys from a user-configurable URL |
| Lead nurture: run sequence steps | hourly (inactive by default) | Email and WhatsApp to leads |
| Lead scraper: run scheduled sources | daily (inactive by default) | Arbitrary fetches; unbounded loops |
| Faizy: recurring invoicing, recurring orders, document reminders, WhatsApp queue | daily / 15 min | The WhatsApp provider is a stub, so nothing is actually sent |

**Plus whatever lives only in the databases:** at least the C2P "BD engine" and the daily lead-archive action. With `odoo2`/`odoo3` lacking `db_name`, any of these can be executed by a process that does not have the module's code. A restored copy of `Mumtaz_C2P` will start emailing real contacts unless neutralised first.

### 2.6 External integrations

Stripe; ZATCA (KSA) and FBR (Pakistan) e-invoicing gateways; OpenAI, Anthropic and ElevenLabs; WhatsApp Cloud API and Twilio; the platform control panel at `app.mumtaz.digital`; arbitrary scrape targets and rate feeds; Google Fonts on every backend page. Keys for most of these are stored in plaintext database fields (ODOO-31) and therefore in every dump.

## 3. Upgrade and change risk

| Risk | Detail |
|---|---|
| Uncontrolled platform upgrades | Nightly package: pin `odoo` with `apt-mark hold`, upgrade deliberately after a staging rehearsal |
| Odoo 19 API drift already present | `_sql_constraints`, `read_group`, `name_get`, `groups_id` on actions, `product_uom`, `partner.mobile` — some uniqueness constraints may not be enforced today (ODOO-28) |
| Module upgrade on production without rehearsal | Standard practice here for C2P/ERP/IG2; the Pharma kit shows the safe pattern (dump → upgrade → verify → rollback command) |
| Uninstalling to "undo" | Drops data; the tracker's own install guide correctly prefers restoring a dump |
| Demo data in production databases | `mumtaz_jewellery_demo` flips a security-relevant parameter; `seed_demo.py` in `mumtaz_media_buying` targets the client database by name |

## 4. Read-only checks to run per instance (with approval)

```bash
# what each unit really runs (passwords masked)
for u in odoo odoo2 odoo3 odoo4 odoo-pharma faizy-odoo; do
  systemctl cat $u.service | grep -E 'ExecStart|User=|Environment'
done
sudo sed -E 's/((admin_passwd|db_password)\s*=\s*).*/\1***masked***/' /etc/odoo/odoo.conf /etc/odoo[0-9]*.conf /etc/odoo-pharma.conf
```

```sql
-- inside each Odoo database
SELECT name, latest_version FROM ir_module_module WHERE state='installed' ORDER BY 1;
SELECT cron_name, active, interval_number, interval_type, nextcall FROM ir_cron ORDER BY active DESC, 1;
SELECT key FROM ir_config_parameter WHERE key IN ('mumtaz.sso_secret','mumtaz_jewellery.client_code_echo','database.is_neutralized','web.base.url');  -- keys only
SELECT count(*) FROM ir_act_server;                       -- logic stored in data
SELECT count(*) FROM res_users WHERE active AND share = false;
```

The parameter query returns key names only — never select the `value` of `mumtaz.sso_secret`.
