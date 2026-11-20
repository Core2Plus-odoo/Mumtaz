# Deliverable 11 — Testing, reconciliation, migration and deployment strategy

Blueprint §14, §15 and §16.

---

## 1. Where testing stands

**[FACT]**

| | Count |
|---|---|
| Test functions in `addons/` | 57 — all in `c2p_project_tracker` |
| Modules with any test | 1 of 38 |
| Test functions in `c2p-delivery-system/delivery_api/tests/` | 28 |
| Tests **executed** anywhere, ever | **0** |
| CI jobs that run an Odoo test | **0** |
| CI jobs that install a module | **0** |

Blueprint §15.3 and §21.2 are explicit: a test not executed is not a passing test.
The honest status of every test in this repository is **NOT RUN**, and this
document will not describe coverage that does not exist.

## 2. Test layers and what each must prove

Blueprint §15.1, with the specific first target for each layer in this codebase.

| Layer | Tooling | First target here |
|---|---|---|
| Static / lint / secrets | flake8, `scripts/audit/*`, secret scan | Promote `faizy-ci.yml`'s stricter checks repo-wide (`CI-001`) |
| Unit | Odoo `TransactionCase` | `mumtaz_core`, `mumtaz_tenant_manager` — most-depended-upon, zero tests (`TEST-001`) |
| Contract | schema assertions on API + webhook payloads | Stripe webhook; e-invoice submission (`INT-001`) |
| Integration | `TransactionCase` with real DB, cross-module | `c2p_project_tracker` milestone sync (tests written, NOT RUN) |
| End-to-end process | `HttpCase` / tours | The Project→Cash reference transaction (Wave 2) |
| Role / security | `TransactionCase` with `with_user()` | Every role, **plus a negative test per role** |
| Reconciliation / property | invariant assertions | `amount_received` == reconciled payments; debits == credits |
| Migration | repeatable import + restart | The 41,182-lead CRM dataset |
| Performance | load with realistic volumes | CRM at 41k leads; the hourly per-lead unindexable scan found in `BD Engine 1` |
| UAT | business scripts + sign-off | Per role, Wave 5 |

### 2.1 The negative-test rule

**A security control with no negative test is an assumption.** Every role test is
paired with one proving the *wrong* role is refused **by the server**, not by a
hidden menu. Blueprint §10.1: "UI hiding alone is not security."

Specifically required for this codebase:
- a non-manager reading `project.project` gets **no** `contract_value` key at all
  (not a zero — `c2p_dashboard.py` already implements omission; a test must pin it);
- a Consultants-only user cannot reach Solutions task detail through any
  `sudo()` aggregation path;
- two users in two companies requesting the same record id get different answers;
- a portal user cannot reach a non-portal model through a custom controller route.

### 2.2 CI gates to add

| Gate | Fails the build on |
|---|---|
| Install | any module that will not install on a clean database |
| Odoo tests | `-i <module> --test-enable --stop-after-init` failing |
| Syntax hygiene | any `attrs=`, `<tree>`, `states={` in `addons/` |
| ACL coverage | a concrete model with no `ir.model.access` row |
| Money typing | `Float` with a money-shaped name; `Monetary` without `currency_field` |
| Dependency cycle | any cycle among own modules |
| Secret scan | a credential in source **or in documentation** |

The install gate matters most: it is the only check that proves a module can be
installed at all, and the production add-on mess (`OPS-001`) is exactly what
happens without it. The last gate is there because this audit's own first draft
put a production credential into a markdown file.

## 3. Reconciliation strategy

Blueprint §9 and §14.2. Reconciliation is a **test layer**, not a month-end
activity — the invariants get asserted in CI.

| Invariant | Assertion |
|---|---|
| Posted entries balance | per company and currency, with documented rounding |
| AR control account | == sum of open customer invoices, credits and receipts |
| AP control account | == sum of open bills, credits and payments |
| Bank | statement balance == reconciled ledger balance |
| Project receipts | `amount_received` == reconciled payments on linked invoices (`FIN-002`) |
| Project margin | revenue − subcontract − labour (`FIN-003`) |
| Intercompany | Consultants recharge == Solutions mirror, eliminations traceable |
| Dashboard figures | every tile == the records its drill-down returns |

The last one is the cheapest and most valuable: a test that opens a dashboard
payload and the drill-down domain behind it and asserts they agree. It catches the
entire class of bug where a dashboard quietly diverges from the ledger.

**No module may create a balancing line to mask a mismatch** (blueprint §6.4).
Mismatches go in a difference register with a root cause and an approver.

## 4. Migration strategy

