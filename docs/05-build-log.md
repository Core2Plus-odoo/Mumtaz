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
