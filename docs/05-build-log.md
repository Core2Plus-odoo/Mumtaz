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
- **Backups** (the first real ones of `Mumtaz_C2P` on the server), in
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
  reads a different add-on folder; the nightly backup job only dumps an empty
  `scratch_pre` database; the live checkout is on a feature branch with
  uncommitted files; `c2p_master_agent` is installed but its source is in
  neither add-on folder listed; the server reports a pending restart and
  security updates.
- **Not installed on live:** `c2p_client_onboarding` (needs
  `c2p_project_tracker`, which is not installed there), `c2p_work_hub`,
  `c2p_meeting_actions`, `c2p_task_change_reason`.
- Shafat's Q1-Q3 had not been received; the owner proceeded for this module,
  which does not touch tasks.
