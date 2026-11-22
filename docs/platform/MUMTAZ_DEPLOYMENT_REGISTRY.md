# Mumtaz deployment registry

Written 21 Nov 2026. One row per system that is deployed or can be deployed from this repository.

## Conclusion

1. **No system in this registry is fully managed yet.** None has a named owner, a tested rollback and a restore-tested backup at the same time. Jawhar staging and Pharma staging come closest; both are non-production.
2. **What the repository says deploys production and what is reported to run do not match.** `CLAUDE.md` says "deploys go to `main`"; that is true for the delivery console only. The three native Odoo production systems are reported to run from an unmerged feature branch, Faizy from its own branch, Pharma from `pharma-*` branches. The two GitHub workflows named "deploy production" and "backup" target a Docker stack that is not what runs, and have never executed.
3. **Every server fact below is REPORTED.** Nobody in this session had server access, and the session's network policy blocks the production hosts. The read-only server check in section 6 is what turns REPORTED into VERIFIED.

## Status legend

| Tag | Meaning |
|---|---|
| **VERIFIED** | Read in code at the cited path, or run on the local Odoo 19 rig on 21 Nov 2026 |
| **REPORTED** | From a repository document or an earlier session note. Includes everything about the live server |
| **PROPOSED** | Recommended, not built or not decided |
| **UNKNOWN** | Needs server evidence or an owner decision |

Sources for REPORTED rows: [`docs/infrastructure-audit/01_ENVIRONMENT_INVENTORY.md`](../infrastructure-audit/01_ENVIRONMENT_INVENTORY.md), [`06_ODOO_INSTANCES_AUDIT.md`](../infrastructure-audit/06_ODOO_INSTANCES_AUDIT.md), [`08_DEPLOYMENT_AND_CICD_AUDIT.md`](../infrastructure-audit/08_DEPLOYMENT_AND_CICD_AUDIT.md), [`09_BACKUP_AND_RECOVERY_AUDIT.md`](../infrastructure-audit/09_BACKUP_AND_RECOVERY_AUDIT.md) and the per-site pages under [`sites/`](../../sites/README.md). This registry does not repeat their detail.

## 0. Server evidence, 22 Nov 2026

The first direct evidence from the server: the owner ran read-only commands
and pasted the output. It supersedes any REPORTED row below that disagrees.
Tag used for these facts: **SERVER** (owner-run command output, not
re-checked by anyone else). Nothing was changed on the server.

### Checkouts of this repository

| Path on the server | Branch | Read by |
| --- | --- | --- |
| `/opt/mumtaz` | `claude/resume-help-95ne9v` at `9590516` (19 Nov 2026; one commit behind the branch on GitHub), 30 uncommitted entries — **not `main`** | nginx: the delivery console (`c2p-delivery-system/web`), the Jawhar copies (`jewel-landing`, `jewel-app`), and two folders that are not in git on `main` (`platform/frontend`, `zaki/frontend`) |
| `/opt/mumtaz-main` | `main` at `bf5251b` (21 Nov 2026), no uncommitted changes | `odoo2` on port 8070: `addons_path` = `/opt/mumtaz-main/addons`. nginx sends `erp.mumtaz.digital` **and the apex `mumtaz.digital`** to this instance |
| `/opt/custom_addons/Mumtaz` | `claude/resume-help-95ne9v` at `9590516` (19 Nov 2026), 30 uncommitted entries — the same branch, commit and count as `/opt/mumtaz`, so very likely the same folder through a link (to confirm with `readlink -f`) | `odoo`, `odoo3` and `odoo4`: all three use `/opt/custom_addons` and `/opt/custom_addons/Mumtaz/addons` |
| `/opt/mumtaz-pharma-staging` | `pharma-erp-v0.1` | `odoo-pharma`, with `/opt/thirdparty/cybroaddons` |
| `/opt/Mumtaz` (capital M) | `claude/odoo-architecture-review-ujm0W` (last commit July 2026) | Nothing found. Probably a leftover |
| `/opt/faizy` | not a git checkout at its top level | `faizy-odoo`: its own Odoo source and virtualenv; configuration `/opt/faizy/odoo.conf` (not shown) |

