# 12. Prioritised implementation backlog with acceptance criteria

Order = business value × dependency × risk. Each item names its wave, the
requirement it serves, and GIVEN/WHEN/THEN acceptance. Items marked ⚠ need a
decision first.

| # | Item | Wave | Req | Acceptance (GIVEN / WHEN / THEN) |
| --- | --- | --- | --- | --- |
| 1 | **Fresh-database install CI for every module** — **built 21 Nov 2026** (`scripts/platform_ci.sh`, `.github/workflows/platform-odoo-install.yml`: all 39 non-jewellery modules in one database, upgrade with tests, fail on any logged ERROR; four modules that could not install were fixed, see the changelog). Still open: a per-module smoke test that loads the main menu | 1 | PLT-REQ-001 | GIVEN a clean Odoo 19 CE database WHEN all 52 modules install and upgrade THEN exit 0 and 0 errors in the log; a module that fails blocks merge |
| 2 | **Access CSV and company scoping audit** (add missing `ir.model.access.csv`; `company_id` on unscoped platform models; one cross-company negative test per tenant-facing module) | 1 | PLT-REQ-002 | GIVEN users A and B in different companies WHEN B requests A's record by id over RPC THEN access error / 404 and nothing written |
| 3 | **`sudo()` inventory and justification** (comment on each; CI grep fails on an unlabelled `sudo(`) | 1 | PLT-REQ-002 | GIVEN the repository WHEN CI runs THEN every `sudo()` carries `# sudo:` and `SECURITY_MATRIX.md` §8a.5 lists the counts |
| 4 | **Versioned C2P CRM rules** (`c2p_crm_rules`: qualification, scoring, assignment, archival as code with tests and a dry-run flag; disables the database actions on install) | 1 | CRM-REQ-001 | GIVEN a staging copy of `Mumtaz_C2P` WHEN the module runs in dry-run THEN its proposed changes match the live actions' on a sample of 500 leads, differences listed; archival writes a lost reason |
| 5 | ⚠ **Localisation bundle** (`mumtaz_tenant_manager` bundle installs `l10n_*` by country; finance manager enters VAT) | 1 | PLT-REQ-003 | GIVEN a new UAE tenant WHEN provisioned THEN chart, VAT taxes and bilingual invoice layout exist; no tax rate hard-coded in the repository |
| 6 | ⚠ **Retire SQLite stores** (zaki-server users → Odoo only; C2P engagement store → Postgres) with a restore drill | 1 | ADR-010 | GIVEN a backup WHEN restored to a new host THEN sign-in and engagement history work; drill documented |
| 7 | **Jawhar staging promotion** (owner runs the deploy and top-up commands) | 1 | D-08 | GIVEN `main` WHEN deployed THEN `verify_site.sh` green and 13 modules at the merged version |
| 8 | **L2C reference transaction with tests on a generic tenant** (partial delivery, partial invoice, payment, reconciliation; drill-down) | 2 | SLS-REQ-001 | GIVEN an order of 10 WHEN 6 ship and are invoiced, then 4 THEN delivered/invoiced quantities, AR and stock agree; a warehouse user cannot post the invoice |
| 9 | **P2P reference transaction with tests** (approval threshold, partial receipt, 3-way match, GRNI clearing) | 2 | PUR-REQ-001 | GIVEN a PO of 10 WHEN 7 received and billed THEN bill control allows 7 only; GRNI balance equals unbilled receipts |
| 10 | ⚠ **Valuation and close controls** (automated valuation per ADR-005; lock dates; reversal-only; month-end pack) | 2 | FIN-REQ-001/003 | GIVEN a closed month WHEN a user edits a posted move THEN refused; AR+AP+bank+stock subledgers equal control accounts in the signed pack |
| 11 | **E-invoicing verification** (sandbox tests, idempotent retry, decision native ZATCA vs custom) | 2 | FIN-REQ-002 | GIVEN a sandbox WHEN submit is called twice THEN one submission, same UUID; failure leaves the invoice posted with an error state |
| 12 | ⚠ **Statements decision** (standard + OCA `mis_builder` vs custom) | 2 | D-02 | GIVEN one month's postings WHEN TB, P&L, BS are produced by both THEN figures match; one path is kept and the other removed |
| 13 | **Field dictionary completion** (`DATA_DICTIONARY.csv` rows for UI screen, report and test id; standard fields referenced) | 2 | §7.4 | every custom field has a test id or a `NOT COVERED` tag |
| 14 | **C2P project costing** (timesheets → analytic → tracker margin; milestone invoicing) | 3 | PRJ-REQ-001 | GIVEN 40 h logged at a cost rate WHEN the portfolio project is opened THEN margin reflects cost; invoice from a reached milestone links to it |
| 15 | ⚠ **C2P intercompany mirror** per finance policy | 3 | FIN-05 | GIVEN a recharge WHEN posted THEN the mirrored entries agree and reconcile |
| 16 | **Media buying and marketplace hardening** (tests, scoping, feature-flag enforcement server-side) | 3 | ARCH §4 TODO | GIVEN a tenant with marketplace disabled WHEN its user calls a marketplace RPC THEN refused |
| 17 | **Metric lineage on dashboards** | 4 | BI-01 | every widget documents domain, filter and source model; drill-through works |
| 18 | ⚠ **One governed AI policy platform-wide** (adopt Jawhar's; retire duplicates) | 4 | AI-REQ-001 | GIVEN a restricted record WHEN any agent runs THEN no restricted value in the model request (test); numbers in replies trace to engine reads |
| 19 | **Noor's two try-on tools registered in ElevenLabs; device test of try-on and voice** | — | Jawhar | tools callable in a live session; fit panel reads on a real camera |
| 20 | **Jewellery workshop / repairs configuration** when a tenant is named | 3 | VRT-01 | repair order from a sold piece; metal issue and return traced |

Out of scope until a charter names them: HR/payroll, manufacturing beyond
the workshop, service desk, rental, consolidation, WhatsApp Cloud API.

## Next smallest safe task

Item 1 is built. **Item 3** (the `sudo()` inventory with a CI grep for
unlabelled uses) is the next one that needs no decision and no data: a
read-and-annotate pass over 56 call sites that also feeds item 2.
