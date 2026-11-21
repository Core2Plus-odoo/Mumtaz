# 01 — Environment Inventory

**Audit date:** 2026-11-21 · **Mode:** read-only · **Auditor access:** GitHub repository only

> **Handling:** this pack describes live weaknesses and the repository `Core2Plus-odoo/Mumtaz` is **public**. It was committed here on 2026-11-21 at the owner's explicit instruction, after the risk was explained (`15_DECISIONS_AND_APPROVALS.md`, decision D-01). That makes findings F-01 to F-03 more urgent, not less.

## 1. What this audit could and could not reach

| Asset | Access this session | Result |
|---|---|---|
| GitHub repo `Core2Plus-odoo/Mumtaz` (public) | Full clone, all 51 branches, 1,089 commits, Actions run metadata, open PRs | **Inspected** |
| VPS `187.77.128.199` (Hostinger, hostname `srv1446185`) | No SSH; no shell | **Not Verified** |
| Production websites (`*.mumtaz.digital`, `core2plus.com`, `myfaizy.com`) | Outbound requests refused by this session's network policy (HTTP 403 at the egress proxy) | **Not Verified** |
| PostgreSQL / MariaDB / SQLite databases | None | **Not Verified** |
| Hostinger hPanel / DNS | None (`.mcp.json` declares a Hostinger connector, but it is not connected here) | **Not Verified** |
| GitHub repo settings (branch protection, secrets list, collaborators) | Not queried / not exposed | **Not Verified** |

Nothing on any server, database, DNS zone or GitHub setting was changed. The only writes were a local `git fetch` of history and the files in this folder.

### Evidence labels used in every document

| Label | Meaning |
|---|---|
| **V-repo** | Verified by me in the repository this session (path given) |
| **V-gh** | Verified by me through the GitHub API this session |
| **R-doc** | Recorded in a repository document from commands the owner ran on the VPS and pasted back (date given). Credible, but **not re-verified** and may be stale |
| **INF** | Inferred from configuration or scripts; no direct observation |
| **NV** | Not verified — no access or no evidence |

The three most useful R-doc sources:

- `docs/pharma/DEPLOY_LOG.md` on branch `pharma-erp-v0.1` — VPS discovery of **2026-11-18**
- `docs/erp/00-current-system-audit.md` on branch `claude/resume-help-95ne9v` — IG2 instance, **2026-11-20**
- `c2p-delivery-system/docs/07-mumtaz-c2p-crm-findings.md` and `docs/05-build-log.md` on `main` — C2P CRM, **2026-10-05**

## 2. Repository

| Fact | Value | Evidence |
|---|---|---|
| Remote | `github.com/Core2Plus-odoo/Mumtaz` | V-repo |
| Visibility | **Public** | V-gh |
| Default branch | `main` | V-repo |
| History | 1,089 commits, 2026-03-01 → 2026-11-21 | V-repo |
| Branches | 51 remote (28 fully merged, 23 carrying unmerged work) | V-repo |
| Tags / releases | 0 | V-repo |
| Tracked files on `main` | 1,201 (527 `.py`, 233 `.xml`, 57 `.md`, 45 `.html`, 42 `.sh`, 36 `.php`) | V-repo |
| Working-tree size | 88 MB (31 MB of it is MediaPipe model binaries in `apps/jawhar-web/public/`) | V-repo |
| Open pull requests | 12 (oldest from 2026-07-11) | V-gh |
| Tracked `.env` / key / dump files | None (only `*.example` templates and three schema `.sql` files) | V-repo |

## 3. Projects identified

Fourteen distinct projects share this one repository. Several exist **only on unmerged branches**.

