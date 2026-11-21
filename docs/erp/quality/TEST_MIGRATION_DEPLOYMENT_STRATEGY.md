# 11. Testing, reconciliation, migration and deployment strategy

## 11.1 Test layers and where they run

| Layer | Tooling here [VERIFIED] | Gap | Target |
| --- | --- | --- | --- |
| Static | flake8 + bugbear, bandit, manifest and XML validation, dependency audit (`ci.yml`); tsc, vitest (`jawhar-web.yml`) | none | add the `sudo` grep and a secrets scan |
| Unit | Jawhar engine tests (19, pure Python), `fit.ts`/`tryon.ts` vitest | platform: none | pricing, tax, state and permission helpers per module |
| Integration (real DB) | Jawhar `TransactionCase` (242), tracker tests (57 functions) | 37 platform modules: none | install/upgrade smoke per module; posting and stock effects |
| Contract / door | Jawhar `HttpCase` on `/jawhar/v1` and public routes | gateway, zaki-server, Stripe, ZATCA: none | contract tests with recorded fixtures; sandbox runs for authorities |
| End-to-end process | Jawhar counter (one transaction), tray → quote → invoice | generic L2C/P2P: none | SLS-E2E-001, PUR-E2E-001 |
| Role / security | Jawhar 404-not-403, VIP rules, audit hidden from staff | platform: none | per-module cross-company negative test |
| Reconciliation / property | Jawhar fine-gram counts, price engine invariants | finance: none | monthly subledger-to-control pack; valuation vs stock account |
| Migration | Jawhar stock import idempotency | none for Odoo-to-Odoo | reconciliation register per tenant migration |
| UI walks | Playwright headless walks of all 22+ Jawhar screens, kiosk with fake camera, EN/AR | Odoo screens, portals: none | Odoo tours for critical flows; portal smoke |
| Performance / reliability | none | — | load test with realistic volumes before a tenant exceeds 10 users; restore drill |
| UAT | owner reviews in chat | no signed scripts | UAT template per module from the pack |

Evidence rule: a PR states the exact commands and counts; "NOT RUN" where a
layer could not run; walks attach screenshots.

## 11.2 Reconciliation controls (finance)

Monthly, per company: AR aged = receivable control; AP aged = payable
control; bank statement balance = bank account; stock valuation report =
stock accounts; GRNI = unbilled receipts; tax report = VAT accounts;
intercompany mirrors agree. Differences go to a difference register with
root cause and approver. Nothing is forced to balance by a plug entry.

## 11.3 Migration method (per tenant or for the C2P databases)

1. Source audit: tables, custom fields, inactive and cancelled records, attachments.
2. History window and cut-off agreed; open balances and open quantities defined.
3. Mapping per object with stable external identities (`x_source_system`, `x_source_ref`); never match by name or number alone.
4. Extract → transform → stage → validate (uniqueness, company, currency, tax, period) → load in dependency order with idempotent upserts and checkpoints.
5. Reconcile counts **and** values per company/currency/period/status; register differences; approver signs.
6. Dry run on a disposable database with rollback rehearsal; go/no-go; cutover; parallel run if finance asks.

Jawhar already has the import half of this for stock books (preview, apply
once, idempotent on serial, run log). The same shape is the template for
partners, products, open invoices and opening balances.

## 11.4 Deployment and environments

| Environment | Today [VERIFIED] | Target |
| --- | --- | --- |
| Local / CI | disposable databases via `scripts/jewel_ci.sh` and GitHub Actions | the same for all modules |
| Staging | Jawhar: `jewel.mumtaz.digital`, isolated compose project, synthetic data; platform ERP: none documented | a platform staging with a masked copy policy |
| Production | one VPS, compose, manual production workflow, nightly backup workflow | pre-deploy backup, smoke test, rollback script exercised, on-call owner named |
| Approvals | Jawhar: named human approval in chat before any server change; C2P console: `main` auto-pulls | written go/no-go per release for the ERP |

Release gate: `RELEASE_GATE_CHECKLIST.md` in this folder, filled per release
with PASS / FAIL / NOT RUN / N/A and evidence links.

## 11.5 Business continuity

RPO/RTO undefined [DECISION ADR-010]. Backups: nightly workflow exists; the
SQLite stores are outside it (R5). A restore drill has not been evidenced in
the repository; it becomes a Wave 1 exit criterion.