### What follows from it

| Finding | Consequence |
| --- | --- |
| Only the ERP instance runs `main`, from its own clean checkout `/opt/mumtaz-main`. C2P, the external client and the base instance run the feature branch | "Production pulls `main` at `/opt/mumtaz`" is wrong: `/opt/mumtaz` is on the feature branch. A merge to `main` reaches the ERP instance and the public website when someone pulls `/opt/mumtaz-main` — and nothing else |
| `odoo`, `odoo3` (the external client) and `odoo4` (C2P) share **one** addons checkout | A `git pull` there changes code for the external client and for C2P in the same moment. The rule "no automatic change to IG2" cannot be kept while they share it |
| nginx serves `/opt/mumtaz/platform/frontend` and `/opt/mumtaz/zaki/frontend` | These are the targets of `platform/ops/install/05-cutover.sh`. **The "stalled rebuild" was cut over.** Its control panel and its ZAKI page are being served |
| The control panel's source (`platform/control-panel/`, an 800-line FastAPI service: sign-up, tenants, Odoo provisioning, sign-on link, impersonation, billing) exists on the production branch. It was deleted from `main` in PR #124 as "abandoned" | A control plane other than the Odoo modules may be running. Whether its service is up and holds real tenants is UNKNOWN — the next check |
| The ZAKI back end in `platform/zaki/backend` is the one the security review found unauthenticated, with one Odoo administrator for every tenant (audit APP-01, APP-02) | If its service is running, that finding is live, not theoretical. UNKNOWN until the next check |
| No nginx root points at `website/`, `sites/`, `ops/` or `tools/` | Those folders are free to reorganize. The apex site and `app.` and `zaki.` hostnames are not served from the paths the old deploy scripts write to (`/var/www/…`), except the marketplace and the two WordPress sites |
| nginx reports `conflicting server name "www.mumtaz.digital"` | Two definitions claim the apex; one is ignored |
| nginx is `1.24.0-2ubuntu7.21` | Patched for the November 2026 nginx flaws (CVE-2026-123007 and others) |
| The host shows "System restart required" and 30 pending package updates | A reboot window is needed |

### Second round, same day

