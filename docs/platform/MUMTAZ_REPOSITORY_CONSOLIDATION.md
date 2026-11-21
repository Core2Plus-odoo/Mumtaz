# Mumtaz repository consolidation — reconciliation

Written 21 Nov 2026. This is a pointer and a delta, not a second repository map.

## Conclusion

1. The repository is now **indexed** (by folder, by website and by module), but it is not yet **consolidated**: it still holds three ZAKI applications, three marketing sites plus two Odoo website modules, a stalled platform rebuild and a portal whose back end was deleted.
2. Each of those duplicates now has a written verdict. What blocks acting on them is not analysis; it is one fact nobody has — **which copy the server actually serves** — and a handful of owner decisions.
3. Three folders must not be moved without a step on the server: `addons/`, `c2p-delivery-system/` and the Jawhar folders. Moving them in git alone would stop running services.

## Status legend

| Tag | Meaning |
|---|---|
| **VERIFIED** | Read in code at the cited path, or run on the local Odoo 19 rig on 21 Nov 2026 |
| **REPORTED** | From a repository document or an earlier session note. Includes everything about the live server |
| **PROPOSED** | Recommended, not built or not decided |
| **UNKNOWN** | Needs server evidence or an owner decision |

## 1. Authoritative documents

| Subject | Document |
|---|---|
| What every top-level folder is; duplicates awaiting a decision | [`REPO_MAP.md`](../../REPO_MAP.md) |
| The repository website by website; what moved and what did not | [`sites/README.md`](../../sites/README.md) and `sites/<domain>/README.md` |
| Every Odoo module with layer, version, dependencies, tests | `registry.yaml` (generated), `registry/classification.json` |
| Target structure, path mapping, change register R-01 to R-17 | [`docs/infrastructure-audit/12_REORGANIZATION_PLAN.md`](../infrastructure-audit/12_REORGANIZATION_PLAN.md) |
| Module ownership, overlaps, install profiles | [`MUMTAZ_MODULE_REGISTRY_REVIEW.md`](MUMTAZ_MODULE_REGISTRY_REVIEW.md) |

## 2. Done

| Item | Evidence | Tag |
|---|---|---|
| `sites/` index: one page per website with code, database, deploy method and open points (13 sites) | `sites/README.md`; PR #173 | VERIFIED |
| Eight folders with no live deploy dependency moved under `sites/<domain>/` and `ops/`, history preserved; seven deploy scripts and one CI job updated to the new paths | mapping table in `sites/README.md`; PR #173 | VERIFIED |
| Module registry and a layering check that fails CI on an unclassified module or a new cross-layer dependency | `scripts/module_registry.py --check`; PR #177 | VERIFIED |
| Fresh-database install and test of every non-Jawhar module in CI | `scripts/platform_ci.sh`; PR #172 | VERIFIED |
| C2P modules that existed only on the server brought into git as found | PR #180; REVIEW-05 open | VERIFIED |
| A real end-to-end check of the registration-to-workspace journey in CI | `scripts/tenant_journey_ci.sh` (this branch) | VERIFIED |

## 3. Must not move without a server step

| Path | Why | Tag |
|---|---|---|
| `addons/` | Every native Odoo service's module path is reported to point at a checkout of this folder; moving it stops Odoo loading its modules. Many unmerged branches also edit it | REPORTED |
| `c2p-delivery-system/` | Production updates itself by pulling `main` at this exact path (`deploy/update.sh`). Its settings file and SQLite stores are untracked files inside the folder: after a move in git, the next pull would remove the tracked code and leave those files stranded; a link at the old path could lead git to remove them | VERIFIED script / REPORTED server |
| `apps/jawhar-web/`, `website/jewel/`, `deploy/jewel-staging/`, `docs/mumtaz-jewel/` | Wired into the Jawhar deploy kit, its compose mounts and two CI workflows | VERIFIED |
| `faizy/`, `wordpress-sites/` | Open branches and pull requests edit them. Their destination is their own repositories, not another folder here | VERIFIED |
| `ops/deployment/`, `scripts/`, `platform/`, root Docker files | Referenced by workflows or by the production branch | VERIFIED |

Installed Odoo modules are a separate rule: **never rename an installed module directly.** A rename needs a migration and a list of the databases where the module is installed.

## 4. Duplicates and their verdicts

