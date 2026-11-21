# Implementation status, requirements traceability and change log

As of 2026-11-20. Scale (blueprint §23): **Not started / In progress / Evidence provided / Accepted / Exception approved**. *Accepted* needs a signed UAT; **no pharma module is Accepted** (UAT-001 not run).

## 1. Status by module (pharma tenant)

| Module | Version | Status | Executed evidence | What is NOT evidenced |
| --- | --- | --- | --- | --- |
| `pharma_core` | 19.0.1.0.0 | Evidence provided | in the 189/189 run | company scope; auditor role |
| `pharma_pk_tax_core` | 19.0.1.1.0 | Evidence provided | 176/176 and 189/189 runs | live data on the tax-link gate (no rule linked) |
| `pharma_reconciliation_hub` | 19.0.1.0.0 | Evidence provided | 189/189 | bank import; Operations write surface |
| `pharma_partner_stock` | 19.0.1.0.0 | Evidence provided (tests) | 176/176 | never run on a real stock location |
| `pharma_courier_cod` | 19.0.1.1.0 | Evidence provided (local) | ledger on the VPS to 1.0.0; flow layer: 92 tests green locally 2026-11-21 | flow layer not yet on the VPS |
| `pharma_courier_cod_accounting` | 19.0.1.3.0 | Evidence provided (local) | entries live on the VPS; 64 tests green locally 2026-11-21 incl. reversal, strict order, Entries to Post, kind tag + migration | 1.2.0 and 1.3.0 not yet on the VPS |
| `pharma_accounting_hardening` | 19.0.1.1.0 | Evidence provided | live, controls verified | none |
| `pharma_demo_data`, `pharma_courier_cod_demo`, `pharma_website_demo` | 1.1.1 / 1.3.0 / 1.1.0 | Evidence provided (local) | 1.3.0 seeding and its migration ran in the local upgrade rehearsal | not yet on the VPS |
| App-per-area menus, `stage.sh rehearse-upgrade`, `upgrade [module]` | n/a | Evidence provided (local, menus) | menus: real upgrade from `6b09f6d` passed locally 2026-11-21 | the `stage.sh` commands themselves **NOT RUN** on the VPS |
| Environment `mumtaz_pharma` | n/a | Staging, demo mode | last verify 2026-11-18 | state after pending slices unknown |

## 2. Requirements traceability (summary)

Process → requirement → entity/field → UI → permission → test, kept in [REQUIREMENTS_REGISTER.csv](REQUIREMENTS_REGISTER.csv) (26 items, all `Draft`) and, for the built COD process, in [PROCESS_LINKAGE_MATRIX.md](../architecture/PROCESS_LINKAGE_MATRIX.md) with the tests named in each module's `tests/`. Retro-fitting requirement IDs onto the 231 existing test methods is backlog DOC-002; today the link is by test name and the presenter-script IDs (T1–T10, R1–R7, P1–P3, S1–S3, C1–C17).

## 3. Pending tasks (ordered)

1. OPS-001 `test-combined` → 2. OPS-002 `rehearse-upgrade` → 3. OPS-003 owner-approved upgrade, verify, smoke → 4. OPS-004 / UAT-001 owner browser pass → 5. Gate-0 decisions D-001..D-012 → then the P1 backlog.

## 4. Change log (branch `pharma-erp-v0.1`, newest first, selected)

| Date | Commit | Change | Verified? |
| --- | --- | --- | --- |
| 2026-11-21 | `8204b42` | Base flow tests assert base rules directly | 0 failed of 222, local |
| 2026-11-20 | `8db4cff` | COD process flow: stage, next step, owner, queues, strict order, Entries to Post | local 222/222 after the test fix; **VPS NOT RUN** |
| 2026-11-20 | `f687c3b` | One app per area; `rehearse-upgrade` | static only, **NOT RUN** |
| 2026-11-18 | `a3f31ba`, `7d30d2b` | Reversal of posted entries; `upgrade [module]` | static only, **NOT RUN** |
| 2026-11-18 | `d95ab00` | Collection entry (1c) | **189/189**, live |
| 2026-11-18 | `b8a61d4` | Settlement entry (1b) | **148/148**, live |
| 2026-11-18 | `84beb56`, `3ecb8c8`, `bf79bd4` | Partner stock; tax-link; hide support button | **176/176**, live |
| 2026-11-18 | `4ab0787`, `21263ee`, `2f7c180` | Courier COD ledger + statement upload; seeder `_order` shadow fix; neutralize flag fix | 130 tests: first run 129 + 1 test defect (fixed), then green; live |
| 2026-11-18 | `85250eb`, `f498fda` | Accounting kit review, hardening module | 62/62, live |
| 2026-11-18 | `3f3a546`, `7a48c39` | Wellness storefront, demo seeder | 54/54, live |
| 2026-11-18 | `c9a8605` … `8757c5c` | Pharma ERP v0.1 and the staging kit | 34/34, live |
| 2026-11-20 | *(this change set)* | `docs/erp/` audit, architecture, standards, roadmap, backlog | documentation only |

Defects found and fixed along the way (kept for lessons): seeder helper `_order` shadowed a reserved model attribute (module failed to load); neutralize flag compared against `True` while Odoo stores `true` (cron stayed active); a hardening test asserted on a comment; demo logins collided with test fixtures; `stage.sh` heredoc and quoting defects. The accounting hardening was found uninstalled once, cause not established, now surfaced by `verify`.
