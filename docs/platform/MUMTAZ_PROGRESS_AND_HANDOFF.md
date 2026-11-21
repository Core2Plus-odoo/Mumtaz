# Progress and handoff

Milestone 1 of the Master Platform Consolidation & Development Directive,
21 Nov 2026. Branch `ccr-620c243b-p9qlq1`, based on `main` at `ff1c797`.

**In one paragraph.** The baseline is done and written down, and the first
functional milestone works for real on a development rig: an organization
registers, chooses Mumtaz ERP, is approved and given a trial entitlement, a
separate staging database is created and verified, and its administrator
signs in through a one-time link. The same journey on a server that is not
allowed to create databases ends with no database and no "active" tenant —
before this work it ended with a tenant marked active and nothing behind it.
**Nothing was deployed. No server, production database, live website or
customer system was touched or inspected.**

Status words: **VERIFIED** (read in code or run on the local Odoo 19 +
PostgreSQL 16 rig) · **REPORTED** (repository documents; includes everything
about the live server) · **PROPOSED** · **UNKNOWN**.

## 1. What was inspected

| Area | How | Result in |
| --- | --- | --- |
| Maps and registries: `REPO_MAP.md`, `registry.yaml`, `registry/classification.json`, `sites/`, `docs/erp/`, `docs/infrastructure-audit/`, `docs/jawhar/` | Read | `README.md` (this folder), `MUMTAZ_REPOSITORY_CONSOLIDATION.md` |
| All 60 Odoo modules: manifest, layer, dependencies in manifests and in code, tests, hard-coded customer data | Read-only review of every module | `MUMTAZ_MODULE_REGISTRY_REVIEW.md` |
| Every ZAKI, AI and CFO implementation (three applications, eight module families) | Read-only review | `MUMTAZ_AI_ARCHITECTURE.md` |
| Every website and brand source (two Odoo website modules, three static copies, twelve token sources) | Read-only review, re-checked after PR #187 | `MUMTAZ_WEBSITE_IMPLEMENTATION.md`, `MUMTAZ_DESIGN_SYSTEM.md` |
| The SaaS control plane: tenant manager, control plane, organization and signup modules, SSO, subdomain routing | Read, then **run** | `MUMTAZ_SAAS_CONTROL_PLANE.md` |
| Deploy scripts, workflows and what the server is reported to run | Read | `MUMTAZ_DEPLOYMENT_REGISTRY.md` |

Not inspected, because this session cannot reach it: the server, any
database on it, the live websites, nginx, DNS, backups.

## 2. What was verified (by running it)

| Finding | Evidence |
| --- | --- |
| The existing provisioner could create an isolated tenant database whose administrator can sign in | Run with the `starter` bundle on the rig, before any change |
| …but it put the tenant registry and the bundle price list inside the customer database | `mumtaz_tenant_manager` installed in the tenant database; five bundle rows present |
| …and it depended on the database manager being exposed, and ignored a failed initialisation | Read in `odoo/service/db.py` (Odoo 19.0) and the provisioner |
| A dry run marked the tenant **active**; the wizard's "Dry Run" box was never read | Read in code; now covered by tests that fail on the old behaviour |
| No link existed between organization signup and tenant provisioning; no plan was seeded | Read in code and data |
| After slice 1 the journey works end to end | `scripts/tenant_journey_ci.sh`, §5 |

## 3. What was developed

| Change | Module / file |
| --- | --- |
| Provisioning result carries `simulated`; **only a real, verified run activates a tenant**; one method records every outcome | `mumtaz_tenant_manager` — `services/provisioning.py`, `models/tenant_provisioning.py` |
| The wizard's "Dry Run" box is honoured: ticked never creates anything; unticked creates a real database or refuses with no state change | `wizards/provision_wizard.py` |
| Database creation no longer needs the database manager exposed; initialisation is checked; a verification step confirms every module of the profile and the administrator | `services/provisioning.py` |
| No operator-typed password: a random one nobody sees, then Odoo's own one-time invitation link for the administrator, stored for platform administrators only | same; field `access_link` |
| A failed run never drops a database; it flags the leftover and blocks a blind retry | field `database_needs_cleanup` |
| Staging tenants: `environment` field, database name must start with `stg_` | `models/tenant_provisioning.py` |
| Only platform administrators can start provisioning (the manager group could, over RPC) | `_check_can_provision` |
| Install profile `mumtaz_erp`: contacts, CRM, sales, purchasing, inventory, accounting, financial reports; no control-plane module | `data/mumtaz_bundle_data.xml` |
| Product catalogue with an evidence-based status; plans belong to a product | `mumtaz_control_plane` — `models/product.py`, `data/product_catalogue.xml` |
| Registration request: `new → approved → provisioning → ready / failed`; approval creates the organization (`res.partner`), the staging tenant record and the trial subscription; provisioning is refused without entitlement | `models/signup_request.py`, views, menu, access rules |
| Public registration route, **closed by default**, that can only create a pending request (hourly cap, honeypot, no enumeration) | `controllers/signup.py` |
| End-to-end check and its CI step | `scripts/tenant_journey_ci.sh`, `scripts/tenant_journey/*.py`, `.github/workflows/platform-odoo-install.yml` |
| Sixteen deliverables: fourteen documents here, the decisions appended to the existing register, this handoff | `docs/platform/`, `docs/erp/project/DECISION_REGISTER.md` |

