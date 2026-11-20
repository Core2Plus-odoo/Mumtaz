# 11. Testing, reconciliation, migration and deployment strategy

Evidence rule (blueprint §15.3, §21): a test is *passed* only if it was executed, with the command, date, build and result recorded. Everything else is `NOT RUN`. Mocked integrations are never reported as external-system success.

## 1. Environments and promotion `[V]` unless marked

| Environment | Today | Rule |
| --- | --- | --- |
| Local/CI | CI lint, manifest check, bandit (all add-ons); Odoo tests in CI **only for jewellery** | `[P]` add the pharma Odoo test job (PHA-CI-001) so evidence no longer depends on a person at a terminal |
| Throwaway test database | `stage.sh test`, `test-combined` (with the accounting kit), `test-kit`; database `mumtaz_pharma_test`, dropped after every run | same module list as the real install; never real data |
| Staging / UAT | `mumtaz_pharma` on the VPS, `odoo-pharma` unit, TLS, neutralized, demo mode | every change is dumped first; owner approves each upgrade |
| Production | repo `/opt/mumtaz`, `main` only, `c2p-delivery-system/deploy/update.sh` | **nothing from `pharma-*` branches reaches it**; a production pharma tenant does not exist yet |

Promotion path for a pharma change: branch → `stage.sh test` / `test-combined` (0 failed) → `stage.sh rehearse-upgrade` (PASSED) → **owner go** → `stage.sh upgrade [module]` (dump, update, re-neutralize, restart `odoo-pharma` only) → `verify` → `smoke` → deploy-log entry with the pasted output → owner browser pass → acceptance.

## 2. Test layers (blueprint §15.1)

| Layer | Pharma today | Target |
| --- | --- | --- |
| Static / lint / security | flake8, bandit in CI; local `py_compile`, pyflakes, XML parse, `bash -n`, reserved-name scan | keep; add dependency scan and secret scan |
| Unit | most of the 231 test methods | keep; one behaviour per test |
| Integration (real DB) | the same suites run on a real throwaway DB at install | add multi-company and multi-currency fixtures once decided |
| Contract | none | uploaded-file formats and raw-event payloads get contract tests (INT-01/02) |
| End-to-end process | **COD path pieces only**; not the invoice leg | PHA-L2C-001: order → delivery → invoice → collection → reconcile to invoice → settle → post → reverse |
| Role / security | per-action negative tests for Finance/Ops/accountant | add auditor, cross-company, RPC-level suite |
| Reconciliation / property | none automated | the checks in §3 as scheduled tests and as `stage.sh verify` lines |
| Migration | none (no real source data yet) | §4 |
| Performance / reliability | none | synthetic volume (e.g. 100k parcels) on a copy; restore drill; failure injection on upload |
| UAT | **NOT RUN**; script exists (`DEMO_SCENARIOS.md` C1–C17) | owner executes; evidence screenshots stored per release |

## 3. Reconciliation checks for the COD ledger (to implement as automated tests and verify lines) `[P]`

| ID | Invariant | Source of truth | Tolerance |
| --- | --- | --- | --- |
| REC-1 | Σ over parcels with a **posted** collection entry of `cod_collected` = Σ debits of COD *collection* entries posted to the courier clearing account | `pharma.courier.shipment` vs `account.move.line` filtered by `pharma_cod_kind` | 0.00 |
| REC-2 | Σ gross of remittances with a **posted** settlement entry = Σ credits of COD *settlement* entries on the clearing account | remittances vs ledger | 0.00 |
| REC-3 | Clearing account balance = Σ(collected on posted collection entries) − Σ(gross on posted settlement entries) = **what the couriers still hold** | ledger vs parcels | 0.00 |
| REC-4 | Every parcel with `flow_next = none` has `cod_outstanding ≤ courier tolerance` | parcels | tolerance per courier |
| REC-5 | Number of built statement rows = number of `pharma.raw.event` rows with that statement's id | statements vs raw events | 0 |
| REC-6 | Per remittance: `Σ deductions + bank received + difference line = gross` and the entry balances | remittance vs entry | 0.00 |
| REC-7 | No COD entry is posted whose parcel/remittance link was removed (orphan check) | ledger vs links | 0 |
| REC-8 | Open exceptions by category vs the queue count | hub | 0 |

Failure of any check is a defect or an explained difference in the **difference register** (template: `templates/MIGRATION_RECONCILIATION_TEMPLATE.csv`); nothing is "fixed" by editing posted entries or inserting balancing lines.

## 4. Migration (pharma has no production source yet; strategy for when it does)

Order: source audit → target model map → extract → transform → stage → validate → load → reconcile → approve → cutover (blueprint §14).

1. Inventory source objects and fields; agree history window, cutover date, open balances and open parcels `[D]`.
2. Stable external identity `(source instance, model, id)`; match parties/products/taxes/accounts by **mapping tables**, never by name or number alone.
3. Load in dependency order with idempotent upserts and checkpoints: couriers → parties/products → open sale orders → parcels (unique `(courier, tracking)`) → open remittances → opening balances through the ledger's own opening-entry mechanism, **never by inserting posted lines**.
4. Reconcile by company, currency and period: counts **and** values (REC-1..8 plus AR/AP, stock valuation, trial balance); signed variances only.
5. Dry run on a restored copy with `rehearse-upgrade`-style tooling; full rollback rehearsal; formal go/no-go.
6. Prohibited: silent destructive cleanup, creating a fake invoice/order to match a total, writing to posted history.

## 5. Release, rollback and continuity

| Item | Standard |
| --- | --- |
| Pre-change backup | `pg_dump -Fc` taken by `stage.sh upgrade` and `install-accounting` before any change; path printed with the rollback command `[V]` |
| Rollback | restore the printed dump into `mumtaz_pharma` and start `odoo-pharma` `[V]`; code rollback = redeploy previous tag; schema changes are additive by policy |
| Smoke | `stage.sh smoke`: HTTP, login, menus, mode, demo counts, production-refuses-demo (rolled back) `[V]` |
| Health | `stage.sh verify` prints module states and versions, hardening endpoint, crons active, journal-entry counts `[V]`; the parcels-by-next-step and reversal lines are new and **NOT RUN** |
| Release evidence | every environment change gets a `DEPLOY_LOG.md` entry with the pasted output `[V]`; release checklist: [RELEASE_GATE_CHECKLIST.md](RELEASE_GATE_CHECKLIST.md) |
| Backups and DR | a backup workflow exists (`.github/workflows/backup.yml`, `scripts/backup.sh`); **RPO/RTO, retention, off-site copy and restore drill are not defined** `[D-010]` |
| Monitoring | `docs/MONITORING.md` exists for the platform; pharma has none beyond `verify` `[P]` |
| Secrets | host-side env files, interactive entry, never committed `[V]` |

## 6. Release gate scoring (copy per release)

Use [RELEASE_GATE_CHECKLIST.md](RELEASE_GATE_CHECKLIST.md) with PASS / FAIL / NOT RUN / N/A and an evidence link per row. **Production** and **Business** rows can only be PASS after a signed go/no-go and signed UAT. The first scored release is the next one that includes the evidence-debt closure.
