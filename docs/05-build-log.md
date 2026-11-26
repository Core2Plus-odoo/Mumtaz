### 20 Nov audit documents withdrawn ✅ (24 Nov 2026)
- Removed `docs/project/00-INDEX` … `ROADMAP`, `docs/architecture/`,
  `docs/quality/TEST_MIGRATION_DEPLOY_STRATEGY.md` and `docs/erp-standard/`.
  They were written from a checkout 169 commits behind `main`, so their figures
  (38 modules, 57 tests) were wrong the day they were committed, and
  `docs/erp/` on `main` is the programme's real instance of the same standard.
- Kept: `docs/project/phase1/` (fit-gap, workflow, plan, 15 templates), written
  against the merged tree, and the read-only scripts in `scripts/audit/`.
- The entry below describes the withdrawn pack and is left as the record of
  what was done and why it was undone.

### ERP Master Blueprint adopted; Wave 0 audit and design pack ✅ (no app code changed)
- **Installed the C2P ERP Master Blueprint v1.0** unmodified at
  `docs/erp-standard/` (blueprint, 8 document templates, 4 architecture
  references, release-gate checklist) as the governing engineering standard.
  The pack's own `CLAUDE.md` is kept as `docs/erp-standard/ERP_CLAUDE_RULES.md`
  rather than overwriting the root one — merging the two is DEC-008, an owner
  decision, because it changes the always-on contract for every session.
- **Produced the 12 Wave 0 deliverables** under `docs/project/`,
  `docs/architecture/` and `docs/quality/`, indexed by
  `docs/project/00-INDEX.md`. Every claim is marked [FACT] / [DESIGN] /
  [ASSUMPTION] / [DECISION].
- **Audit scripts committed** at `scripts/audit/` so every count is
  reproducible: module inventory + risk flags, per-model ACL/record-rule
  coverage, and a 978-row AS-IS field dictionary
  (`docs/architecture/DATA_DICTIONARY_AS_IS.csv`).
- Measured, among others: 38 modules / 21,772 Python lines / 62 concrete models
  / 978 fields; **62 of 62 models have an ACL row** but only 22 have any
  `ir.rule`; 34/34 Monetary fields carry an explicit `currency_field`; zero
  `attrs=`, `<tree>` or `states={` anywhere; dependency graph acyclic with a
  depth-9 chain; **57 tests exist, all in one module, none ever executed**.
- The decisive finding: **none of the 978 fields references `account.move`,
  `account.payment` or `stock.picking`**, so no document-to-ledger lineage
  exists. `project.project.amount_received` and `media.plan.net_revenue` are
  hand-entered or planned figures that cannot reconcile to the accounts.
- Corrected one of my own measurements mid-audit: the first ACL-coverage pass
  reported 69/106 because its `_name\s*=` regex also matched `_rec_name` and
  `brand_name`, inventing models. Anchored to line start, the real answer is
  62/62 — the opposite conclusion. Both the error and the fix are recorded in
  `scripts/audit/README.md` and in the audit itself.
- Also caught and fixed in-flight: the first draft of `01-AS-IS-AUDIT.md`
  carried a live production credential into a committed document. The safety
  classifier refused the write. The exposure is now described without the value,
  and "no secrets in documentation" is now an explicit rule in
  `docs/architecture/DEVELOPMENT_STANDARDS.md` plus a proposed CI gate.
- Verified: no credentials in any new doc (grep); 0 broken relative links
  (link-checker over all new markdown); all three audit scripts re-run and
  reproduce their published numbers. **No Odoo test was run — this container
  cannot reach the VPS (connection refused on 22 and 8069), so the audit is
  static-evidence only and says so up front.**
- Next action is `SEC-000`: close the production exposure. No dependencies, no
  decision, no code.


### Premium dashboard + Sales/Customers/Project IA + project gating ✅
- **Premium dashboard** (new default home) — gradient hero with quick actions,
  four colour-coded stat tiles (Leads / Customers / Projects / Approvals), a
  recent-projects list (each bound to its customer) and a pipeline summary.
- **Separated navigation** — Sales (Leads) and Customers are now distinct
  sections; projects live under a Project section labelled with the selected
  project's name.
- **Project gating** — all project-scoped views (presales, proposal, client
  replies, documents, BA, functional, developer, execution, overview) are locked
  (🔒, dimmed) until a project is selected; clicking one routes to the Project
  Manager to open/create a project. `goView` enforces the gate too.
- **Projects bound to customers** — the dashboard shows each project's customer
  (via account_id → account name).
