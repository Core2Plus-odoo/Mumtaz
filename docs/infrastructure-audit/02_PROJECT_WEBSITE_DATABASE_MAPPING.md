# 02 — Project ↔ Website ↔ Database Mapping

Evidence labels are defined in `01_ENVIRONMENT_INVENTORY.md`. Nothing here was verified on the server; "R-doc" rows come from owner-run output recorded in the repository.

**Do not treat these as one system.** At least four independent data owners share the VPS: the Core 2 Plus group itself (C2P CRM, Platform ERP), a client (IG2), a separate product (Faizy), and demo/staging tenants (Jewel, Pharma). Their data, access and recovery must be handled separately.

## 1. Mapping table

| # | Website | Served by | Code of record | Database | Runs on | Routing | Config source | External services | Env | Shares infra/data with | Deploy + recovery known? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `core2plus.com` | Odoo 19, `odoo4.service` :8075 | `addons/c2p_*` on `main` **plus** `c2p_pk_vouchers`, `c2p_proposal`, `c2p_appointment` on branch `claude/resume-help-95ne9v` **plus** `c2p_master_agent` (no source anywhere) **plus** 25 server actions stored in the DB | `Mumtaz_C2P` | VPS, systemd | nginx vhost (template on branch: `ops/deployment/nginx-core2plus.conf`) | `/etc/odoo4.conf` | SMTP outbound (BD engine), LLM APIs | **Production** | Postgres role `odoo`; also selectable by `odoo.service` :8069 | Deploy: manual, partly documented. Recovery: **no backup found** |
| 2 | `erp.mumtaz.digital`, `admin.mumtaz.digital` | Odoo 19 — `odoo.service` :8069 and/or `odoo2.service` :8070 (**which one is NV**) | `addons/mumtaz_*` | `Mumtaz_ERP` (odoo2) — but `odoo.service` is pinned to `Mumtaz_C2P` | VPS, systemd | nginx vhost; `/longpolling` proxied to :8073, which is the **Jewel** container | `/etc/odoo/odoo.conf`, `/etc/odoo2.conf` | Stripe, e-invoicing gateways (ZATCA, FBR), SMTP | **Production** | Postgres role `odoo` | Deploy: four conflicting scripts. Recovery: **no backup found** |
| 3 | `ig2.mumtaz.digital` and `http://<VPS IP>:8071` | Odoo 19, `odoo3.service` :8071 on `0.0.0.0` | Branch `claude/resume-help-95ne9v` (`c2p_pk_vouchers`, `mumtaz_financial_reports`) + third-party `base_accounting_kit` | `Mumtaz_IG2` (two client companies) | VPS, systemd | **Bypasses nginx** — direct port, plain HTTP | `/etc/odoo3.conf` | — | **Production client data; no staging** | Postgres role `odoo` | Deploy: `git pull` + `-u`. Recovery: **no backup found** |
| 4 | `myfaizy.com` | Odoo 19 (source install), `faizy-odoo.service` | `faizy/` on branch `claude/repo-audit-faizy-instance-fck6o3` | `faizy_prod` | VPS, systemd, OS user `faizy` | nginx vhost | `/opt/faizy/odoo.conf` | WhatsApp, payments (NV) | **Production** | Same Postgres server, **own role** | Deploy: documented one-liner. Recovery: NV |
| 5 | `jewel.mumtaz.digital` | Static landing (`/opt/mumtaz/jewel-landing`) + Odoo 19 in Docker :8072/:8073 | `website/jewel/`, `addons/mumtaz_jewellery*`, `apps/jawhar-web/` on `main` | `jewel_demo` in its **own** Postgres 16 container | VPS, Docker Compose `mumtaz-jewel-staging` | nginx vhost; Odoo prefixes behind IP allow-list **or** basic auth | `deploy/jewel-staging/.env` | none connected | Staging / demo, synthetic data | Nothing by design; in practice `erp.` longpolling is routed into its port | Deploy + backup + restore drill all scripted |
| 6 | `pharma.mumtaz.digital` | Odoo 19, `odoo-pharma.service` :8076/:8077 | Branches `pharma-*`; third-party kit in `/opt/thirdparty` | `mumtaz_pharma` | VPS, systemd | nginx vhost, own certificate | `/etc/odoo-pharma.conf` | none (neutralised) | Staging, demo data | Postgres role `odoo` | Deploy + rollback logged step by step |
| 7 | `delivery.mumtaz.digital` | Static console (symlink `web/index.html`) + FastAPI :8800 | `c2p-delivery-system/` on `main` | SQLite `delivery.db`, `control.db`, per-tenant `.db` files beside the code | VPS, systemd | nginx vhost, `/api` → :8800 | `c2p-delivery-system/delivery_api/.env` | LLM provider, GitHub (stored token), any Odoo it is connected to, Stripe | **Production** | Holds a stored connection to a live Odoo database | Deploy: `deploy/update.sh`. Recovery: **no backup found** |
| 8 | `app.mumtaz.digital` | Static portal + `/api` → :8002 | `apps/portal/` on `main`; API source **deleted** | SQLite `/opt/zaki-server/users.db` → Odoo via admin XML-RPC | VPS | nginx — **five different definitions in the repo** | `/opt/zaki-server/.env` | Stripe, SMTP, Anthropic | Unknown | Odoo admin credentials for `Mumtaz_ERP` | Not known |
| 9 | `zaki.mumtaz.digital` | One of: Node :3000, static + FastAPI :8001, static + FastAPI :8002 | `apps/zaki-ai/`, `apps/zaki/`, `platform/zaki/` | none / via Odoo | VPS | nginx — three conflicting upstreams | varies | Anthropic, ElevenLabs | Unknown | — | Not known |
| 10 | `marketplace.mumtaz.digital` | Static + `/api` → :8002 | `apps/marketplace/` | via zaki-server | VPS | nginx standalone vhost | — | — | Unknown | — | Not known |
| 11 | `mumtaz.digital`, `www.` | Static | `apps/website/` (also `platform/marketing/`, `website/index.html`) | none | VPS `/var/www/mumtaz.digital` or `/opt/mumtaz/marketing` | nginx — two definitions | — | — | Production | — | Copy script |
| 12 | `odditytrend.com`, `youngcraze.com` | WordPress | `wordpress-sites/` | two MariaDB DBs | "shared Hostinger VPS" | nginx + PHP-FPM | `setup-lemp.env` | AdSense | Unknown | Same VPS as client ERPs | Installer only; no backup |

