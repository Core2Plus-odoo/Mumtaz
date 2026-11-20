# 01. Current-system technical and functional audit

Date: 2026-11-20 · Scope: repository `Core2Plus-odoo/Mumtaz` at branch `pharma-erp-v0.1` (head after `8db4cff`), plus facts the owner pasted from the VPS on 2026-11-18. Method: static inspection of the working tree; no code executed for this audit.
Labels: `[V]` verified (evidence given) · `[R]` reported by the owner from the VPS, not re-verified · `[A]` assumption · `[D]` decision needed.

## 1. Executive summary

1. `[V]` This is **not one ERP; it is a monorepo of several products on one Odoo 19 base**: the Mumtaz SaaS platform and marketplace (33 addons), the Jawhar jewellery vertical (14), a CFO/AI-CFO stack (4), a project tracker and command centre (2), and the **pharma tenant (10 addons)**, plus non-Odoo apps (C2P Agency OS in FastAPI, ZAKI server, Faizy AI, WordPress sites). The "complete enterprise ERP" of the directive has to be defined *per tenant/vertical*, not for the repo as a whole (decision D-001).
2. `[V]` The platform choice is already made by the code: **Odoo 19, extension add-ons, database per tenant** (ADR-001/002/012 are verifiable, see the decision register). No greenfield stack is needed or justified.
3. `[V]` The **pharma tenant is the only part with a disciplined delivery trail** (tests, staging script, deploy log). Its verified state is narrower than its written state: tests were last *executed* green at **189 of 189** on 2026-11-18 14:58 UTC, covering everything up to the COD collection entry. Four later pieces are **written but NOT RUN**: reversal of posted entries, the one-app-per-area menu split, the COD process flow, and the three cherry-picked commits already verified at 176 (see section 6).
4. `[V]` The largest structural gap against the blueprint is **company scope and record-level security**: the 18 pharma models have no `company_id` and no record rules; money is stored as `Float` (46 fields) not `Monetary` (0). This is safe only while a pharma database holds exactly one legal entity and one currency `[A]` (decision D-003).
5. `[V]` Test coverage is very uneven: pharma 231 test methods, jewellery 248, project tracker 57, and **2 test methods across the other ~49 platform add-ons** (tenant manager, control plane, marketplace, CFO, ZAKI, e-invoicing, API gateway, billing, AI, voice). Money-moving platform code (`mumtaz_billing_stripe`, `mumtaz_einvoicing`, `mumtaz_cfo_*`, `mumtaz_zaki`) is effectively untested.
6. `[V]` There is **no CI that runs the pharma Odoo tests**. CI runs manifest lint, flake8, bandit; Odoo module tests run in CI only for jewellery (`jewel-odoo-tests.yml`). Pharma tests run only through `deploy/pharma-staging/stage.sh` on the VPS.

## 2. Platform and environment (verified)

| Fact | Evidence |
| --- | --- |
| Odoo **19.0**, Community. Staging build `Odoo Server 19.0-20260719` | `Dockerfile` `FROM odoo:19`; `stage.sh preflight` output 2026-11-18; original task named Community |
| 63 custom add-ons, all `19.0.x`, **no module-level dependency cycles**, max depth 8 | manifest analysis, [MODULE_DEPENDENCY_MAP.md](../architecture/MODULE_DEPENDENCY_MAP.md) |
| Tenancy: **one isolated Odoo database per tenant**, registry model `mumtaz.tenant`, central auth in `zaki-server` | `docs/ARCHITECTURE.md` §2; `addons/mumtaz_tenant_manager` |
| Pharma tenant: DB `mumtaz_pharma`, unit `odoo-pharma`, dbfilter `^mumtaz_%d$`, ports 8076/8077, TLS, neutralized, `pharma.mode=demo` | `deploy/pharma-staging/`, `docs/pharma/DEPLOY_LOG.md` |
| Standard apps on the pharma install list: `account, sale_management, purchase, stock, mrp, website_sale, contacts` + third-party accounting kit (pinned commit, source not vendored) + our hardening module | `stage.sh` `MODULES` |
| Standard apps referenced by *any* custom add-on: mail, account, base, web, crm, stock, sale_management, website, portal, purchase, sale, project, website_blog, contacts, website_sale | manifest scan |
| **Not referenced by any custom add-on:** hr, hr_payroll, hr_holidays, hr_attendance, hr_expense, mrp (installed on pharma staging, unconfigured), maintenance, fleet, helpdesk, point_of_sale, stock_account, purchase_requisition, account_asset, quality, industry_fsm, hr_timesheet | manifest scan (a database may still have them installed `[A]`) |
| Production: Hostinger VPS `187.77.128.199`, repo at `/opt/mumtaz`, **deploys go to `main`**; feature branches never reach production | root `CLAUDE.md` |
| The VPS runs several independent Odoo instances; two of them have no `db_name`, and two vhosts proxy websocket to wrong ports | `[R]` owner-pasted discovery output 2026-11-18; production, untouched |
| Branches: 40+ remote branches (`claude/*`, `jawhar-*`, `jewel-*`, `pharma-*`); 236 commits | `git branch -a` |

