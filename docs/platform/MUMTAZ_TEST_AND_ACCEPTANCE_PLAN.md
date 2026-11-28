# Mumtaz platform test and acceptance plan

Written 21 Nov 2026 on branch `ccr-620c243b-p9qlq1` (base `main` at `ff1c797`).

This plan covers the platform: control plane, provisioning, product
integration, website. It sits above, and does not repeat:

- [`docs/erp/quality/TEST_MIGRATION_DEPLOYMENT_STRATEGY.md`](../erp/quality/TEST_MIGRATION_DEPLOYMENT_STRATEGY.md)
  — test layers, reconciliation controls and the migration method for the ERP;
- [`docs/erp/quality/RELEASE_GATE_CHECKLIST.md`](../erp/quality/RELEASE_GATE_CHECKLIST.md)
  — the per-release gate table;
- [`docs/erp/BACKLOG.md`](../erp/BACKLOG.md) — acceptance for ERP items #1–#20;
- [`docs/infrastructure-audit/13_REMEDIATION_BACKLOG.md`](../infrastructure-audit/13_REMEDIATION_BACKLOG.md)
  — validation for each V-, S-, B-, O-, A- item.

Backlog items PL-00…PL-21 and phases 0–8 are defined in
[`MUMTAZ_DEVELOPMENT_ROADMAP.md`](MUMTAZ_DEVELOPMENT_ROADMAP.md). Decisions
P-01…P-17 are in [`docs/erp/project/DECISION_REGISTER.md`](../erp/project/DECISION_REGISTER.md).

## 1. Conclusion

1. **Six automated layers exist and run in CI.** The newest,
   `scripts/tenant_journey_ci.sh`, proves the first platform milestone against
   a real database and a real HTTP server, including the negative case: a
   server that may not create databases ends the journey with no database and
   no active tenant.
2. **All of that evidence is from disposable databases.** No test has run on a
   Mumtaz server, no backup has been restored, and no load or accessibility
   test exists.
3. **Most platform modules still have no tests.** `registry.yaml` records the
   count per module; statutory e-invoicing and Stripe billing are at zero.
4. **A claim is VERIFIED only with a command and its recorded output.** A page
   that renders is not a test. A dry run is not a provisioned tenant.
5. **Nothing reaches a server without the gates in section 5**, and no test is
   skipped, disabled or quarantined to make a run green.

## 2. Status legend

| Tag | Meaning |
|---|---|
| **VERIFIED** | The command named was run on 21 Nov 2026, or the fact was read in the cited file. |
| **REPORTED** | Stated in a repository document; not re-run here. |
| **PROPOSED** | A test or gate that does not exist yet. |
| **UNKNOWN** | Needs a CI run, server evidence or an owner decision. |

## 3. Test layers that exist today

Each row gives the command a developer runs. CI runs the same scripts.