| Area | Copies | Verdict | Where the verdict is argued | Tag |
|---|---|---|---|---|
| ZAKI application | `sites/zaki.mumtaz.digital/static`, `sites/zaki.mumtaz.digital/node-app`, `platform/zaki` | None is safe to expose. Canonical: ZAKI inside each tenant's Odoo (`mumtaz_zaki` plus a shared AI core taken from the Jawhar AI module); the three applications become reference, then retire. `platform/zaki` back end: retire, do not deploy | [`MUMTAZ_AI_ARCHITECTURE.md`](MUMTAZ_AI_ARCHITECTURE.md) | PROPOSED |
| Marketing site | `sites/mumtaz.digital/site` (14 pages), `website/index.html`, `platform/marketing/index.html` | Canonical: the native Odoo module `mumtaz_website_builder`. The three static copies are content reference and rollback until cut-over, then retire | [`MUMTAZ_WEBSITE_IMPLEMENTATION.md`](MUMTAZ_WEBSITE_IMPLEMENTATION.md) | PROPOSED |
| Odoo website modules | `mumtaz_website_builder`, `mumtaz_website` (and the lead API `mumtaz_api`) | Keep the builder; retire `mumtaz_website` after cut-over; fold or retire `mumtaz_api` with the static site | same; [`MUMTAZ_MODULE_REGISTRY_REVIEW.md`](MUMTAZ_MODULE_REGISTRY_REVIEW.md) | PROPOSED |
| Brand and tokens | About ten sources (`brand/`, `mumtaz_theme`, `mumtaz_branding`, the Jawhar stylesheet, each static site) | One token set in the approved navy, emerald and lime direction; `mumtaz_branding` holds the white-label record | [`MUMTAZ_DESIGN_SYSTEM.md`](MUMTAZ_DESIGN_SYSTEM.md) | PROPOSED |
| Control plane | Odoo modules (`mumtaz_tenant_manager`, `mumtaz_control_plane`, `mumtaz_billing_stripe`, `mumtaz_subdomain_routing`) vs `platform/` (FastAPI rebuild, control panel absent) vs the static portal `sites/app.mumtaz.digital/portal` (back end deleted in commit `48a2cf9`) | Canonical: the Odoo modules — they exist, install, and now pass a real end-to-end provisioning check. `platform/` is a stalled rebuild: reference, then archive. The static portal is orphaned: retire or rebuild as a thin client of the Odoo control plane | [`MUMTAZ_CURRENT_SYSTEM_AUDIT.md`](MUMTAZ_CURRENT_SYSTEM_AUDIT.md); audit decision D-08 | VERIFIED (modules work) / PROPOSED (retirement) |
| Tenancy model | `mumtaz.tenant` (database per tenant) vs `mumtaz.org` (company per organization) | Database per tenant only (decision P-01, consistent with ADR-002); migrate or retire `mumtaz_org_config` | [`MUMTAZ_MODULE_REGISTRY_REVIEW.md`](MUMTAZ_MODULE_REGISTRY_REVIEW.md) | PROPOSED |
| Portals, AI/CFO modules, foundation, APIs | several modules each | Survivor named per group | [`MUMTAZ_MODULE_REGISTRY_REVIEW.md`](MUMTAZ_MODULE_REGISTRY_REVIEW.md) | PROPOSED |
| Deploy scripts and nginx definitions | `ops/deployment`, `ops/platform-routing`, `platform/ops`, `deploy/`, `scripts/`, per-site `deploy.sh` and `nginx.conf` | One template per hostname generated from the live configuration; six scripts still pull a feature branch | [`MUMTAZ_DEPLOYMENT_REGISTRY.md`](MUMTAZ_DEPLOYMENT_REGISTRY.md) section 3; change R-12 | VERIFIED (duplication) / PROPOSED |
| Legacy Docker "production" stack | root `Dockerfile`, `docker-compose*.yml`, `scripts/deploy-*.sh`, `backup.sh`, two workflows | Not what runs; retire after approval (audit D-06) | audit 08 | REPORTED |

Nothing in this table has been deleted or deprecated. One pull request per row, after its precondition below.

## 5. Next steps, in dependency order

| # | Step | Precondition | Changes production? |
|---|---|---|---|
| 1 | Server inventory: hostname → service → checkout → branch → database → installed modules | Owner runs the read-only verification pack (audit 13, V-01 to V-12) | No |
| 2 | Record the inventory in the registry (`installed_in` per module) and in the deployment registry | Step 1 | No |
| 3 | Add owner, install profiles and the first registry checks so a wrong bundle fails CI | None — repository only | No |
| 4 | Remove customer-specific data from reusable and public code (section 7) | Decision P-15; step 1 for the two modules that may be installed for the external client | No for static files; module changes follow the customer's change rule |
| 5 | Retire dead static copies and scripts that nothing serves | Step 1 shows nothing live reads them; one owner decision per row of section 4 | No |
| 6 | Reconcile the production feature branch into `main`; servers check out `main` or a release tag | Step 1; verified backups; a staging copy per database (change R-05, R-11) | Yes — approval per system |
| 7 | Move Faizy, Pharma, the external client's code and the WordPress sites to their own repositories | Decision D-12; a deploy plan per system, because servers pull this repository | Yes — remote of each checkout |
| 8 | Move `c2p-delivery-system/` and the Jawhar folders under `sites/` | Step 6 pattern proven; a short stop-move-start window per site | Yes — approval per site |
| 9 | Split `addons/` by product, each Odoo config given its own module path | Steps 2, 6 and the install profiles | Yes — every Odoo instance |
| 10 | Merge or retire overlapping modules (portals, CFO, foundation, AI) with migrations | Step 2 (where each is installed); never a direct rename | Yes — per database |