| Fact (SERVER) | Consequence |
| --- | --- |
| `mumtaz-platform` and `zaki` are both **active**, on loopback ports 8002 and 8001 | The FastAPI control panel and the FastAPI ZAKI back end are running |
| nginx proxies `app.mumtaz.digital` and `marketplace.mumtaz.digital` to 8002, and `zaki.mumtaz.digital` (`/api/`, `/health`) to 8001, with no access control in the reviewed definition | Both are reachable from the internet |
| The deployed ZAKI back end is byte-identical to the reviewed file (`platform/zaki/backend/main.py`): its finance, health-score, opportunities, knowledge-base and voice routes take a tenant number and check nothing | **Audit findings APP-01 and APP-02 are live**, subject to one confirmation: that the routes answer for the tenants on record |
| The control panel's database `mumtaz_platform` holds **2** tenants | It is in use, at least minimally. Decision P-02 must treat it as a live system, not as dead code |
| The control panel has an open public sign-up route, and its token-signing secret has a default written in the code on a public branch | If the server's settings file does not set its own secret, anyone can forge an administrator token. To check: that the setting exists (not its value) |
| Ports 8069 (base Odoo) and 8071 (the external client's Odoo) listen on every interface; all other Odoo ports are loopback only | Audit finding F-01 confirmed at the listener level. Whether a firewall blocks them is the next check |
| `mumtaz.digital` is proxied to the ERP instance on 8070 | The public website is already served by the ERP's Odoo and database. Decision P-10 is about moving it away, not about where to put it first |
| Databases present: `Mumtaz_C2P`, `Mumtaz_C2P_staging`, `Mumtaz_ERP`, `Mumtaz_IG2`, `IG2`, `mumtaz_erp`, `mumtaz_pharma`, `mumtaz_platform`, `faizy_prod`, `scratch_pre`, and two demo databases not seen before (`C2P_DEMO_E2C`, `Mumtaz_Demo_E2C`) | Matches the audit's list of stray databases, plus two |
| Also listening on loopback: an Ollama model server, Redis, MariaDB, and two Docker-published ports (3000, 8000) not accounted for in this repository | To identify |

**Deploy caution that follows.** `/opt/mumtaz-main` is clean and on `main`,
so the next pull there brings every change merged since 21 Nov, including the
tenant-manager and control-plane changes of platform slice 1. Those add
database columns. If the two modules are installed in `Mumtaz_ERP`, restart
that instance only together with
`-u mumtaz_tenant_manager,mumtaz_control_plane`, after a backup; new code on
old columns would fail.

### Next read-only checks

1. Do the ZAKI finance routes answer without credentials (status code only), and which databases do the two tenants point at?
2. Does the server's settings file set the control panel's token secret and `ZAKI_REQUIRE_JWT`? (presence only)
3. Firewall state for ports 8069 and 8071.
4. Is `/opt/custom_addons/Mumtaz` a link to `/opt/mumtaz`?
5. Which Mumtaz modules are installed in `Mumtaz_ERP`.

## 1. The four categories

| Category | Meaning | Systems |
|---|---|---|
| **Shared Platform** | Runs the business of selling and operating products | Control plane, marketing website |
| **Commercial Product** | Sold to customers | Mumtaz ERP, Jawhar, Pharma, ZAKI, Marketplace, Delivery OS |
| **Customer Deployment** | One customer's own system. Not a product; changed only with that customer's process | C2P (internal customer), IG2 (external client) |
| **Supporting** | Independent ventures and content sites that share the server or the repository | Faizy, two WordPress sites |

## 2. Registry

Owner is **UNKNOWN** for every row until audit decision D-02 names one business owner and one technical owner per system. Backup is "none verified" for every row: see section 4.

### 2.1 Shared Platform

| System | Domain | Runtime (REPORTED) | Database | Branch the server runs (REPORTED) | Deploy manifest in the repo (VERIFIED path) | Manifest matches reality? |
|---|---|---|---|---|---|---|
| **Control plane** (tenants, plans, subscriptions, provisioning) | `app.mumtaz.digital` is the intended address | UNKNOWN which Odoo instance holds the tenant registry. The static portal at this hostname calls an API whose source was deleted in July 2026 | UNKNOWN — `Mumtaz_ERP` is the likely candidate (decision P-02) | UNKNOWN | Odoo modules `addons/mumtaz_tenant_manager`, `addons/mumtaz_control_plane`. Static portal: `sites/app.mumtaz.digital/portal/deploy.sh`, `ops/deployment/deploy-website.sh` | **No.** No manifest installs the control-plane modules anywhere. The static portal's back end no longer exists in git |
| **Marketing website** | `mumtaz.digital`, `www.` | nginx static web root | none | UNKNOWN which copy is served; on 21 Nov the live title matched `platform/marketing` (REPORTED in `REPO_MAP.md`) | `ops/deployment/deploy-website.sh` (publishes `sites/mumtaz.digital/site/`, default branch `main`); `platform/ops/install/05-cutover.sh` (publishes `platform/marketing/`) | **No.** Two scripts publish two different copies to two different roots. Five nginx files define the apex (section 3). The native Odoo website module (`addons/mumtaz_website_builder`) is not deployed anywhere by any manifest; its host is decision P-10 |

### 2.2 Commercial Products

| System | Domain | Runtime (REPORTED) | Database | Branch the server runs (REPORTED) | Deploy manifest in the repo (VERIFIED path) | Manifest matches reality? |
|---|---|---|---|---|---|---|
| **Mumtaz ERP** (flagship general ERP) | `erp.mumtaz.digital`, `admin.` | systemd `odoo2`, port 8070. Records conflict: `odoo` on 8069 may answer this hostname instead, and that unit is pinned to the C2P database (F-07) | `Mumtaz_ERP` | `claude/resume-help-95ne9v`, not `main` | None that is tested. By hand: `git pull`, then `odoo -u`. `ops/deployment/deploy.sh` fetches `main`; `scripts/deploy-architecture-review.sh` pulls another feature branch | **No** |
| **Mumtaz ERP staging tenants** (new in this branch) | `<code>.erp.mumtaz.digital` (PROPOSED address pattern; VERIFIED as the default the code writes) | Not deployed. Provisioning is VERIFIED on the local rig only | `stg_<code>` — one database per tenant | n/a | `scripts/tenant_journey_ci.sh` proves the path on a throwaway database; no server manifest yet | n/a — nothing on a server. Where to enable it first is decision P-03 |
| **Jawhar** (jewellery edition) | `jewel.mumtaz.digital` | Docker Compose project `mumtaz-jewel-staging`, ports 8072/8073 on loopback | `jewel_demo`, own PostgreSQL 16 container | The one branch named in the kit's settings file; the script refuses any other branch and refuses the production checkout (VERIFIED in the script) | `deploy/jewel-staging/deploy.sh`, `finish.sh`, `backup.sh`, `verify_site.sh` | **Yes** — the reference deploy kit in this repository. Staging/demo only |
| **Pharma** | `pharma.mumtaz.digital` | systemd `odoo-pharma`, ports 8076/8077 on loopback | `mumtaz_pharma` | `pharma-*` branches (four, unmerged) | `deploy/pharma-staging/stage.sh` — exists on the `pharma-*` branches, **not on `main`** | **Partly.** A gated script with a deploy log exists, but outside `main`. Staging only |
| **ZAKI** | `zaki.mumtaz.digital` | UNKNOWN which of three implementations is served, if any | none of its own | UNKNOWN | `sites/zaki.mumtaz.digital/node-app/deploy.sh` and `update.sh` (both pull `claude/odoo-architecture-review-ujm0W`); `ops/deployment/deploy-website.sh` (static page); `platform/ops/install/05-cutover.sh` (FastAPI) | **No.** Three manifests for three implementations; two pull a feature branch. None is safe to expose ([`MUMTAZ_AI_ARCHITECTURE.md`](MUMTAZ_AI_ARCHITECTURE.md)) |
| **Marketplace** | `marketplace.mumtaz.digital` | nginx static pages; back end deleted | via the deleted API | UNKNOWN | `ops/deployment/deploy-website.sh`, `ops/deployment/nginx-marketplace.conf` | **No** — orphaned |
| **Delivery OS** (C2P Agency OS) | `delivery.mumtaz.digital` | uvicorn under systemd, port 8800 on loopback, behind nginx | SQLite files beside the code | `main` | `c2p-delivery-system/deploy/update.sh` (`git pull --ff-only origin main`, relink console, restart, health check) | **Yes for code.** No backup, test or rollback step. A merge to `main` is a production release |

### 2.3 Customer Deployments

| System | Domain | Runtime (REPORTED) | Database | Branch the server runs (REPORTED) | Deploy manifest in the repo (VERIFIED path) | Manifest matches reality? | Rule for change |
|---|---|---|---|---|---|---|---|
| **C2P** — the group's own CRM and internal ERP. An internal customer, not a product | `core2plus.com` | systemd `odoo4`, port 8075. A second unit (`odoo`, 8069) is also bound to this database | `Mumtaz_C2P` | `claude/resume-help-95ne9v`; some modules were copied to the server by hand; 25 business rules exist only in the database | None. Install note: `addons/c2p_project_tracker/scripts/backup_and_install.md` | **No** | Changes go through a backup and a staging copy first. Internal, but it holds real contacts and sends real email |
| **IG2** — external client's accounting | `ig2.mumtaz.digital`; in practice a raw port over plain HTTP (F-01) | systemd `odoo3`, port 8071 on all interfaces | `Mumtaz_IG2` | `claude/resume-help-95ne9v`; its modules are deliberately not on `main` | None | **No** | **No automatic change.** Nothing reaches this database without a compatibility test on a copy and the client's approval. No staging copy exists today |

### 2.4 Supporting

| System | Domain | Runtime (REPORTED) | Database | Branch the server runs (REPORTED) | Deploy manifest in the repo (VERIFIED path) | Manifest matches reality? | Rule for change |
|---|---|---|---|---|---|---|---|
| **Faizy** — independent venture | `myfaizy.com` | systemd `faizy-odoo`, own OS user, loopback ports | `faizy_prod`, own database role | `claude/repo-audit-faizy-instance-fck6o3` (well ahead of `main`) | A one-line command documented in `faizy/CLAUDE.md` on that branch; CI `faizy-ci.yml` | **Yes, on its branch.** The copy on `main` is behind production | Own branch, own release. Not forced into the ERP architecture |
| **WordPress sites** | `odditytrend.com`, `youngcraze.com` | UNKNOWN whether deployed | one MariaDB database each | UNKNOWN | `wordpress-sites/deploy/setup-lemp.sh` (install only) | UNKNOWN | Should not share a host with client ledgers (audit D-12) |

## 3. Manifest mismatches, in one list

| # | Mismatch | Evidence | Tag |
|---|---|---|---|
| M-1 | `CLAUDE.md` says the VPS pulls `main`. The native Odoo production checkouts are reported on `claude/resume-help-95ne9v` | `CLAUDE.md`; audit 01 §5, 06 I-6 | VERIFIED text / REPORTED server |
| M-2 | `deploy-production.yml` and `backup.yml` run `scripts/deploy-production.sh` and `scripts/backup.sh`, which drive a Docker Compose stack and a database named `mumtaz`. Neither is reported to exist on the server | `.github/workflows/deploy-production.yml:29-45`, `.github/workflows/backup.yml:23` | VERIFIED |
| M-3 | Both workflows, with `deploy-staging.yml` and `test.yml`, still use `secrets.*` inside an `if:` on `main`. GitHub refuses to parse that, so they have never run. `deploy-staging.yml` also deploys a `develop` branch that does not exist | `backup.yml:26`, `deploy-production.yml:48`, `deploy-staging.yml:33`, `test.yml:129` | VERIFIED |
| M-4 | Fixing M-3 without redesign would start SSH jobs against production that back up the wrong database and report success (audit D-06) | audit 09 §2 | REPORTED |
| M-5 | Six scripts pull the feature branch `claude/odoo-architecture-review-ujm0W`: `sites/zaki.mumtaz.digital/node-app/deploy.sh:12`, `update.sh:9`, `ops/deployment/deploy-mumtaz.sh:7`, `deploy-phase-a.sh:18`, `setup-ssl.sh:25`, `scripts/deploy-architecture-review.sh:37` | those lines | VERIFIED |
| M-6 | The apex `mumtaz.digital` is defined in five nginx files with two different web roots: `ops/deployment/nginx-mumtaz-digital.conf`, `ops/deployment/nginx-mumtaz-platform.conf`, `platform/ops/nginx/mumtaz.digital.conf`, `sites/mumtaz.digital/site/nginx.conf`, `ops/platform-routing/nginx-wildcard.conf` | those files | VERIFIED |
| M-7 | `ops/deployment/deploy-website.sh` copies the ZAKI static page with `rsync --delete` into the directory the ZAKI node app is documented to run from and keep its settings file in | [`MUMTAZ_AI_ARCHITECTURE.md`](MUMTAZ_AI_ARCHITECTURE.md) | VERIFIED |
| M-8 | `docs/mumtaz-website/README.md:110` gives a "production" command against the ERP instance's config and `Mumtaz_ERP` for the website module. No decision records that the website belongs in that database | that line; decision P-10 | VERIFIED text |
| M-9 | Pharma's deploy kit and Faizy's production code are not on `main` | `sites/pharma.mumtaz.digital/README.md`, `sites/myfaizy.com/README.md` | REPORTED |
| M-10 | Odoo is installed from a nightly package source; a system package upgrade moves every native instance to a new build at once | audit 06 I-10 | REPORTED |

## 4. Backup state

| System | State | Tag |
|---|---|---|
| `Mumtaz_C2P`, `Mumtaz_ERP`, `Mumtaz_IG2`, their filestores | No backup found | REPORTED |
| `faizy_prod` | Not documented | UNKNOWN |
| Delivery OS SQLite stores and its settings file | No backup found | REPORTED |
| Pharma staging | On-demand dumps, same disk | REPORTED |
| Jawhar staging | Scripted dump with a restore drill; whether the schedule was installed is not known | VERIFIED script / UNKNOWN schedule |
| Off-site copy of anything | None found | REPORTED |
| Restore test of anything | None recorded | REPORTED |

No system may be described as backed up until a restore has been demonstrated. Detail and proposed recovery objectives: audit 09.

## 5. What a registry entry must contain before a system counts as managed (PROPOSED)

| Field | Requirement |
|---|---|
| Owner | One business owner and one technical owner, by name (audit D-02) |
| Category | One of the four in section 1; a Customer Deployment also names the customer and who approves change |
| Source | Repository and the branch or tag the server checks out; `main` or a release tag, never a feature branch |
| Deploy command | One documented command or workflow, kept in git, that refuses the wrong branch |
| Rollback | A written, rehearsed way back for code and for data |
| Backup | Schedule, off-site destination, and the **date of the last successful restore test** |
| Health check | A check against the named instance, not "any Odoo answers" |
| Environment | Production or staging, stated; staging never shares a database role or outbound mail with production |
| Record | Each deploy appends who, what version, which database, dump location and result to a per-system log |

Scorecard today: Jawhar staging meets the source, deploy and health rows; Pharma staging meets deploy, rollback (printed, not rehearsed) and record; the delivery console meets source and deploy. No production Odoo system meets any row. (REPORTED)

## 6. Staging tenant convention (VERIFIED in code, this branch)

| Rule | Where |
|---|---|
| A staging tenant's database name starts with `stg_`; a production tenant's must not | `addons/mumtaz_tenant_manager/models/tenant_provisioning.py`, constraint `_check_environment_database_name` |
| The tenant record carries `environment = staging` | same file, field `environment` |
| A registration request always creates a staging tenant named `stg_<code>`, with subdomain `<code>` | `addons/mumtaz_control_plane/models/signup_request.py`, `action_approve` |
| A tenant is `active` only after a real, verified provisioning run | `tenant_provisioning.py`, `_apply_provision_result` |
| A failed run that created a database flags it for a person to inspect; nothing is dropped automatically | `addons/mumtaz_tenant_manager/services/provisioning.py`, `BaseProvisioner.run` |

The prefix lets backup, monitoring and clean-up tooling tell trial data from production by name. Tenants created before this field existed have an empty `environment` and are not reclassified automatically.

## 7. Evidence still needed from the server

The owner runs the read-only verification pack in [`docs/infrastructure-audit/13_REMEDIATION_BACKLOG.md`](../infrastructure-audit/13_REMEDIATION_BACKLOG.md) (items V-01 to V-12; the script masks passwords and writes nothing) and returns the output privately.

| Registry gap | Closed by |
|---|---|
| Which unit answers each hostname; which web root serves the apex | V-03 |
| Branch and commit of every checkout; untracked files | V-05 |
| Which of ports 3000, 8001, 8002, 8003 has a listener (ZAKI, deleted API) | V-06 |
| Open ports and firewall rules | V-02 |
| Database list, owners, roles, connections | V-08 |
| Existing dumps, schedules, provider snapshots | V-09 |
| Certificate and domain expiry | V-10 |
| Modules installed per database — which database holds the tenant registry (P-02) and whether `mumtaz_sso` is installed anywhere | V-11 |