| Layer | Command | Workflow | What it proves (VERIFIED by reading the script or workflow) | What it does not cover |
|---|---|---|---|---|
| **Lint and static checks** | `flake8 addons/ tools/scrapers/` · `python3 scripts/check_sudo.py addons` · `python3 scripts/module_registry.py --check` | `ci.yml` (also manifest validation, XML validation, bandit, secrets scan, dependency audits) | Style; every `sudo()` carries a `# sudo: <reason>` label; every module is classified; no new upward dependency between layers; `registry.yaml` is current | Whether a `sudo()` reason is true. Ownership, install profiles, bundle contents, soft dependencies (`MUMTAZ_MODULE_REGISTRY_REVIEW.md` §8.2). `platform/`, `sites/` and `scripts/` are outside flake8 |
| **Fresh install, upgrade and module tests** | `ODOO_PATH=… bash scripts/platform_ci.sh` (subset: `MODULES=a,b`) | `platform-odoo-install.yml` | Every non-Jawhar addon installs into one clean Odoo 19 database, upgrades, and its own tests pass; any `ERROR` or `CRITICAL` log line fails the run | It installs everything together, so it proves co-installability, not any real install profile, and it hides missing dependencies. Modules with no tests are only installed. No upgrade from an **older** version (see section 6) |
| **Tenant journey, end to end** | `ODOO_PATH=… bash scripts/tenant_journey_ci.sh` | a step of `platform-odoo-install.yml` | See section 3.1 | See section 3.1 |
| **Jawhar suite** | `ODOO_PATH=… bash scripts/jewel_ci.sh` | `jewel-odoo-tests.yml` | The Jawhar modules install on a clean database, their suite passes, and the synthetic demo data seeds | Jawhar under the control plane (no profile, no bridge — PL-11). Devices: camera try-on and voice are not tested by automation (ERP backlog #19) |
| **Jawhar web app** | `npm run typecheck && npm test && npx vite build` in `apps/jawhar-web` | `jawhar-web.yml` | Types, unit tests, a production build with a non-empty entry page | A browser session against a live Odoo |
| **Faizy** | `python3 faizy/odoo/tools/validate_modules.py` and the other validators; `flake8 faizy/odoo …` | `faizy-ci.yml` | Manifests, XML, access files, view fields, view schemas, plan price matrix, lint | **It does not install Odoo.** The `faizy_core` tests (record rule on documents) run only when someone runs them by hand on an Odoo 19 database |
| **Agency OS (Delivery OS)** | — | `ci.yml` runs a dependency audit only | Known CVEs in its requirements | Its behaviour. Its tests are not run in CI (audit A-08) |

Whether the latest CI run of each workflow is green is UNKNOWN from this
document; read it on the pull request.

### 3.1 What the tenant journey proves, exactly

`scripts/tenant_journey_ci.sh` builds a throwaway control database, installs
`mumtaz_tenant_manager` and `mumtaz_control_plane`, and then runs the journey
twice through the same model methods that the operator's buttons and the
scheduled worker call. Nothing is stubbed. Every Odoo process is started with
`--no-database-list`, the way a multi-tenant server should run.

| Stage | Check | Read from |
|---|---|---|
| **Dry path** (`MUMTAZ_REAL_PROVISIONING=0`) | Registration is recorded as a pending request; no tenant exists before approval | control database, through the ORM |
| | Approval creates a staging tenant in draft; `erp_access` is granted; `zaki_access` is not | feature-access service |
| | After the worker runs: the request is back to "approved", the tenant is not active, the log says nothing was created | ORM |
| | **No database was created** | `pg_database`, by `psql` |
| **Real path** (`MUMTAZ_REAL_PROVISIONING=1`) | Same registration and approval checks | ORM |
| | After the worker runs: request "ready", tenant "active", database exists, a set-password link was issued, no password is left on the control-plane record | ORM and `exp_db_exist` |
| **Isolation** | The tenant database holds no `mumtaz_tenant`, `mumtaz_subscription` or `mumtaz_plan` table | `to_regclass` in the tenant database |
| | The control database holds no `crm_lead` or `account_move` table | `to_regclass` in the control database |
| | The tenant administrator is not a user of the control database | `res_users` in the control database |
| | The tenant database has exactly one internal user | `res_users` in the tenant database |
| **Workspace over HTTP** | The link is Odoo's own invitation URL; the page opens and is for the administrator's login | HTTP GET |
| | A chosen password is accepted; the session is uid 2, in the tenant's own database, with the administrator's login | `/web/session/get_session_info` |
| | The web client loads at `/odoo` | HTTP GET |
| | Every module of the install profile is installed; there is one company | RPC as the signed-in administrator |
| | The chosen password signs in on its own | `/web/session/authenticate` |
| | **The link is dead after first sign-in**; replaying it signs nobody in and does not change the password | HTTP GET and POST in a fresh session |
| | A wrong password is refused | `/web/session/authenticate` |

What it does **not** prove:

- Anything about a Mumtaz server: its PostgreSQL role, its proxy, its worker
  time limits, its mail. A general ERP database takes minutes to build, so the
  cron worker's time limit on the real server matters and is untested.
- Subdomain routing. The script reaches the tenant by `--db-filter`, not
  through `mumtaz_subdomain_routing`.
- Two tenants side by side. Isolation is shown between the control database
  and one tenant; a second tenant is not created.
- Database-level isolation between tenants. One PostgreSQL role is used for
  everything, as on the server today (REPORTED). See PL-18.
- Email delivery of the link, trial expiry, billing, localisation.
- Concurrency: two requests provisioned at once.

### 3.2 Unit tests added with Slice 1 (VERIFIED: 30 tests, 0 failed, fresh database)

| File | What the tests hold in place |
|---|---|
| `addons/mumtaz_tenant_manager/tests/test_provisioning.py` | The "Dry Run" box always wins, even on a server allowed to create databases. A real run is refused when the server disallows it and changes nothing. Only a verified real run activates a tenant. A failure leaves draft and flags a leftover database, and a later failure does not clear the flag. A Platform Manager cannot provision and cannot read the set-password link. Staging database names carry `stg_`. The ERP profile's modules all exist and its dependency closure contains no control-plane module |
| `addons/mumtaz_control_plane/tests/test_signup_journey.py` | The catalogue: only Mumtaz ERP is open; a planned product cannot be opened. A plan must belong to its product. Approval creates organization, staging tenant and trial, and the entitlement comes from the shared resolver. Tenant codes do not collide and do not take reserved names. No provisioning before approval or without entitlement. "Ready" only after a real run; a dry run does not make a request ready; a failed run blocks a blind retry. Only a Super Admin approves and provisions. Ordinary staff and portal users cannot read requests. The public intake is closed by default, only creates a pending request, deduplicates, drops honeypot submissions and has an hourly cap. The HTTP route answers only when switched on |

The real provisioner cannot run inside an Odoo `TransactionCase` (it creates a
database and commits), so the unit tests use a stand-in and the journey script
exercises the real one.

## 4. Acceptance criteria

Negative tests are listed first in each group. They are the ones that fail
silently when a guard is removed.

### 4.1 Phase 2 — control plane (Slice 1 and PL-03, PL-04, PL-05, PL-19)

| # | GIVEN | WHEN | THEN | Status |
|---|---|---|---|---|
| CP-N1 | a server not allowed to create databases | a request is approved, provisioned and the worker runs | no database exists; tenant is draft; request is "approved", never "ready" | VERIFIED — journey dry path; `test_dry_run_does_not_make_the_request_ready` |
| CP-N2 | a tenant whose subscription is suspended | "Provision" is pressed | refused; nothing is queued | VERIFIED — `test_no_provisioning_without_entitlement` |
| CP-N3 | a product whose status is "planned" | someone tries to open it to requests, or posts its code to the public route | refused | VERIFIED — `test_planned_product_cannot_be_opened`, `test_public_intake_only_ever_creates_a_pending_request` |
| CP-N4 | an ordinary internal user, or a portal user | they read a registration request | access error | VERIFIED — `test_ordinary_staff_cannot_see_requests` |
| CP-N5 | a Platform Manager | they call the queue method over RPC | access error; tenant unchanged | VERIFIED — `test_platform_manager_cannot_provision` |
| CP-N6 | the public route with its switch off | anything is posted | an error; no record | VERIFIED — `test_route_is_closed_until_switched_on` |
| CP-N7 | a used set-password link | it is opened again by anyone | nobody is signed in; the password is unchanged | VERIFIED — journey, workspace stage |
| CP-N8 | tenant A's administrator | they try to sign in to tenant B, or to the control database | refused | PROPOSED — needs a second tenant in the journey script |
| CP-N9 | a run that created the database and then failed | "Provision" is pressed again | refused until a person has dealt with the database; the database is never dropped by code | VERIFIED — `test_failed_run_blocks_a_blind_retry`, `test_failure_leaves_draft_and_flags_the_leftover_database` |
| CP-P1 | a server allowed to create databases | the full journey runs | section 3.1, real path | VERIFIED on a development rig; UNKNOWN on any server |
| CP-P2 | a trial past its end date (PL-03) | the lifecycle cron runs | subscription expired, tenant suspended, database still present, host no longer routes | PROPOSED |
| CP-P3 | a provisioned tenant (PL-04) | provisioning ends | one email with the link is queued; the link is in no log; "resend" issues a new link | PROPOSED |
| CP-P4 | the public route open (PL-05) | an unverified address submits; one address bursts | no request reaches reviewers before confirmation; the burst is refused at the proxy | PROPOSED |
| CP-P5 | the target server's staging (PL-19) | `tenant_journey_ci.sh` runs there | passes; the rollback has been rehearsed | PROPOSED; blocked by PL-00, P-02, P-03 |

### 4.2 Phase 1 — governance (PL-01, PL-02, PL-17)

| # | GIVEN | WHEN | THEN | Status |
|---|---|---|---|---|
| GV-N1 | a bundle naming a module that is neither in `addons/` nor in Odoo 19 Community | `module_registry.py --check` | fails and names the bundle and the module | PROPOSED |
| GV-N2 | a tenant profile whose dependency closure reaches a control-plane module | the same check | fails | PROPOSED for all bundles; VERIFIED for `mumtaz_erp` by `test_erp_profile_modules_exist_and_stay_out_of_the_control_plane` |
| GV-N3 | a reusable module containing a client name, a staff address or a database name | the hardcoding lint | fails unless the line is on the allow-list with a reason | PROPOSED |
| GV-N4 | a new module with no entry in `registry/classification.json` | CI | fails | VERIFIED — existing check |
| GV-P1 | each corrected bundle | provisioned by the journey script | no control-plane table in the tenant; no module skipped | PROPOSED |

### 4.3 Phase 3 — ERP commercial readiness

Acceptance is in ERP backlog #5, #8, #9, #10, #11, #12 and the ERP roadmap's
wave exit evidence. Added here for the platform:

| # | GIVEN | WHEN | THEN | Status |
|---|---|---|---|---|
| ERP-P1 | a registration from a UAE organization (PL-06) | provisioned | chart of accounts, VAT taxes and the bilingual invoice layout exist; no tax rate is hard-coded in the repository | PROPOSED; blocked by ADR-006, D-06, P-06 |
| ERP-N1 | two tenants | a user of one requests the other's record by id | not reachable: different database | PROPOSED (same test as CP-N8) |

### 4.4 Phase 5 — product integration (PL-07, PL-09, PL-11, PL-12)

| # | GIVEN | WHEN | THEN | Status |
|---|---|---|---|---|
| PI-N1 | tenant A's agent token | used with tenant B's code | refused | PROPOSED |
| PI-N2 | a sign-on token minted for tenant A | presented to tenant B; presented twice; presented after expiry | refused each time | PROPOSED |
| PI-N3 | the control plane unreachable | a paid feature is called | fails closed after the stated grace period | PROPOSED |
| PI-N4 | a portal user or a non-accounting user | calls a ZAKI endpoint | refused | VERIFIED for `/zaki/api/snapshot` (`mumtaz_zaki/tests/test_snapshot_access.py`); PROPOSED for `/zaki/api/ask` |
| PI-N5 | a model reply containing a number the tools did not return | grounding check | the sentence is discarded | VERIFIED for Jawhar (its suite); PROPOSED for ZAKI |
| PI-N6 | two companies in one database | each user asks ZAKI for a snapshot | each sees only their own company's figures | PROPOSED — the current connector sums all companies under `sudo()` |
| PI-P1 | a Jawhar request | approved and provisioned | the Jawhar modules are installed, demo and website modules are not, `jewel_ci.sh` stays green | PROPOSED |
| PI-P2 | every AI call, including a refusal | — | exactly one run-log row with model, tokens and policy level; usage is written against the tenant | PROPOSED |

### 4.5 Phase 4 — website and design (PL-13, PL-14, PL-15)

| # | GIVEN | WHEN | THEN | Status |
|---|---|---|---|---|
| WB-N1 | the module installed on a database with an existing homepage | install or upgrade | the homepage, menus and published pages are unchanged | VERIFIED for a fresh database by the module's footprint test; PROPOSED for a database with an existing site |
| WB-N2 | a visitor | opens the unpublished preview page | not found | VERIFIED — module test |
| WB-N3 | a form submission without consent, or with the honeypot filled | posted | refused; other website forms are unaffected | VERIFIED — module tests |
| WB-P1 | the page in Arabic | rendered | the layout mirrors; Arabic text has no negative letter-spacing; an Arabic font is loaded | PROPOSED |
| WB-P2 | every text and background pair | automated accessibility check | contrast ≥ 4.5:1; visible focus on every control; reduced motion respected | PROPOSED |
| WB-P3 | a partner brand override | applied | a pair below 4.5:1 is refused | PROPOSED |
| WB-P4 | the price shown on the site | compared with the one price source | equal; no price exists in any other file | PROPOSED; blocked by D-11, P-09 |

### 4.6 Phases 6–8

Marketplace (PL-20), white-label and further products get their acceptance
tests when P-12 and P-14 are answered. One rule already applies: a tenant
never reads another tenant's database, and each new product enters the
catalogue as "planned" until a recorded test moves it.

## 5. Release gates before anything reaches a server

These apply to every step that changes a server, whatever its size. They add
to `RELEASE_GATE_CHECKLIST.md`; they do not replace it.

| Gate | Requirement | Evidence to record |
|---|---|---|
| **Backup** | A backup of every database and filestore the step can touch, taken for this step, copied off the host (audit B-02) | File names, sizes, checksums, where they are |
| **Restore test** | At least one of those backups restored on another machine, neutralised, and started (audit B-03). A backup that has not been restored is not called recoverable | Module list and a few row counts from the restored copy |
| **Staging run** | The change and `tenant_journey_ci.sh` run on the target server's staging first, with the same Odoo package and PostgreSQL as production | The script's output |
| **Rollback** | Written before the step and rehearsed on staging: what is switched off, what is restored, how long it takes | The procedure and the rehearsal result |
| **Owner approval** | A row in the approval log, [`docs/infrastructure-audit/15_DECISIONS_AND_APPROVALS.md`](../infrastructure-audit/15_DECISIONS_AND_APPROVALS.md) §3: scope, systems, backup reference, window, approver, date | The row |
| **IG2** | Nothing is applied to the IG2 instance, and no module it uses is changed on its checkout, without a compatibility test on a copy of its database and the client's agreement | Test result and the agreement |
| **Independent systems** | Faizy and the C2P internal ERP are changed only through their own branch and procedure | — |
| **Green means green** | No test is skipped, disabled or quarantined to get a green run. A failing test is fixed or the change does not ship. "NOT RUN" is written as "NOT RUN" | CI run link |
| **No secrets** | No password, token, key or sign-in link in a commit, a log uploaded by CI, or a report | Secrets scan in `ci.yml` |

Enabling real provisioning on a server (PL-19) needs all of the above and, in
addition: the control database identified (P-02); the cron worker's time limit
raised to cover a full ERP install; the database manager denied at the proxy
(audit S-09); a list of the databases the first run may create.

## 6. Upgrade and migration testing

### 6.1 Rules

1. **A module version bump accompanies any change to its data model, its data
   files or its views.** `registry.yaml` is regenerated in the same change
   (`python3 scripts/module_registry.py --write`).
2. **Never rename an installed module directly.** A rename needs a migration
   script (model data, tables, external identifiers) and an inventory of every
   database where the module is installed. Without the inventory (audit V-11)
   no rename is planned.
3. **`noupdate` data does not change on upgrade.** A corrected record in a
   `noupdate` file reaches new installs only. Existing databases need a
   migration script or a manual, approved edit. State which in the pull request.
4. **A new required field needs a default or a migration** that is right for
   rows that already exist. If no honest value exists, the field stays optional
   (as `environment` on tenants created before the field existed).
5. **Nothing is deleted by an upgrade.** Data that is no longer used is left in
   place and listed.

### 6.2 Procedure: upgrade from `main` to the branch

Run for every pull request that changes a module's models, data or views.

| Step | Action |
|---|---|
| 1 | Check out `origin/main` in a separate worktree |
| 2 | Create a throwaway database and install the affected modules from the `main` worktree's `addons/` |
| 3 | Insert a few rows that stand for existing production data (for example a tenant created before the change) |
| 4 | Run `odoo-bin -u <modules> --test-enable --test-tags /<module>,…` with the branch's `addons/` |
| 5 | Require: exit code 0; the test summary shows 0 failed, 0 errors; no `ERROR` or `CRITICAL` log line; the module versions in `ir_module_module` are the new ones |
| 6 | Inspect the rows from step 3: unchanged where they should be, and new fields hold an honest value (empty rather than a guessed default) |
| 7 | Confirm new records from `noupdate` files were created and existing ones were not overwritten |
| 8 | Drop the database and remove the worktree. Record the commands and counts in the changelog |

The result of this procedure for Slice 1 is recorded separately in the
changelog.

### 6.3 Tenant and client data migration

The method is `TEST_MIGRATION_DEPLOYMENT_STRATEGY.md` §11.3. Two platform
migrations are foreseen and neither may start before its decision:

| Migration | Decision | Extra acceptance |
|---|---|---|
| `mumtaz.org` rows → `mumtaz.tenant` (PL-16) | P-01 | Row counts before and after match; every organization has exactly one tenant record; no company created by signup is deleted |
| Module merges and retirements (`mumtaz_base` → `mumtaz_core`, portals, CFO stack) | D-13, P-16 | Run on a copy of each database where the module is installed; table and column names unchanged; record counts equal |

## 7. Evidence rule

- A claim is **VERIFIED** only when the command and its output are recorded in
  [`docs/erp/quality/RELEASE_CHANGELOG.md`](../erp/quality/RELEASE_CHANGELOG.md):
  the exact command, the test count, failures, errors.
- "It rendered", "the screen looks right" and "the dry run passed" are not
  tests of a working product.
- A test that could not run is reported as **NOT RUN** with the reason. It is
  never turned into a pass.
- A product's status in the catalogue (`mumtaz.product.status`) changes only
  with an entry in its "Basis for the Status" field that names the test or the
  deployment.
- Server facts stay **REPORTED** until the verification pack output is on file.

## 8. Known gaps in test coverage

| Gap | Evidence | Where it is planned |
|---|---|---|
| Most platform and product modules have no tests | `registry.yaml` test-file counts; `MUMTAZ_MODULE_REGISTRY_REVIEW.md` §4 | Registry check 11 (tests required unless listed in `known_untested`), PL-01 |
| Statutory e-invoicing (UAE, KSA, PK) is untested and posts with network calls | `mumtaz_einvoicing`: 0 test files | ERP backlog #11 |
| Stripe billing is untested | `mumtaz_billing_stripe`: 0 test files | PL-10; audit A-11, A-12 |
| Single sign-on has no tests and a known flaw | `mumtaz_sso`: 0 test files; audit ODOO-01 | PL-09 |
| Subdomain routing is untested | `mumtaz_subdomain_routing`: 0 test files | Extend the journey script to reach the tenant by host |
| Real install profiles are not tested, only "everything together" | `scripts/platform_ci.sh` | PL-01 checks 3–6; one journey run per profile |
| Two tenants side by side; database-level isolation | Section 3.1 | CP-N8; PL-18 |
| No restore drill | Audit B-03, B-06 | PL-00 |
| No load or concurrency test | `TEST_MIGRATION_DEPLOYMENT_STRATEGY.md` §11.1 | Before a tenant exceeds 10 users; before two provisioning runs can overlap |
| No accessibility, RTL or performance check on the website | `MUMTAZ_WEBSITE_IMPLEMENTATION.md` §4.3 | WB-P1, WB-P2 |
| Faizy tests do not run in CI | `faizy-ci.yml` has no Odoo install | A Faizy job on the pattern of `platform-odoo-install.yml`, on Faizy's own branch |
| Agency OS tests do not run in CI | `ci.yml` | Audit A-08 |
| ZAKI: no test of company isolation, cash figure or grounding | `MUMTAZ_AI_ARCHITECTURE.md` §6 | PL-12 |
| No test on any Mumtaz server | Section 1 | PL-19 and the gates in section 5 |