## 3. What exists, by product

| Product | Add-ons | Models | Tests | Verified state |
| --- | ---: | ---: | ---: | --- |
| **Pharma tenant** (COD, tax gate, reconciliation hub, partner stock, demo, hardening) | 10 | 18 `_name` models (15 with declared fields) + extensions | 231 defined (189 + 14 + 28 executed or expected, see §6) | Tests executed green on staging up to 189/189 on 2026-11-18; later slices NOT RUN |
| **Jawhar jewellery** (piece inventory, pricing, VIP, AML, kiosk, AI, API, stores) | 14 | 20 with declared fields | 248 | CI runs its Odoo tests; design docs in `docs/mumtaz-jewel/` (roadmap rev. 3, decisions D1…D8) |
| **Mumtaz platform** (tenant manager, control plane, billing, marketplace, portals, SSO, routing, theme, API gateway, e-invoicing, ZAKI, AI, voice, lead tools) | 33 | 59 with declared fields | 2 | Not independently verified in this audit; architecture documented in `docs/ARCHITECTURE.md` |
| **CFO stack** (`mumtaz_cfo_base/ingestion/transactions/toolkit`) | 4 | 7 with declared fields | 0 | 7 `company_id` fields across the family; untested |
| **C2P project tracker / command centre** | 2 | 3 with declared fields (6 `_name` classes in the tracker) | 57 | Tracker has ACL + rules + 57 tests; command centre is a single dashboard model |
| **C2P Agency OS** (FastAPI + one-file console; presales to deploy pipeline) | n/a (not Odoo) | n/a | `delivery_api/tests/test_phase1.py` | Out of scope of the ERP directive; it is a delivery tool, not a tenant ERP `[A]` |

## 4. Functional audit of the one tenant that is an ERP: pharma (verified from code and tests)

| Capability | What exists | Evidence |
| --- | --- | --- |
| Tax control | Effective-dated, **approved-only** PK tax rules; SKU classification; sale confirm and customer invoice post are **blocked** when a product has no approved rule; opt-in link of a rule to a standard `account.tax` with a hard equality check | `pharma_pk_tax_core`, 30 tests |
| Reconciliation hub | Runs, items, exceptions; exact-reference > one-to-many > amount+date matching; **maker-checker closure**; immutable raw-event ingestion with duplicate and conflict handling | `pharma_core`, `pharma_reconciliation_hub`, 16 tests |
| Courier COD ledger | Parcel ledger (declared/collected/remitted), ageing from delivery date, remittance slips with itemised deductions, **statement upload** (validate then build), six exception categories, daily cron | `pharma_courier_cod`, 75 executions on staging (82 now defined: 7 added by the unrun flow tests) |
| COD accounting | Draft-only entries: collection (Dr clearing, Cr customer receivable) and settlement (Cr clearing, Dr bank and deductions, difference line); **reversal** of posted entries as drafts (written, not run); **strict order** with logged override (written, not run) | `pharma_courier_cod_accounting` |
| Partner stock | Distribution Partner roll-forward derived from done stock moves | `pharma_partner_stock`, 7 tests |
| Process flow | Stored stage / next step / owner per parcel, work queue, pipeline pivot, accountant's Entries to Post queue (written, not run) | `docs/pharma/COD_PROCESS_FLOW.md` |
| Storefront and demo | Wellness-themed storefront, one app per area, fictional demo data for every scenario | `pharma_website_demo`, `pharma_demo_data` |

## 5. Gaps against the blueprint (verified unless marked)