- Verified: JS syntax + no dup names + headless render (default=dashboard,
  sections Sales/Customers/Project, 10 gated items when no project, stat tiles
  and customer-bound project rows populate) — no page errors.

### mumtaz.digital marketing landing page ✅
Built the public marketing site the CI expected (the "Website Deployment Check"
was failing because `website/` was missing — now green).
- **`website/index.html`** — premium, responsive landing on the official
  gold-first Mumtaz brand: sticky header, hero ("The ERP — and the AI team that
  delivers it."), the two products (Mumtaz ERP + Automated ERP Implementation),
  the four segments (ERP/Bookkeeping/Accounting/Consulting), a dark how-it-works
  band (4 steps), a 6-card feature grid, a gold CTA band and footer. CTAs link to
  the console at delivery.mumtaz.digital.
- **`website/assets/css/style.css`** — self-contained gold/teal/ivory design
  system (Fraunces display + Plus Jakarta Sans), fully responsive with a mobile nav.
- **`website/assets/js/main.js`** — mobile-nav toggle, footer year, and a
  progressive-enhancement reveal (transform-only, so JS can never hide content;
  respects prefers-reduced-motion).
- Verified: JS syntax; all three CI-required files present; Playwright headless
  render (hero, both products, four segments, all sections visible) — no page
  errors.

### Client master record, onboarding checklist and plan control (24 Nov 2026) — built, not installed
Two new addons on top of the existing partner and the Consultants–Solutions
project pair. No client, engagement or project model; no project-creation
automation.
- **`c2p_client_onboarding`** — Client Overview page on `res.partner`
  (contacts with roles, engagements with scope/staff/onboarding, milestones,
  instance inventory, required documents, access register, a "next required
  action" line). Scope fields and a nine-item onboarding checklist on the
  portfolio project, each item with owner, due date, evidence and what a gap
  blocks. Access register stores `vault://collection/item` references only;
  text that looks like a secret is refused. Welcome email is drafted into the
  standard composer and sent by a person.
- **`c2p_plan_control`** — contributors propose plan changes; the delivery owner
  approves in-scope ones (previous value, new value, baseline, reason, actor,
  time kept); milestone date moves keep the baseline and notify the account
  owner; scope changes become one `c2p.change.request` for Consultants.
- **Fixes to code already on main**, found by the demonstration:
  `c2p_work_hub` hid all tasks when a milestone was upcoming;
  `c2p_project_tracker` delivery dashboard never opened (getter/method name
  clash).
- Verified: `0 failed, 0 error(s) of 160 tests` for the six C2P modules on a
  fresh Odoo 19 database; flake8, sudo-label check and module registry clean;
  27-screen walkthrough with fictional data in
  `docs/project/demo-client-onboarding/`.
- Not done: nothing installed or deployed; live security audit still denied,
  so group membership and record-rule questions are listed in the PR.

### Plan control withdrawn, milestone forecast added (25 Nov 2026) — built, not installed
Owner's decision after the founder answers of 25 Nov (X2, R3, forecast rule).
- **Removed `c2p_plan_control`** before it was ever merged or installed. It
  conflicted with `c2p_task_change_reason` and with the forecast rule: it wrote
  task and milestone dates without a reason, and treated the milestone deadline
  as a moving forecast rather than a locked commitment.
- **Added `c2p_milestone_forecast`** — commitment date (the standard milestone
  deadline), forecast date, calculated health (green / amber 1-5 days / red
  over 5 / grey "No forecast"), project shows its worst milestone, reached
  milestones keep their colour, a reason is required to change an existing
  commitment or forecast date and is stored with the tracked change.
- `c2p_client_onboarding` is unchanged.
- Verified on **stock Odoo 19 only, not Mumtaz_C2P**. Test counts are in the
  pull request.
- Not done: `c2p_task_change_reason` is not in this repository (its files never
  reached the build session); no approval step for commitment changes; nothing
  installed or deployed.

### c2p_milestone_forecast installed on core2plus.com (25 Nov 2026, about 08:47 UTC)
First live install from this work. Run by the owner as root on the VPS, one
step at a time, after his explicit "yes, install on live".
- **Backups** (taken by hand before the install; nightly ones already
  existed, see the correction in the next entry), in
  `/var/backups/pg/`: `Mumtaz_C2P_pre-forecast-2026-11-25.dump` (08:35) and
  `Mumtaz_C2P_pre-forecast-live-2026-11-25-0846.dump` (immediately before the
  install). Database only; the filestore was not backed up.
- **Restore test:** the 08:35 dump was restored into a locked copy and matched
  live exactly (684 tasks, 54 milestones, 1,172 contacts). Scheduled jobs and
  mail servers were switched off on the copy before any Odoo service could
  open it. The module installed there and passed 17 of 17 tests. The copy was
  deleted afterwards.
- **Live:** module copied to `/opt/custom_addons/c2p_milestone_forecast`
  (outside the git checkout, which was not touched), installed on
  `Mumtaz_C2P`, `odoo4.service` restarted. Site answered 200, 0 errors logged,
  record counts unchanged, all 54 milestones grey "No forecast".
- **Rollback:** uninstall from Apps; or restore the 08:46 dump.
- **Found on the server, not changed:** `odoo2` and one other Odoo service
  open every database owned by the `odoo` role, including `Mumtaz_C2P`, so
  scheduled jobs on live data may run from more than one service; `odoo2`
  reads a different add-on folder; (the nightly backup claim that stood here was wrong; see the
  correction in the next entry); the live checkout is on a feature branch with
  uncommitted files; `c2p_master_agent` is installed but its source is in
  neither add-on folder listed; the server reports a pending restart and
  security updates.
- **Not installed on live:** `c2p_client_onboarding` (needs
  `c2p_project_tracker`, which is not installed there), `c2p_work_hub`,
  `c2p_meeting_actions`, `c2p_task_change_reason`.
- Shafat's Q1-Q3 had not been received; the owner proceeded for this module,
  which does not touch tasks.

### Server housekeeping after the forecast install, and a correction (25 Nov 2026, 08:55-09:01 UTC)
Run by the owner as root on the VPS, one block at a time.
- **Correction.** The previous entry said the nightly backup only dumped an
  empty `scratch_pre` database. That was wrong: it came from reading the last
  few files of an alphabetical listing. `/usr/local/bin/pg-backup.sh` runs at
  01:30, dumps every database including `Mumtaz_C2P`, and keeps 14 days. What
  was true: no restore had been tested before today, uploaded files were not
  backed up, and every copy is on the same disk as the live system.
- **Uploaded files are now backed up.** New `/usr/local/bin/filestore-backup.sh`
  and `/etc/cron.d/c2p-filestore-backup` (01:45 nightly, 14 days, one archive
  per database in `/var/backups/filestore/`). First run archived seven
  databases; the `Mumtaz_C2P` archive holds 894 files, matching the live
  folder. `pg-backup.sh` was not edited.
- **`Mumtaz_C2P_staging` switched off.** It had 42 active scheduled jobs and
  11 active mail servers, last run 11 Aug 2026. All set inactive; the list of
  what was active is in `/root/Mumtaz_C2P_staging_was_active_2026-11-25.txt`.
- **Removed** two leftover filestore folders from the morning's test runs.
- **Found, not changed:** the 03:00 job `/opt/mumtaz/scripts/backup.sh` fails
  every night (it targets a Docker stack that no longer runs); there is no
  off-server copy of any backup; `odoo2` and `odoo3` still open every database.
- `PR 205` was merged to `main` at about 08:55 UTC. The server does not pull
  `main`; the live forecast module is the hand-installed copy.

### Tracker, My Work Today, Minutes and Client Overview installed on core2plus.com (25 Nov 2026, about 09:33 UTC)
Run by the owner as root on the VPS after choosing "Yes, all four".
- **Installed on `Mumtaz_C2P`:** `c2p_project_tracker`, `c2p_work_hub`,
  `c2p_meeting_actions`, `c2p_client_onboarding`, from `main`, copied to
  `/opt/custom_addons/` (the git checkout was not touched). `odoo4.service`
  restarted; site answered 200; 0 errors logged; record counts unchanged
  (684 tasks, 54 milestones, 1,172 contacts); 43 active scheduled jobs
  (42 plus the tracker's hourly sync).
- **Rehearsal first:** a locked copy of that morning's data, scheduled jobs and
  mail switched off before any Odoo service could open it; all five modules
  installed; `0 failed, 0 error(s) of 139 tests`. Copy deleted afterwards.
- **What the tracker's install hook did on live:** paired 2 of 4 engagements
  (TUV Austria, 8 milestones linked; Medicslab, 6 linked); Aaban and Ghandhara
  were skipped because no project with those names exists; classified 8
  template and 3 internal projects, 18 left unclassified; assigned roles to
  1 Portfolio Manager, 1 Delivery Lead and 8 Delivery Members; seeded the
  contract figures recorded on 5 Oct, which the owner should check.
- **Effect on existing work, measured on the copy:** 2 open delivery tasks
  lack an assignee, deadline or milestone, and 2 "Waiting on Client" tasks
  have no reason; each will ask for the missing detail when next edited.
- **Backups before the install:** database
  `Mumtaz_C2P_pre-tracker-live-2026-11-25-0932.dump` and uploaded files
  `Mumtaz_C2P_pre-tracker-live-2026-11-25-0932.tar.gz`.
- **Also that hour:** `odoo2` pinned to `Mumtaz_ERP` (`db_name` added to
  `/etc/odoo2.conf`, previous config saved in `/var/backups/`); it now opens
  only its own database. `odoo3` is still unpinned.
- **Not verified:** nobody has yet opened the new screens in a browser on
  live; Shafat's Q1-Q3 were not received; no access review with real users.

### File uploads on required documents and scope (25 Nov 2026) — live on core2plus.com since about 09:57 UTC
Asked for by the owner after the live install: "we need upload document".
- `c2p_client_onboarding` 19.0.1.1.0. Each Required Documents row now takes a
  file; uploading one moves a waiting row to Received and dates it, and leaves
  a Verified or Not-applicable row as its owner set it. The engagement's Scope
  & Onboarding tab takes the signed scope or contract file, locked with the
  rest of the scope once approved.
- Files are stored as Odoo attachments in the filestore, which the nightly
  uploaded-files backup added today already covers. Whoever can read the row
  can download the file; a Delivery Member cannot upload; a user with no
  tracker role cannot reach it.
- Verified on stock Odoo 19: `0 failed, 0 error(s) of 88 tests` for
  `c2p_project_tracker` and `c2p_client_onboarding`; both uploads driven in a
  browser with fictional files (screens `U3`, `U4` in
  `docs/project/demo-client-onboarding/screens/`).
- **Live upgrade (about 09:57 UTC, run by the owner):** rehearsed first on a
  locked copy of that hour's data (`0 failed, 0 error(s) of 31 tests`, the one
  marked client preserved), then `c2p_client_onboarding` upgraded to
  19.0.1.1.0 on `Mumtaz_C2P` and `odoo4.service` restarted. Site answered 200,
  0 errors logged, 684 tasks and 1,173 contacts unchanged, 43 active scheduled
  jobs. Backups before it: `Mumtaz_C2P_pre-uploads-live-2026-11-25-0956.dump`
  and the matching filestore archive. The previous module version is kept at
  `/root/c2p_module_backups/c2p_client_onboarding-before-2026-11-25-0956`.
- Not done: one file per row, not several; no preview; the upload has not yet
  been tried in a browser on live.

### c2p_order_projects built (26 Nov 2026) — merged work only, not installed anywhere
Built after the owner's decisions D1 to D4 and D6 in
`docs/project/phase1/04-ORDER-TO-PROJECT-PATHS.md`.
- New addon `addons/c2p_order_projects` 19.0.1.0.0. Confirming an order that
  holds a project-creating product (`project_only` or `task_in_project`) makes
  sure the order has one oversight and one delivery project. The oversight
  project is the one the standard Sales Project flow creates; this module tags
  it. The delivery project is created from a template in the delivery company
  and tagged. A database index allows one of each per order; an archived
  project still counts, and templates are never matched.
- Pairing in the Project Tracker (layers and counterpart) is done only when the
  delivery template has a Backlog stage, because the tracker refuses a task that
  leaves Backlog without an owner, a date and a milestone.
- Where the database-only fields `x_billing_project_id`, `x_delivery_project_id`
  and `x_billing_milestone_id` exist (they exist on Mumtaz_C2P only), they are
  filled as action 919 filled them, so the milestone-to-billing rule keeps
  working. Elsewhere that step does nothing.
- Confirming never fails because of this module: an error is logged and noted
  on the order. Nothing happens until four system parameters switch it on
  (`c2p.order_projects.*`); no emails, scheduled jobs or access rules.
- Verified on stock Odoo 19: `0 failed, 0 error(s) of 22 tests`, including
  archived projects, a template carrying the key, losing a race, repeats and
  re-confirmation, a Consultants-only salesperson, and an error not blocking
  the confirmation. A separate run with the three `x_` fields present filled
  them and mirrored the milestone.
- **Not done:** not run on a copy of live data; not installed; no live
  automation changed. The proposed changes to the live automations are in
  `docs/project/phase1/05-ORDER-PROJECTS-CUTOVER.md`, as text only. The staging
  runbook is `docs/project/phase1/06-ORDER-PROJECTS-STAGING-RUNBOOK.md`; its scripts
  were rehearsed on a local stand-in that holds the pasted live actions (baseline,
  install, off, on, edited and a two-process race all as expected) and have not run
  against live data.