| ID | Project | Type | Source location | Lives on |
|---|---|---|---|---|
| P01 | **Mumtaz Platform** — multi-tenant SaaS shell (tenant manager, control plane, billing, portals, e-invoicing, CFO, marketplace) | Odoo 19 CE addons (37 `mumtaz_*` non-jewellery modules) | `addons/mumtaz_*` | `main` |
| P02 | **C2P CRM / internal ERP** (Core 2 Plus group's own system) | Odoo 19 CE + `c2p_*` addons | `addons/c2p_project_tracker`, `addons/c2p_command_center`; `c2p_pk_vouchers`, `c2p_proposal`, `c2p_appointment` | `main` + branch `claude/resume-help-95ne9v` |
| P03 | **IG2** — client accounting system (media agency, two companies in one database) | Odoo 19 CE, uses `c2p_pk_vouchers`, `mumtaz_financial_reports`, third-party `base_accounting_kit` | as P02 | branch `claude/resume-help-95ne9v` |
| P04 | **Faizy** — family-care service, separate product | Odoo 19 CE addons (`faizy_core`, `faizy_website`, `faizy_ai`) | `faizy/` | `main` (62 files) and branch `claude/repo-audit-faizy-instance-fck6o3` (far ahead) |
| P05 | **Jawhar / Mumtaz Jewel** — jewellery retail OS | Odoo 19 CE (14 `mumtaz_jewellery*` modules) + React/Vite SPA | `addons/mumtaz_jewellery*`, `apps/jawhar-web/`, `website/jewel/`, `deploy/jewel-staging/` | `main` |
| P06 | **Pharma ERP** — staging tenant with demo data | Odoo 19 CE (`pharma_*` modules) + third-party accounting kit | `addons/pharma_*`, `deploy/pharma-staging/` | branches `pharma-*` only |
| P07 | **C2P Agency OS** — AI delivery console | FastAPI + SQLite + single-file HTML console | `c2p-delivery-system/` | `main` |
| P08 | **ZAKI AI CFO** | Three competing implementations: Node/Express (`apps/zaki-ai`), static page (`apps/zaki`), FastAPI (`platform/zaki`) | `apps/zaki-ai/`, `apps/zaki/`, `platform/zaki/` | `main` |
| P09 | **Platform API ("zaki-server") and "erp-server"** — auth + tenant registry, SQLite | FastAPI | **Source deleted from `main`** in commit `48a2cf9` (PR #124); still referenced by nginx configs, scripts and docs | history only |
| P10 | **Customer portal, marketplace, marketing site** | Static HTML | `apps/portal/`, `apps/marketplace/`, `apps/website/` (+ duplicates `platform/marketing/`, `website/index.html`) | `main` |
| P11 | **"Platform clean rebuild"** — control panel + PostgreSQL schema | FastAPI + PostgreSQL (`mumtaz_platform`) | `platform/` | `main` |
| P12 | **WordPress content sites** (two AdSense sites) | PHP themes + LEMP installer (MariaDB) | `wordpress-sites/` | `main` |
| P13 | **Pakistan trade portal scraper** | Python | `tools/scrapers/pakistan_trade_portal/` | `main` |
| P14 | **Legacy Docker "production" stack** (Odoo 19 + Postgres 15 via compose) | Docker Compose | `Dockerfile`, `docker-compose*.yml`, `scripts/` | `main` |

Other unmerged work worth knowing about: `c2p/odoo` + `c2p_agents` (PR #131), a WordPress affiliate plugin and server-hardening script (PR #134), an unmerged security fix for e-invoicing CSRF (branch `security/h1-h2-…`), and a single-file bank-document replica (PR #127 — see finding F-19).

## 4. Runtime services on the VPS

Source: R-doc (2026-11-18 and 2026-11-20) unless marked. **None re-verified.**

| Service | Runtime | Port(s) | Config | Database | Domain |
|---|---|---|---|---|---|
| `odoo.service` | Native `/usr/bin/odoo` 19.0-20260719 | 8069 / 8072 | `/etc/odoo/odoo.conf` — `dbfilter = ^Mumtaz`, `db_name = Mumtaz_C2P`, `list_db = False` | `Mumtaz_C2P` (and can match any `Mumtaz*` DB) | `erp.mumtaz.digital`? (INF) |
| `odoo2.service` | Native Odoo 19 | 8070 | `/etc/odoo2.conf` — dbfilter set, **no `db_name`** | `Mumtaz_ERP` | NV |
| `odoo3.service` | Native Odoo 19 | 8071, bound to `0.0.0.0` | `/etc/odoo3.conf` — `dbfilter = ^Mumtaz_IG2$`, **no `db_name`** | `Mumtaz_IG2` | `ig2.mumtaz.digital` vhost exists; in practice used over `http://<IP>:8071` |
| `odoo4.service` | Native Odoo 19 | 8075 | `/etc/odoo4.conf` | `Mumtaz_C2P` | `core2plus.com` |
| `faizy-odoo.service` | Odoo 19 from source in a venv, user `faizy` | 8079 / 8078 (INF from docs) | `/opt/faizy/odoo.conf` | `faizy_prod` | `myfaizy.com` |
| `odoo-pharma.service` | Native Odoo 19 | 8076 / 8077 | `/etc/odoo-pharma.conf` — `dbfilter = ^mumtaz_%d$`, `db_name = mumtaz_pharma` | `mumtaz_pharma` | `pharma.mumtaz.digital` |
| Jewel staging | Docker Compose project `mumtaz-jewel-staging` (`odoo:19` + `postgres:16-alpine`) | 8072 / 8073 on loopback | `deploy/jewel-staging/odoo.rendered.conf` | `jewel_demo` (own Postgres container) | `jewel.mumtaz.digital` |
| C2P Agency OS API | uvicorn (systemd unit from `delivery-api.service.tmpl`) | 8800 on loopback | `c2p-delivery-system/delivery_api/.env` | SQLite `delivery.db` (+ `control.db`, per-tenant `.db`) | `delivery.mumtaz.digital` |
| `erp-server.service` | FastAPI | 8003 (INF) | `/opt/erp-server/.env` | — | **Crash-looping** (`activating (auto-restart)`); its source was deleted from the repo |
| `zaki-server` | FastAPI under pm2 or systemd | 8002 (INF) | `/opt/zaki-server/.env` | SQLite `/opt/zaki-server/users.db` | `app.` / `zaki.` / `marketplace.mumtaz.digital` `/api/` — **NV whether still running** |
| ZAKI AI (Node) | pm2 | 3000 (INF) | `apps/zaki-ai/ecosystem.config.js` | none of its own | `zaki.mumtaz.digital` — **NV** |
| nginx | System package | 80 / 443 | One vhost file per site in `sites-enabled`, certbot-managed TLS | — | all |
| PostgreSQL | System package, local | 5432 | — | shared by every native Odoo instance through one role `odoo` | — |
| WordPress ×2 | nginx + PHP-FPM + MariaDB | — | — | two MariaDB databases | `odditytrend.com`, `youngcraze.com` — **NV whether ever deployed** |

Two things stand out even before the risk review:

1. `odoo.service` (:8069) and `odoo4.service` (:8075) both name `Mumtaz_C2P`. Two Odoo servers on one database is a duplicate-instance risk (F-07).
2. The repository's own "production" deploy path (P14, Docker Compose) does not match anything recorded as running. Production is native systemd units configured by hand.

## 5. Master infrastructure inventory

Security risk is the audit's rating of the asset as documented, not of its business value. "Docs" refers to documentation that matches reality.

| ID | Project | Repo path | Domain | App type | Runtime status | Env | Hosting | DB engine | DB name | DB owner | Reverse proxy | Deploy method | Git status | Dependencies | Risk | Docs | Recommended action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P01 | Mumtaz Platform ERP | `addons/mumtaz_*` | `erp.` / `admin.` / `app.mumtaz.digital` | Odoo 19 CE | Running (R-doc) | Production | VPS, systemd `odoo2` | PostgreSQL (local) | `Mumtaz_ERP` | role `odoo` (shared) | nginx vhost | Manual `git pull` + `-u` | VPS checkout on branch `claude/resume-help-95ne9v`, not `main` | Stripe, ZATCA/FBR e-invoicing, Anthropic, zaki-server | **High** | Stale / contradictory | Repair + review |
| P02 | C2P CRM | `addons/c2p_*` | `core2plus.com` | Odoo 19 CE | Running (R-doc) | Production — 41 users, 41k leads | VPS, systemd `odoo4` (and `odoo`) | PostgreSQL (local) | `Mumtaz_C2P` | role `odoo` (shared) | nginx vhost | Manual | Code partly untracked; 25 server actions live only in the DB | Outbound email, BD engine crons | **Critical** | Partial | Repair |
| P03 | IG2 client accounting | branch `claude/resume-help-95ne9v` | `ig2.mumtaz.digital` / `IP:8071` | Odoo 19 CE | Running (R-doc) | **Production client data, no staging** | VPS, systemd `odoo3` | PostgreSQL (local) | `Mumtaz_IG2` | role `odoo` (shared) | Bypassed (direct port) | Manual | Code only on an unmerged branch | `base_accounting_kit` (third party) | **Critical** | Partial (branch only) | Repair |
| P04 | Faizy | `faizy/` | `myfaizy.com` | Odoo 19 CE | Running (R-doc) | Production | VPS, systemd `faizy-odoo`, own OS user | PostgreSQL (local) | `faizy_prod` | role `faizy` (own) | nginx vhost | Manual, documented | Production code on an unmerged branch 37 commits ahead | WhatsApp, payments (NV) | **High** | Good (on branch) | Retain, separate repo |
| P05 | Jawhar / Jewel | `addons/mumtaz_jewellery*`, `apps/jawhar-web`, `website/jewel` | `jewel.mumtaz.digital` | Odoo 19 CE + React SPA | Running (R-doc: ports in use) | Staging / demo, synthetic data | VPS, Docker Compose | PostgreSQL 16 (own container) | `jewel_demo` | own | nginx vhost, IP allow-list + basic auth | `deploy/jewel-staging/deploy.sh` | Clean, on `main`, CI green | MediaPipe (client-side) | **Medium** | Good | Retain |
| P06 | Pharma ERP | branches `pharma-*` | `pharma.mumtaz.digital` | Odoo 19 CE | Running (R-doc 2026-11-18) | Staging, neutralised, demo data | VPS, systemd `odoo-pharma` | PostgreSQL (local) | `mumtaz_pharma` | role `odoo` (shared) | nginx vhost, cert to 2027-02-16 | `deploy/pharma-staging/stage.sh` | Four unmerged branches | Third-party Cybrosys kit | **Medium** | Good (on branch) | Retain, separate repo |
| P07 | C2P Agency OS | `c2p-delivery-system/` | `delivery.mumtaz.digital` | FastAPI + SQLite | Running (INF from CLAUDE.md) | Production | VPS, systemd + nginx | SQLite | `delivery.db`, `control.db` | app | nginx vhost | `deploy/update.sh` | On `main` | Anthropic/OpenAI-compatible LLM, GitHub token, Odoo XML-RPC, Stripe | **High** | Good | Retain, repair |
| P08 | ZAKI AI CFO | `apps/zaki-ai`, `apps/zaki`, `platform/zaki` | `zaki.mumtaz.digital` | Node / static / FastAPI | Unknown | Unknown | VPS | none / SQLite | — | — | Three conflicting vhost definitions (ports 3000, 8001, 8002) | pm2 or systemd | On `main` | Anthropic, ElevenLabs, Odoo | **High** | Contradictory | Consolidate |
| P09 | zaki-server / erp-server | deleted (`48a2cf9`) | `/api/` under `app.`, `zaki.`, `marketplace.` | FastAPI | `erp-server` crash-looping; `zaki-server` unknown | Production (if running) | VPS | SQLite | `/opt/zaki-server/users.db` | app | nginx | None — source no longer in the repo | **Orphaned** | Odoo XML-RPC with admin credentials, Stripe, SMTP | **High** | Wrong | Review → retire or restore |
| P10 | Portal / marketplace / marketing | `apps/portal`, `apps/marketplace`, `apps/website` | `app.`, `marketplace.`, `mumtaz.digital` | Static HTML | Unknown | Production | VPS, `/var/www/*` | — | — | — | nginx | `rsync` / `cp` scripts | On `main`, untouched since June | zaki-server API | **Medium** | Stale | Review |
| P11 | Platform clean rebuild | `platform/` | intended to replace P08–P10 | FastAPI + PostgreSQL | Unknown; database exists (R-doc) | Unknown | VPS | PostgreSQL | `mumtaz_platform` | NV | planned | `platform/ops/install/*.sh` | On `main`, untouched since July | — | **Medium** | Plan only | Review → decide |
| P12 | WordPress sites | `wordpress-sites/` | `odditytrend.com`, `youngcraze.com` | WordPress | Unknown | Unknown | "shared Hostinger VPS" per README | MariaDB | two databases | per-site user | nginx | `setup-lemp.sh` | On `main` | AdSense | **Medium** | Fair | Review, separate repo |
| P13 | Trade portal scraper | `tools/scrapers/` | — | Python | Not a service | Dev tool | wherever run | — | writes to an Odoo DB | — | — | manual | On `main` | target website, Odoo XML-RPC | **Low** | Fair | Review |
| P14 | Legacy Docker stack | root `Dockerfile`, `docker-compose*.yml`, `scripts/` | — | Docker Compose | **Not running** (no evidence it ever ran) | — | — | PostgreSQL 15 | `mumtaz` | — | — | GitHub Actions (never succeeded) | On `main` | — | **Medium** (misleads operators) | Wrong | Retire after approval |

## 6. Databases named anywhere in the evidence

| Database | Engine | Purpose | Status | Evidence |
|---|---|---|---|---|
| `Mumtaz_C2P` | PostgreSQL | C2P CRM — production, 41 users | Confirmed active | R-doc 2026-10-05 |
| `Mumtaz_ERP` | PostgreSQL | Platform ERP / tenant registry | Likely active | R-doc 2026-11-18 |
| `Mumtaz_IG2` | PostgreSQL | Client accounting (two companies) | Confirmed active | R-doc 2026-11-20 |
| `faizy_prod` | PostgreSQL | Faizy production | Confirmed active | R-doc |
| `mumtaz_pharma` | PostgreSQL | Pharma staging, demo data | Confirmed active | R-doc 2026-11-18 |
| `jewel_demo` | PostgreSQL 16 (Docker) | Jewel demo, synthetic data | Likely active | V-repo + R-doc |
| `mumtaz_platform` | PostgreSQL | Platform rebuild control DB | Unknown ownership | R-doc 2026-10-05 |
| `mumtaz_erp` (lower case) | PostgreSQL | Unknown — name collides with `Mumtaz_ERP` | Potentially unused | R-doc 2026-10-05 |
| `IG2` | PostgreSQL | Unknown — predecessor of `Mumtaz_IG2`? | Potentially unused | R-doc 2026-10-05 |
| `Mumtaz_C2P_staging` | PostgreSQL | Copy of the C2P CRM, owned by `postgres` | Potentially unused; **contains real lead data** | R-doc 2026-10-05 |
| `scratch_pre` | PostgreSQL | Unknown; described as "dead" | Potentially unused | R-doc 2026-11-20 |
| `Mumtaz_C2P_test`, `Mumtaz_Demo_E2C`, `mumtaz_pharma_test` | PostgreSQL | Throwaway test/demo DBs created by documented procedures | Unknown whether present | V-repo (procedures) |
| `delivery.db`, `control.db`, `tenants/*.db` | SQLite | C2P Agency OS store | Confirmed active (INF) | V-repo |
| `/opt/zaki-server/users.db` | SQLite | Platform users + tenants registry | Unknown | V-repo (scripts) |
| two WordPress DBs | MariaDB | Content sites | Unknown | V-repo (installer) |

## 7. Domains and certificates

| Domain | Points to | TLS | Evidence |
|---|---|---|---|
| `mumtaz.digital`, `www.` | VPS | certbot per-host | INF; one note dated 2026-11-20 says the domain "lapsed" — see F-10 |
| `app.`, `erp.`, `admin.`, `zaki.`, `marketplace.`, `api.` | VPS | certbot | INF from nginx configs in repo |
| `delivery.mumtaz.digital` | VPS | certbot | INF (CLAUDE.md) |
| `jewel.mumtaz.digital` | VPS | certbot | INF |
| `pharma.mumtaz.digital` | VPS | Let's Encrypt, **expires 2027-02-16**, auto-renew scheduled | R-doc 2026-11-18 |
| `ig2.mumtaz.digital` | VPS vhost exists; `/websocket` proxied to a port where nothing listens | Unknown | R-doc 2026-11-18 |
| `core2plus.com`, `www.` | VPS, `odoo4` | Unknown | INF |
| `myfaizy.com` | VPS, `faizy-odoo` | Unknown | INF (branch docs) |
| `odditytrend.com`, `youngcraze.com` | Intended: VPS | Unknown | INF |
| `mumtaz.io`, `admin.mumtaz.io`, `*.mumtaz.io` | Only in an old nginx template | — | V-repo — likely never live |

DNS for `mumtaz.digital` is hosted at Hostinger (R-doc). Certificate expiry for every host except `pharma` is **Not Verified**.

## 8. CI/CD workflows (V-gh)

| Workflow | Trigger | State on `main` |
|---|---|---|
| `ci.yml` (Mumtaz CI) | every push | **Failing** — flake8 job and TruffleHog job fail |
| `test.yml` | push/PR to `main`, `develop` | **Invalid workflow file** — fails at startup on every push |
| `deploy-staging.yml` | push to `develop` (branch does not exist) | **Invalid workflow file** |
| `deploy-production.yml` | manual | **Invalid workflow file** — has never deployed |
| `backup.yml` | nightly 02:00 UTC + manual | **Invalid workflow file** — 920 runs, all failures, **no backup has ever run from it** |
| `jewel-odoo-tests.yml` | changes under jewellery addons | Passing |
| `jawhar-web.yml` | changes under `apps/jawhar-web` | Passing |
| `faizy-ci.yml` | changes under `faizy/` | Not checked this session |

The four invalid workflows share one defect (`secrets.*` used inside an `if:` expression). PR #168 (`fix/workflow-startup-failure`), open since 2026-11-19, fixes it.

## 9. Backups found

| Scope | Mechanism | Verified working? |
|---|---|---|
| Legacy Docker DB `mumtaz` | `scripts/backup.sh` via `backup.yml` | **No** — workflow invalid; target stack not running |
| Jewel demo | `deploy/jewel-staging/backup.sh` (dump, 14-day retention, restore drill) | NV whether the cron was installed |
| Pharma staging | `stage.sh backup` — dumps taken 2026-11-18 into `/var/local/pharma-staging/backups/` | R-doc: files existed that day; on the same disk |
| `Mumtaz_C2P`, `Mumtaz_ERP`, `Mumtaz_IG2`, `faizy_prod` | **None found** | — |
| Odoo filestores | **None found** | — |
| SQLite stores (`delivery.db`, `users.db`) | **None found** | — |
| Off-site copy of anything | **None found** | — |

Full detail in `09_BACKUP_AND_RECOVERY_AUDIT.md`.
