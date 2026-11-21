# 10. Development roadmap: dependency-based waves and milestones

No calendar promises. Each wave has an entry gate, exit evidence, and the
regression of every earlier wave. "Done" means the blueprint's definition in
`DEVELOPMENT_STANDARDS.md` §7.5.

## Wave 0 — Audit and design (this deliverable)

Exit: charter signed (G0), decision register answered for ADR-003/005/006/009/010 and D-01/D-06 (G1).

## Wave 1 — Platform foundation and engineering hygiene

| Milestone | Scope | Depends on | Exit evidence |
| --- | --- | --- | --- |
| M1.1 Fresh-database CI for all 52 modules | extend `jewel-odoo-tests.yml` pattern to a platform suite: install + upgrade every module; smoke tests per module | — | green workflow on `main`; install log attached |
| M1.2 Security pass | access CSV for every model; `sudo()` inventory with reasons; cross-company negative test per tenant-facing module; MFA for manager groups | M1.1 | `SECURITY_MATRIX.md` §8a.5 complete; tests green |
| M1.3 Versioned CRM logic (R1) | `c2p_crm_rules` module replacing the 25 server actions with tested automation; dry-run mode; archive with reason | M1.1 | parity test against a staging copy; server actions disabled, not deleted |
| M1.4 Localisation bundle | tenant bundle installs `l10n_ae`/`l10n_sa`/`l10n_pk` + `l10n_gcc_invoice`; finance manager enters VAT | ADR-006, D-06 | a fresh tenant has a chart, taxes and bilingual invoice |
| M1.5 State stores | SQLite in zaki-server and C2P delivery API moved to Postgres or Odoo; backups cover them | ADR-010, D-05 | restore drill documented |
| M1.6 Jawhar staging promotion | deploy `main` to `jewel.mumtaz.digital` | owner runs the two commands | verify_site green |

## Wave 2 — Financial and commercial spine (reference transactions)

| Milestone | Scope | Depends on | Exit evidence |
| --- | --- | --- | --- |
| M2.1 L2C proven on a generic tenant | quote → order → partial delivery → partial invoice → payment → reconciliation, with tests (SLS-REQ-001) | M1.4 | `SLS-E2E-001` green; drill-down from order to journal entries |
| M2.2 P2P proven | RFQ → PO (approval threshold) → partial receipt → bill (3-way) → payment (PUR-REQ-001) | M1.4 | `PUR-E2E-001` green; GRNI clears |
| M2.3 Valuation and close controls | automated valuation per ADR-005; lock dates; reversal-only corrections; month-end reconciliation pack (FIN-REQ-001/003) | ADR-005, ADR-011 | signed reconciliation for one month on `Mumtaz_ERP` |
| M2.4 E-invoicing verified | sandbox tests for UAE QR, ZATCA (native vs custom decided), FBR; idempotent retries (FIN-REQ-002) | M2.1 | `FIN-TEST-002` green against sandboxes |
| M2.5 Statements decision | standard reports + OCA `mis_builder` vs `mumtaz_financial_reports` (D-02) | M2.3 | ADR written; one path kept |

## Wave 3 — Operations and verticals

| Milestone | Scope | Depends on |
| --- | --- | --- |
| M3.1 C2P project costing | timesheets → analytic cost → tracker margin (PRJ-REQ-001); milestone invoicing | M2.1 |
| M3.2 C2P intercompany | mirrored invoices between the two companies per finance policy (FIN-05) | M2.3, finance decision |
| M3.3 Jewellery workshop and repairs | standard `repair`, `mrp` configured for a workshop tenant | a named tenant |
| M3.4 Media buying hardening | tests, company scoping, PO/bill link proof | M2.2 |
| M3.5 Marketplace and portals | tests; server-side feature-flag enforcement | M1.2 |
| M3.6 HR foundation (if scoped) | `hr`, attendance, leave, expenses; payroll deferred | charter |

## Wave 4 — Analytics and intelligence

| Milestone | Scope | Depends on |
| --- | --- | --- |
| M4.1 Metric lineage on every dashboard | command centre, CEO dashboard, board pack | M2 |
| M4.2 One governed AI policy platform-wide (D-03) | levels A–E, restricted data exclusion, numbers from the engine, audit; retire duplicate provider layers | M1.2 |
| M4.3 Agent evaluation corpus | Arabic/English utterance sets; injection suite | M4.2 |

## Wave 5 — Migration, UAT, go-live per tenant

Per tenant: source audit → mapping → dry run → reconciliation register →
UAT scripts → cutover rehearsal → go/no-go → hypercare. Template in
`quality/TEST_MIGRATION_DEPLOYMENT_STRATEGY.md`.

## Conditional 30/60/90-day view (contingent on decisions, not a promise)

- **First 30 days**: Wave 1 M1.1–M1.3, M1.6; decisions ADR-003/005/006, D-01, D-06.
- **Days 30–60**: M1.4, M1.5, M2.1, M2.2.
- **Days 60–90**: M2.3–M2.5, M3.1.

## Gate-0 decisions required to start Wave 1

ADR-003 (branch model), ADR-005 (valuation), ADR-006 (localisation),
ADR-009 (MFA, service identities), ADR-010 (RPO/RTO), D-01 (first slice),
D-05 (SQLite stores), D-06 (named finance manager).
