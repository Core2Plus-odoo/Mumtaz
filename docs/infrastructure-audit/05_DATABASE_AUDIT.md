# 05 — Database Audit

**No database was connected to in this audit.** No SQL of any kind was run. Everything below comes from repository files (V-repo) and from owner-run output recorded in repository documents (R-doc). Sizes, versions of the system PostgreSQL, extensions, index health, privileges and connection encryption are therefore **Not Verified**; section 6 lists the exact read-only queries that would settle them.

## 1. Engines in use

| Engine | Where | Version | Evidence |
|---|---|---|---|
| PostgreSQL (system package) | VPS, local socket / `localhost:5432` | "14+" per Faizy doc; exact version **NV** | R-doc |
| PostgreSQL 16 (alpine) | Docker, Jewel staging, not published to the host | 16 | V-repo `deploy/jewel-staging/docker-compose.yml` |
| PostgreSQL 15 (alpine) | Legacy compose files — not evidenced as running | 15 | V-repo |
| SQLite | C2P Agency OS (`delivery.db`, `control.db`, `tenants/*.db`); `zaki-server` (`users.db`) | library default | V-repo |
| MariaDB | WordPress installer | distro default | V-repo `wordpress-sites/deploy/setup-lemp.sh`; **NV** whether installed |

## 2. Database register

| Database | Application | Owner role | Data sensitivity | Lifecycle | Backup found | Findings |
|---|---|---|---|---|---|---|
| `Mumtaz_C2P` | C2P CRM (Odoo 19, 144 modules, 41 users, 3 companies) | `odoo` | **High** — 41k leads with contact data, proposals, invoices | Production | None | F-02, F-05, F-06, F-07 |
| `Mumtaz_ERP` | Platform ERP / tenant registry | `odoo` | High — tenant, subscription, billing data | Production | None | F-02, F-06, F-07 |
| `Mumtaz_IG2` | Client accounting, two legal entities | `odoo` | **High** — a client's general ledger, vendors, tax | Production | None | F-01, F-02, F-06, F-08 |
| `faizy_prod` | Faizy | `faizy` | **High** — family members, identity documents (CNIC, passport), wallet transactions | Production | NV | F-02 |
| `mumtaz_pharma` | Pharma staging | `odoo` | Low — fictional demo data, neutralised | Staging | Pre-change dumps on the same disk | F-06 |
| `jewel_demo` | Jewel demo | container-local | Low — synthetic | Staging | Scripted; cron install NV | — |
| `mumtaz_platform` | Platform rebuild control DB (users, tenants, module catalogue) | NV | Medium | Unknown | None | F-13 |
| `mumtaz_erp` | Unknown; lower-case twin of `Mumtaz_ERP` | NV | Unknown | Unknown | — | F-13 |
| `IG2` | Unknown; possibly an earlier IG2 database | NV | Possibly High | Unknown | — | F-13 |
| `Mumtaz_C2P_staging` | Copy of the CRM, owned by `postgres` | `postgres` | **High — real lead data in a non-production database** | Unknown | — | F-13, F-14 |
| `scratch_pre` | Unknown; described as dead | NV | Unknown | Unknown | — | F-13 |
| `delivery.db` (+ `control.db`, tenant DBs) | C2P Agency OS | file owner | High — client engagements, leads, encrypted Odoo connection and GitHub token | Production | None | F-02 |
| `users.db` | zaki-server | file owner | High — user accounts and password hashes, tenant registry | Unknown | None | F-11 |

## 3. Access model

| Check | Result | Evidence |
|---|---|---|
| Shared privileged account | **Yes.** One PostgreSQL role, `odoo`, owns or can open the C2P, ERP, IG2 and Pharma databases. The Odoo role normally has `CREATEDB`, so it can also create and drop databases | R-doc; `ops/deployment/odoo-c2p.conf` on branch says "db_password — COPY FROM /etc/odoo/odoo.conf" |
| Per-application isolation | Only Faizy (own role, own OS user) and Jewel (own container) | R-doc, V-repo |
| Superuser use by applications | A staging database is owned by `postgres`; whether any app connects as `postgres` is **NV** | R-doc |
| Network exposure of 5432 | **NV.** The setup script opens only 22/80/443, but ports have been added to `ufw` by hand since | V-repo `scripts/setup-vps.sh`; R-doc |
| Connection encryption | Local connections; TLS to PostgreSQL **NV** (not needed for loopback) | INF |
| Database manager (`/web/database/*`) | `list_db = False` on `odoo`, `odoo3`; **`list_db = True` on Jewel staging** (deliberate, behind an allow-list); others **NV** | R-doc, V-repo |
| Odoo master password (`admin_passwd`) | Present in every config; strength **NV**. A prior audit records a default-strength administrator credential on a reachable instance | R-doc (as-is audit, branch `claude/gifted-turing-jjdsb2`) |
| Hardcoded credentials in repo | None found on `main` or in history beyond weak placeholder defaults in `.env.example` | V-repo (history scan, 1,089 commits) |