Versions: `mumtaz_tenant_manager` and `mumtaz_control_plane`
`19.0.1.0.0 → 19.0.1.1.0`. Schema changes are additive (new columns, two new
tables, new seed records). No module was renamed; no existing record is
rewritten; the five older bundles are untouched.

## 4. Files changed

- `addons/mumtaz_tenant_manager/` — `__manifest__.py`, `services/provisioning.py`, `models/tenant_provisioning.py`, `wizards/provision_wizard.py`, `data/mumtaz_bundle_data.xml`, `views/mumtaz_tenant_views.xml`, `tests/` (new)
- `addons/mumtaz_control_plane/` — `__manifest__.py`, `__init__.py`, `models/__init__.py`, `models/product.py` (new), `models/signup_request.py` (new), `models/tenant_commercial.py`, `controllers/` (new), `data/product_catalogue.xml` (new), `views/product_views.xml` (new), `views/signup_request_views.xml` (new), `views/menus.xml`, `security/ir.model.access.csv`, `tests/` (new)
- `scripts/tenant_journey_ci.sh`, `scripts/tenant_journey/journey.py`, `scripts/tenant_journey/open_workspace.py` (new)
- `.github/workflows/platform-odoo-install.yml` — one added step and two path triggers
- `registry.yaml` (regenerated), `README.md`, `REPO_MAP.md` (module count, IG2 note), `sites/app.mumtaz.digital/README.md`, `docs/erp/BACKLOG.md`, `docs/erp/project/DECISION_REGISTER.md`, `docs/erp/quality/RELEASE_CHANGELOG.md`
- `docs/platform/` — fifteen files (new)

## 5. Tests executed and results

All on the local rig: Odoo 19.0 Community (commit `da89d33`), PostgreSQL 16,
throwaway databases that the scripts created and dropped.

| Test | Command | Result |
| --- | --- | --- |
| Unit tests, fresh database | `odoo-bin -i mumtaz_tenant_manager,mumtaz_control_plane --test-enable --test-tags /mumtaz_tenant_manager,/mumtaz_control_plane` | **0 failed, 0 errors of 30 tests** (12 + 18) |
| Fresh install, upgrade, tests, no ERROR line in the log — the two modules and three that depend on them | `MODULES=mumtaz_tenant_manager,mumtaz_control_plane,mumtaz_billing_stripe,mumtaz_subdomain_routing,mumtaz_sme_profile scripts/platform_ci.sh` | **5 of 5 installed; 30 tests, 0 failed; passed** |
| Upgrade path: install both modules from `origin/main`, insert an active tenant row, upgrade to this branch with tests | `odoo-bin -u …` against a database installed from a `main` worktree | **exit 0; 30 tests, 0 failed; 0 ERROR lines**; the old tenant kept `state=active` with an empty `environment`; new profile, six products and the trial plan were created; both modules at `19.0.1.1.0` |
| Tenant journey, provisioning **disabled** | `scripts/tenant_journey_ci.sh` (first half) | request back to `approved`, tenant `draft`, **no database created** |
| Tenant journey, provisioning **enabled**, database manager hidden (`--no-database-list`) | same script (second half) | request `ready`, tenant `active`, database `stg_journey_ci_<id>` exists, link issued, no password left on the record |
| Isolation, read from PostgreSQL | same script | no control-plane tables in the tenant database; no ERP tables in the control database; the tenant administrator is not a control-plane user; exactly one internal user in the tenant |
| Open the workspace over HTTP | same script → `open_workspace.py` | set-password page opens; password accepted; session is uid 2 in the tenant's own database; `/odoo` loads; all nine modules of the profile installed; the link is dead after first sign-in and a replay signs nobody in; a wrong password is refused |
| Whole journey script | `scripts/tenant_journey_ci.sh` | **passed**, about two minutes |
| Lint | `flake8 addons/ tools/scrapers/` | clean |
| `sudo()` labels | `scripts/check_sudo.py` | OK, 296 of 296 labelled |
| Module registry and layering | `scripts/module_registry.py --check` | OK, 60 modules, 1 known violation (unchanged) |
| Full platform CI, every non-jewellery module in one database | `scripts/platform_ci.sh` | **43 of 43 modules installed; upgrade with tests: 110 tests, 0 failed; passed** |