## 2. Answers to the ten mapping questions, per site

The table columns answer questions 1–10 in order. Three sites need more explanation.

### `erp.mumtaz.digital` — which database does it actually open?

Three documents disagree:

- The repository says Odoo on :8069 serves database `Mumtaz_ERP` (`README.md`).
- The VPS discovery of 2026-11-18 says `/etc/odoo/odoo.conf` (the :8069 service) has `dbfilter = ^Mumtaz` and `db_name = Mumtaz_C2P`, and that `Mumtaz_ERP` belongs to `odoo2` on :8070.
- The IG2 audit of 2026-11-20 lists `odoo` :8069 with no database and `odoo4` :8075 for `Mumtaz_C2P`.

If the `erp.` vhost still proxies to :8069, then **`erp.mumtaz.digital` opens the C2P CRM database**, not the platform ERP. This must be confirmed on the server before anything else is touched (verification V-03 in `13_REMEDIATION_BACKLOG.md`).

### `Mumtaz_C2P` — two servers, one database

`odoo.service` (:8069) is pinned to `Mumtaz_C2P` and `odoo4.service` (:8075) serves `Mumtaz_C2P` for `core2plus.com`. If both are running with different `addons_path` values, then scheduled jobs run twice, and one of them loads the database with modules missing from its path. The 2026-10-05 inspection already measured "module shadowing" between duplicate checkouts.

### Cron polling across databases

`odoo2` and `odoo3` have a `dbfilter` but no `db_name`. Odoo's cron runner ignores `dbfilter`, so those two processes open **every database on the PostgreSQL server** looking for scheduled jobs. This was observed directly: within seconds of `mumtaz_pharma` being created, both processes held sessions on it. Consequences:

- The IG2 client's Odoo process connects to the C2P CRM, the platform ERP and staging databases, and vice versa.
- Jobs can run under a process whose addons path lacks the module that defines them.
- Any database restored onto this server for testing is immediately picked up by production processes (and, unless neutralised, sends real email).

## 3. Risk patterns the brief asked about

| Pattern | Found? | Where |
|---|---|---|
| Incorrect database connection | **Suspected** | `erp.mumtaz.digital` → :8069 → `Mumtaz_C2P` (see above) |
| Website pointing at a test database | Not found | — |
| Several sites unintentionally sharing one database | **Suspected** | `odoo` and `odoo4` both on `Mumtaz_C2P` |
| Cross-project data exposure | **Confirmed by R-doc** | Shared Postgres role `odoo`; cross-database cron polling; `dbfilter = ^Mumtaz` on :8069 matches every `Mumtaz*` database |
| Duplicate application instances | **Confirmed by R-doc** | `odoo` / `odoo4`; duplicate 37-module checkouts on the VPS |
| Production using development configuration | **Confirmed by R-doc** | Production checkouts sit on feature branch `claude/resume-help-95ne9v`; IG2 served over plain HTTP on a raw port |
| Abandoned application still accepting traffic | **Suspected** | `erp-server.service` crash-looping; `zaki-server` routes still in nginx templates; `ig2.` vhost websocket points at a dead port |
| Publicly exposed database service | Not found for PostgreSQL (no evidence 5432 is open — **NV**). **Odoo application ports are exposed** (8071 confirmed by R-doc; others reported) |

## 4. Shared components and blast radius

| Shared component | Used by | If it fails or is compromised |
|---|---|---|
| The VPS itself (one host, ~8 GB RAM) | everything | Every product and client is down together; no second host |
| PostgreSQL server | all native Odoo instances | All Odoo databases unavailable |
| PostgreSQL role `odoo` | C2P, ERP, IG2, Pharma | Read/write on every one of those databases |
| OS user `odoo` | `odoo`, `odoo2`, `odoo3`, `odoo4`, `odoo-pharma` | Read access to every config file and filestore owned by that user |
| nginx | all sites | All sites unreachable; one bad vhost blocks reload for all |
| `/opt/mumtaz` checkout | C2P Agency OS, Jewel landing, legacy scripts | A branch switch here changes what several services serve |
| Hostinger DNS zone `mumtaz.digital` | ten subdomains | All subdomains fail together if the registration or zone lapses |