## 4. Application ↔ database correctness

See `02_PROJECT_WEBSITE_DATABASE_MAPPING.md` §2 for the reasoning.

| Issue | Status |
|---|---|
| `odoo` (:8069) and `odoo4` (:8075) both bound to `Mumtaz_C2P` | Suspected duplicate instance — verify |
| `odoo2`, `odoo3` have no `db_name`; their cron workers open every database | Confirmed by R-doc (observed sessions on a new database) |
| `dbfilter = ^Mumtaz` on :8069 matches `Mumtaz_C2P`, `Mumtaz_ERP`, `Mumtaz_IG2`, `Mumtaz_C2P_staging` | Confirmed by R-doc. With `db_name` set and `list_db = False` the practical exposure is reduced, but any request that can name a database (`?db=`) is not constrained to one tenant |
| Mixed-case names (`Mumtaz_ERP` vs `mumtaz_erp`) | Confirmed by R-doc — a typo selects a different database |
| Naming convention | None. Six conventions appear in the repository (`mumtaz`, `mumtaz_main`, `mumtaz_master`, `mumtaz_%d`, `Mumtaz_X`, `corp_{slug}`/`org_{slug}`) |

## 5. Schema, migrations and data integrity

| Topic | Observation | Evidence |
|---|---|---|
| Odoo schema | Managed by Odoo's module system; version strings are `19.0.x.y.z` across all manifests | V-repo |
| Migration control | **None beyond Odoo's own.** Upgrades are run by hand with `-u`; `scripts/migrate.py` is a thin wrapper that defaults to `-u base` on database `mumtaz` | V-repo |
| Staging before production | Only Jewel and Pharma have it. C2P has a documented restore-to-test procedure (`addons/c2p_project_tracker/scripts/backup_and_install.md`). IG2 has none | V-repo, R-doc |
| Logic stored in data | 25 `ir.actions.server` records on `crm.lead` in `Mumtaz_C2P` carry qualification, scoring, assignment and archival rules — no version history | R-doc 2026-10-05 |
| Unexplained bulk change | 29,484 of 41,182 leads archived with no lost reason and no identified cause | R-doc 2026-10-05 |
| Platform schema (`platform/db/schema.sql`) | PostgreSQL; one forward migration file; no migration tool | V-repo |
| SQLite stores | Created and altered by application code at start-up; WAL mode; no migration history | V-repo |
| Third-party modules | `base_accounting_kit` (Cybrosys) installed in `Mumtaz_IG2`. The Pharma review of the same kit found an unguarded export route and a form that can send data to the vendor, and wrote a hardening module — **applied to Pharma only** | R-doc |

## 6. Read-only verification pack (to run on the VPS, with approval)

These are metadata queries only. No table scans, no locks beyond a catalog read, no customer rows.

```sql
-- V-DB-1  server version and settings that matter
SELECT version();
SHOW listen_addresses;  SHOW ssl;  SHOW password_encryption;

-- V-DB-2  every database: owner, size, connection limit
SELECT d.datname, r.rolname AS owner, pg_size_pretty(pg_database_size(d.datname)) AS size,
       d.datallowconn, d.datconnlimit
FROM pg_database d JOIN pg_roles r ON r.oid = d.datdba
WHERE NOT d.datistemplate ORDER BY pg_database_size(d.datname) DESC;

-- V-DB-3  roles and their powers (no password hashes)
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolcanlogin, rolconnlimit
FROM pg_roles WHERE rolname !~ '^pg_';

-- V-DB-4  who is connected to what, right now
SELECT datname, usename, application_name, client_addr, state, count(*)
FROM pg_stat_activity GROUP BY 1,2,3,4,5 ORDER BY 1,2;

-- V-DB-5  last activity per database (finds dead ones)
SELECT datname, xact_commit, tup_inserted + tup_updated + tup_deleted AS writes, stats_reset
FROM pg_stat_database WHERE datname NOT IN ('template0','template1','postgres');

-- V-DB-6  per Odoo database: installed modules and where they come from
--         (run inside each database; ir_module_module is small)
SELECT name, latest_version, author FROM ir_module_module WHERE state = 'installed' ORDER BY name;

-- V-DB-7  per Odoo database: active scheduled jobs
SELECT cron_name, interval_number, interval_type, nextcall FROM ir_cron WHERE active;
```

```bash
# V-DB-8  network exposure and client rules (read-only)
sudo ss -ltnp | grep -E ':5432|:3306'
sudo grep -vE '^\s*(#|$)' /etc/postgresql/*/main/pg_hba.conf
```

## 7. What must not be done yet

- No `DROP DATABASE` for the stray databases until V-DB-2, V-DB-4 and V-DB-5 have been read and an owner has signed off each name (`15_DECISIONS_AND_APPROVALS.md`).
- No role changes or password rotation without a per-instance restart plan — every `/etc/odooN.conf` holds the shared password.
- No restore of a production dump onto this server without neutralising it first; production cron workers will attach to it within seconds.