| # | Gap | Blueprint reference | Severity | Evidence |
| --- | --- | --- | --- | --- |
| G-1 | No `company_id` and no `ir.rule` on any pharma model; admin write roles are global | §4.2 company ownership, §10, §17.2 blocker "record rules leak company data" | **High if a tenant ever holds 2 legal entities**; acceptable for one entity | grep: 0 `company_id` fields in `pharma_*/models`, 0 `ir.rule` records |
| G-2 | Money as `fields.Float(digits=(16,2))` with no currency; single-currency assumed | §4.2 fixed-point money, currency context | Medium | 46 Float, 0 Monetary in `pharma_*` |
| G-3 | No chart-of-accounts localization for Pakistan (generic COA on staging); no fiscal lock-date policy configured | ADR-006, ADR-011, §9 | High before any real accounting | `stage.sh` install list has no `l10n_pk`; DEPLOY_LOG notes generic chart |
| G-4 | Collection entry reconciled to a **real posted invoice** has never been exercised; reversal of a reconciled entry leaves reconciliation to a human | §6.1, §15.2 | High (the money loop) | tests post misc entries only |
| G-5 | `sudo()` used 33 times in pharma (deliberate: Finance creates drafts without Accounting rights); no audit that each is least-privilege | §10.1, §17.1 | Medium | `grep -c "sudo()"`; rationale documented per call site only in module docs |
| G-6 | No Auditor role, no delegation, no documented segregation-of-duties matrix beyond maker-checker and accountant-posts | §10.1 | Medium | `pharma_core/security` has 4 roles |
| G-7 | Pharma has **no CI**; only a manual VPS gate | §3.5, §16 | High (regression risk) | `.github/workflows/` |
| G-8 | Platform add-ons carry money/billing/e-invoicing logic with 2 tests in total | §15 | High | test scan |
| G-9 | No requirements register, ADRs, data dictionary or traceability existed before this audit | §2, §20 | Medium | `docs/` listing; now started in `docs/erp/` |
| G-10 | No bank-statement import and matching against remittances; no freight validation against rate cards; returns not tied to tax-event reversal | blueprint FIN-03, SLS-03 | Medium | open items in DEPLOY_LOG |
| G-11 | HR, payroll, manufacturing configuration, maintenance, helpdesk, fixed assets: no custom or configured capability | §5 registry | Unknown priority until scope is signed (D-002) | manifest scan |
| G-12 | Standard accounting on Community relies on a **third-party kit** (pinned, hardened) | ADR-004 | Medium (vendor dependency, support call-home disabled by our hardening) | `docs/pharma/ACCOUNTING_KIT.md` |

## 6. Verification status of the pharma work (honest ledger)

| Slice | State | Executed evidence |
| --- | --- | --- |
| Core, tax gate, hub, demo, website, accounting kit + hardening | Live on staging | tests green; smoke green |
| Courier COD ledger + statement upload (1) | Live on staging | green |
| COD settlement entry (1b), collection entry (1c) | Live on staging | `test-combined` **189/189**, `upgrade` + `smoke` green, 2026-11-18 |
| `pharma-functionality` cherry-picks (tax link, partner stock, hide support button) | Live on staging | `test-combined` **176/176**, upgrade + smoke green |
| Reversal of posted entries (cherry-picked `de063d4`) | **Written, NOT RUN** | static checks only; 14 tests expected |
| App-per-area menu split + `rehearse-upgrade` | **Written, NOT RUN** | static checks only |
| COD process flow, queues, strict order | **Written, NOT RUN** | static checks only; about 28 new tests |
| **Acceptance by a business owner** | **None** | no UAT sign-off exists for any slice |

The next smallest safe task is therefore **not new code**: it is to burn down this evidence debt (backlog items `OPS-001..004`).

## 7. Risks that could cause irreversible harm (none triggered by this audit)

- Writing to a production database or `main`: not done. All work is on `pharma-erp-v0.1`; the VPS pulls `main`.
- Posted fiscal history: the pharma modules never post; reversal creates drafts; migration scripts only *tag* existing draft/posted COD entries (SQL `UPDATE` of a custom tag column, never amounts).
- Dropping the shared "Pharma" root menu on upgrade: guarded by `stage.sh rehearse-upgrade` (NOT RUN yet).
- Unreviewed `sudo()` creating accounting entries on behalf of non-accountants: mitigated by Finance-group checks inside each action and draft-only entries; still needs the review in G-5.

## 8. Items this audit could not establish (state, do not guess)

Client/legal entity count and countries `[D]`; whether any tenant besides pharma is live and on which databases `[R]`; production data volumes; what `test.yml`'s test job executes; the true state of the platform add-ons beyond their manifests; HR/payroll scope; backup retention and RPO/RTO; whether a Pakistan chart of accounts and e-invoicing gateway are required for the pharma tenant.