Steps 1 to 5 change nothing on any server and can proceed now.

## 6. Stale statements to correct in existing documents

Listed here; the files themselves were not edited in this change.

| File | Statement | Fact at this branch | Tag |
|---|---|---|---|
| `REPO_MAP.md` | "`addons/` — 57 Odoo 19 modules" | 58 folders in `addons/`, plus 2 under `faizy/`: 60 registered modules | VERIFIED |
| `REPO_MAP.md` | Platform layer: 17 modules, 2 with tests; "30 of the 33 foundation, platform and product modules have no test file" | 18 platform modules; `mumtaz_tenant_manager` and `mumtaz_control_plane` now carry tests; see `registry.yaml` for current counts | VERIFIED |
| `REPO_MAP.md` | "Nothing in this repository names IG2" | `sites/ig2.mumtaz.digital/`, `addons/mumtaz_ceo_dashboard` and `addons/mumtaz_media_buying/scripts/seed_demo.py` do | VERIFIED |
| `REPO_MAP.md` | "Pharma — no pharma module exists in this repository" | True for `main`; the modules exist on `pharma-*` branches | REPORTED |
| `REPO_MAP.md` | Portal shells and organisation model listed as plain duplicates | `mumtaz_organization` is a partner directory, not a second tenancy registry; `mumtaz_customer_portal` serves the tenant's own customers | VERIFIED |
| `README.md`, `CLAUDE.md` | "Odoo modules (57)" / "57 Odoo 19 Community addons" | 58 in `addons/` | VERIFIED |
| `CLAUDE.md` | "Deploys go to `main` — the VPS pulls main" | True for the delivery console only; the native Odoo checkouts are reported on a feature branch | REPORTED |
| `docs/erp/architecture/MODULE_DEPENDENCY_MAP.md` | "No dependency cycles" | True for manifests; `mumtaz_tenant_manager` references models of modules that depend on it | VERIFIED |
| `addons/mumtaz_website_builder/README.md` and manifest | Seven blocks; "no custom controller" | Ten blocks after PR #187; a controller exists | VERIFIED |
| `docs/infrastructure-audit/*` | Paths under `apps/` | Translated by the table in `sites/README.md` | VERIFIED |

## 7. Customer-specific data in reusable or public code (decision P-15)

Paths only; the data is not repeated here. All VERIFIED to exist at these paths.

| Path | What kind of data | Why it should move |
|---|---|---|
| `addons/mumtaz_ceo_dashboard/static/src/js/ceo_dashboard.js` | The external client's name and currency hard-coded in a module named as reusable | A reusable module must not carry one client's identity |
| `addons/mumtaz_media_buying/scripts/seed_demo.py` | The external client's database name as the seed target | Same; and a seed script must never default to a client's live database |
| `addons/c2p_master_agent/models/master_agent.py` | Staff names, client names, an active proposal and a price list in source | Belongs in a private repository or in database records |
| `addons/c2p_project_tracker/hooks.py` | Project identifiers, client names and staff email addresses in an install hook | Move to data files outside the public repository |
| `addons/c2p_command_center/models/command_center.py` | A role mailbox, a board name, a fixed time zone and stage names as constants | System parameters, so the module is not tied to one company |
| `sites/zaki.mumtaz.digital/node-app/agents/zaki.js`, `agents/farid.js`, `odoo/models.js` | One named client's company, bank account codes and a supplier-specific tool | Retire with the application; do not carry into the canonical ZAKI |
| `platform/ops/install/00-foundation.sh`, `ops/platform-routing/setup_master_admin.sh` | The owner's name and administrator login; a literal fallback credential in the second | Parameters, and no fallback credential |
| `sites/erp.mumtaz.digital/legacy-spa/deploy.sh` | Literal fallback credentials | Retire with the abandoned page |
| `c2p-delivery-system/docs/05-build-log.md`, `docs/07-mumtaz-c2p-crm-findings.md`, `delivery_api/README.md` | Database names, user and lead counts, staff names, internal CRM rules | Private operations notes |
| Six pages under `sites/mumtaz.digital/site/`, `CLAUDE.md`, `deploy/jewel-staging/README.md`, `c2p-delivery-system/deploy/finish.sh`, `ops/deployment/deploy-phase-a.sh`, `wordpress-sites/deploy/setup-lemp.sh` | The server's address | Use hostnames; keep the address in private operations notes |
| Branch `claude/resume-help-95ne9v` (not on `main`) | The external client's legal name, sister company, customer list and named finance staff | REPORTED by the audit; that client's code and documents belong in its own private repository |

Removing a value from the current files does not remove it from git history or from copies already made. The owner decided on 21 Nov 2026 to keep the repository public (audit D-01); this list is what that decision leaves exposed.