**Not run:** anything on a server; the Jawhar suite (`scripts/jewel_ci.sh` —
no Jawhar module was changed); the GitHub workflow itself (it runs on the
pull request); a browser rendering of the new screens; load, restore or
penetration tests.

## 6. Risks

| Risk | Where it stands |
| --- | --- |
| Real provisioning creates databases on the PostgreSQL server that holds client ledgers | Off unless `MUMTAZ_REAL_PROVISIONING=1` is set in the service environment. Not to be set on a production instance before backups are verified (P-03, P-17) |
| The upgrade adds columns and seed records to a control database nobody here could inspect | Additive only; tested from `main`. Take a backup first; run on staging first |
| The set-password link is a credential until first use (valid six days by Odoo's default) | Visible to platform administrators only; not logged; dies on first sign-in. Email delivery is not built |
| The five older bundles still put control-plane modules in customer databases and name an Enterprise-only module | Documented, not edited (`noupdate` data possibly in use). Use `mumtaz_erp` |
| The public route exists | Closed by default; creates only a pending request; needs captcha and email verification before it is opened (P-08) |
| A general ERP install takes about two minutes | Use the queue, not the wizard, and give the scheduled worker enough time |
| `main` moves quickly (several merges a day from other sessions) | Re-run the three scripts after merging `main`; `registry.yaml` is regenerated, never hand-merged |
| Everything about the server is REPORTED | The read-only V-pack in `docs/infrastructure-audit/13_REMEDIATION_BACKLOG.md` is still the first server-side step |

## 7. Remaining work

The ordered backlog (PL-00 …) is in `MUMTAZ_DEVELOPMENT_ROADMAP.md`. The
next slices that need no owner decision:

1. Registry schema and profile checks in CI, so a bundle that names a missing module or pulls a control-plane module into a customer database fails the build (PL-01).
2. Tenant lifecycle for staging trials: expiry → suspend → archive, with no automatic deletion (PL-03).
3. Email and resend of the set-password link (PL-04).
4. ZAKI step 1: correct the finance snapshot (company scope, cash, revenue basis) with tests (PL-12).
5. Website structure: tokens, focus states, RTL rules, self-hosted fonts (PL-13).

## 8. Decisions that need the owner

Seventeen, P-01 … P-17, in `docs/erp/project/DECISION_REGISTER.md`. The five
that unblock the most:

| ID | Question |
| --- | --- |
| P-02 | Which Odoo instance and database is the control plane? |
| P-03 | Where is real provisioning enabled first — and are backups verified there? |
| P-01 | Is database-per-tenant the only model (retire the company-per-org signup)? |
| P-09 | One price list. The website module now shows prices that no plan record carries |
| P-10 | Where does the Odoo website run? A document on `main` names the ERP database; no decision records it |

Still open from earlier work, all on the owner's side: change the weak Odoo
administrator password; delete branches `claude/html-creation-7knykl` and
`claude/faizy-document-access`; run the read-only V-pack on the server; back
up `faizy_prod` and upgrade `faizy_core` there; name an owner per system.

## 9. Report in the ERP programme's format (`docs/erp/DEVELOPMENT_STANDARDS.md` §7.2)

- **TASK** — Prove "register organization → choose Mumtaz ERP → assign entitlement → provision isolated staging tenant → open ERP workspace" with real code and tests; baseline and consolidate the platform documentation.
- **REPOSITORY STATUS** — Branch `ccr-620c243b-p9qlq1` on `main@ff1c797`. Two modules changed, both platform layer; no cross-layer dependency added.
- **PROCESS IMPACT** — Lead-to-tenant only (control database). No accounting, stock or sales posting logic touched. Customer databases receive standard Odoo apps and `mumtaz_financial_reports`.
- **PLAN** — As §3.
- **IMPLEMENTED** — As §3 and §4.
- **VERIFIED** — As §5. Nothing is claimed that was not run.
- **RECONCILIATION** — Not applicable: no financial or stock figure is produced.
- **DECISIONS / BLOCKERS** — P-01 … P-17. Production enablement is blocked on P-02, P-03, P-17 and on the audit's backup batch.
- **NEXT ACTION** — Owner: answer P-02 and P-03, run the V-pack. Engineering: PL-01, PL-03, PL-04.