Blueprint §14. **Nothing may be migrated yet** — the blocking gap is structural.

**[FACT] There is no external-identity infrastructure.** Of 978 declared fields,
**zero** carry `source_system` or `source_record_id`. Blueprint §14.1 item 3
requires stable external identities to avoid duplicates, and item 4 forbids
matching by name or number alone where collisions are possible.

This is not a theoretical concern here. Prior inspection of the live CRM found
41,182 leads of which ~86% have **no email address** — so name is the only
available match key, and name collisions in a 41k scraped-lead dataset are
certain. Migrating without external identities would create duplicates that
cannot afterwards be untangled.

### Sequence

1. **Source audit** — inventory every source model including inactive and
   cancelled records. Start with the known dataset: 41,182 leads, 29,484 archived
   by bulk action, `write_uid` = admin on 29,337 (`MIG-001`).
2. **Decide the history window and cutover** with the owner. Which of the 29,484
   archived leads are evidence and which are noise?
3. **Build `ARCH-001`'s mixin first.** No extract runs before
   `(source_system, source_record_id)` exists with a unique index.
4. **Explicit mappings** for partner, product, tax, account, UoM, journal,
   payment term and user. Never by name alone.
5. **Preserve lineage** — order lines to deliveries and invoice lines; bills to
   receipts; payments to invoice allocations.
6. **Idempotent upserts** in dependency order, with checkpoints and restartability.
7. **Reconcile counts *and* values** per blueprint §14.2 — by company, currency,
   period, status and document type.
8. **Difference register** with source id, target id, field, expected, actual,
   root cause, disposition, approver.
9. **Dry run in non-production with a rollback rehearsal**, then a formal go/no-go.

**Prohibited:** silent destructive cleanup of target records; creating a fake
invoice or order to make a total reconcile; writing to posted history. Posted
records are corrected by reversal or credit note, never by edit.

### The CRM patches already written

`c2p-delivery-system/docs/07-mumtaz-c2p-crm-findings.md` contains proposed
replacement logic for the CRM defects found in earlier sessions — including the
server action that hardcodes `user_id = 42` as assignment policy, and its hourly
per-lead unindexable scan. **It was deliberately not applied.** Applying it is
`MIG-002`, it changes live database records, and it needs a backup and the owner's
explicit go-ahead first.

## 5. Deployment strategy

**[FACT] Current state:** dev → staging (auto on `develop`) → production (manual
`workflow_dispatch`, with pre-deploy backup and health check), nightly backup at
02:00, deploy via `c2p-delivery-system/deploy/update.sh` on the VPS pulling `main`.

**That structure is sound.** The gaps are in evidence and recovery, not shape.

| Gap | Fix |
|---|---|
| CI does not install or test modules | `CI-002`, `CI-003` |
| No schema-compatibility check before deploy | add a `--stop-after-init` upgrade dry-run against a production restore |
| No documented RPO/RTO | state them; the nightly backup implies RPO ≤ 24h — confirm that is acceptable |
| **Backups never restore-tested** | blueprint §16 requires verified restores. A backup that has not been restored is a hope |
| No rollback for schema changes | document the per-release rollback, code **and** database |
| Production add-on layout broken | `OPS-001` — one checkout on the `addons_path` |
| Certificate renewal unmonitored | `MON-001` |

### 5.1 The restore test is the priority

Of everything in this section, **restore-testing the nightly backup is the single
highest-value action.** The repository has a backup job, a deploy job and a health
check — and no evidence that a backup has ever been restored successfully. Every
other recovery control assumes it works.

Run it against a throwaway database, record the output, and it doubles as the
disposable test database that Waves 1 and 2 need anyway.

## 6. Observability

**[DESIGN]** Blueprint §16. Required and absent: structured logs with correlation
ids (`ARCH-001` supplies the field), job-queue health, a business-exception
dashboard (failed webhooks, unreconciled documents, stuck approvals), and audit
access logging. `mumtaz_api_gateway` logs API usage, which is the only
observability in `addons/` today.

## 7. Performance

**[FACT, prior session]** One concrete problem is already identified: a server
action performing an hourly per-lead unindexable scan over a 41k-row table. 115
fields carry `index=True`, so indexing discipline exists in general.

**[DESIGN]** Load-test with realistic volumes before go-live: CRM at 41k+ leads,
dashboards under concurrent load, imports at full dataset size. Blueprint §16
warns specifically against unbounded list pulls, N+1 reads and simultaneous
expensive dashboard queries — the cross-company aggregation in
`c2p_dashboard.py` is the obvious candidate to profile first, since it fans out
across companies on every page load.
