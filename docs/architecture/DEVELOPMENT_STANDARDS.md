# Deliverable 7 — Development standards and coding conventions

These are the rules for `addons/`. They are written **from what this codebase
already does well**, so adopting them is mostly ratifying existing practice rather
than imposing new process. Where a rule is new, it is marked **[NEW]**.

Governing references: `docs/erp-standard/ERP_MASTER_BLUEPRINT.md` §17 and §21;
root `CLAUDE.md` for repository-specific knowledge.

---

## 1. Odoo 19 syntax — ratify what is already universal

**[FACT] The codebase is already compliant on every point below** (0 violations
across ~200 XML files and 21,772 Python lines). Make it explicit so it stays true.

| Rule | Status |
|---|---|
| `<list>`, never `<tree>` | 0 violations |
| Column/field visibility via `invisible="..."` expressions, never `attrs=` | 0 violations |
| No field-level `states={...}` | 0 violations |
| `models.Constraint` / `models.Index` over raw `_sql_constraints` | in use |
| `res.groups.privilege` + `user_ids` (not `category_id` / `users`) | in use |
| `ir.cron` without `numbercall` / `doall` | in use |
| OWL 2 components in the `actions` registry | in use (`c2p_project_tracker`) |

**[NEW]** CI must enforce these rather than relying on care. A grep job costs
seconds — see §7.

## 2. Money

1. **All monetary amounts are `fields.Monetary` with an explicit
   `currency_field`.** Currently 34/34 compliant. Never `fields.Float`.
   - One outstanding violation to fix: `mumtaz.module.bundle.monthly_price`.
2. **[NEW]** Store rate context with any converted amount: source rate, rate
   timestamp, transaction currency, company currency (blueprint §4.2). No model
   does this today; required for any multi-currency transaction.
3. **[NEW] Never store a derived monetary amount that the ledger already knows.**
   Compute it from `account.move`. This rule exists because
   `project.project.amount_received` and `media.plan.net_revenue` both violate it
   and both will drift from the accounts.

## 3. Security — server-side, always

1. Every concrete model gets an `ir.model.access` row. **62/62 today — keep it.**
2. **[NEW]** Every model holding tenant- or company-scoped rows gets an `ir.rule`,
   or a comment in `security.xml` stating why it does not need one. 40 of 62
   models currently have neither.
3. **[NEW]** Company rules use `[('company_id', 'in', company_ids)]` — never
   `= user.company_id.id`, which breaks for multi-company users. 17 rules already
   use the correct form; 1 does not.
4. **[NEW]** Any field holding cost, margin, commission, salary or a credential
   carries `groups=`. Credentials already comply; commercial fields in
   `mumtaz_media_buying` do not.
5. **Every `.sudo()` gets a comment on the line above saying why it is safe.**
   `c2p_project_tracker` is the reference implementation: a `_check_member()`
   guard on every entry point, aggregates returned rather than records, and
   restricted keys **omitted** from the payload rather than zeroed — because a
   zero is a readable value and an absent key is not.
6. **[NEW]** No new module may add a portal controller route that standard
   `portal` already serves.

## 4. The §7.1 entity contract

**[NEW]** Every new transactional model inherits the project mixin (to be built,
`ARCH-001`) providing `source_system`, `source_record_id`, `version`,
`approval_state`, `approved_by`, `approved_at`. Do not add these field-by-field.

Rationale: five of §7.1's required concepts are absent from all 62 models. Adding
them per-model means 310 edits and guaranteed inconsistency; one mixin means one
review.

## 5. Extension discipline

1. `_inherit` + `super()` to extend standard behaviour. `mumtaz_einvoicing`'s
   `action_post` override is the reference pattern — **copy it**.
2. Never add `groups=` to a *standard* Odoo field. Declare a new field with a
   `c2p_`/`mumtaz_` prefix instead. `c2p_project_tracker` does this deliberately
   (`c2p_currency_id`, `c2p_sale_order_id`, `c2p_company_currency_id`) and the
   reason is worth stating: restricting a core field breaks standard views for
   every user who lacks the group.
3. No raw SQL that bypasses the ORM. **0 violations today.**
4. No core forks. **0 today.**
5. New modules declare complete `depends`; cycles are a build failure.
6. **[NEW]** A module must not depend on a module in a higher layer
   (`MODULE_DEPENDENCY_MAP.md` §2). `mumtaz_portal_routing → mumtaz_cfo_base` is
   the existing violation.

## 6. Tests — the rule this repository most needs

**[NEW] A pull request that adds a model, a state transition, a monetary
computation or an access rule and adds no test is not reviewable.**

Minimum per transactional slice (blueprint §15.1):

| Layer | Requirement |
|---|---|
| Unit | computed fields, constraints, state guards |
| Security | one test per role *and* one negative test proving the wrong role is refused |
| Integration | the cross-module effect, against a real database |
| End-to-end | the business process hop the slice completes |
| Reconciliation | the invariant (totals balance, subledger ties to control account) |

`addons/c2p_project_tracker/tests/` is the structural template: `common.py` for
fixtures, then one file per concern (`test_security`, `test_commercials`,
`test_hygiene`, `test_sync`, `test_dashboard`, `test_health`).

**And the rule that goes with it:** a test that has not been executed is reported
as **NOT RUN**, never as passing. All 57 tests in this repository are currently
NOT RUN. Blueprint §21.2 forbids fabricating test output; so does root `CLAUDE.md`.

## 7. CI gates

**[FACT]** CI today: manifest validation, flake8 `E9,F63,F7,F82`, and — only for
`faizy/` — compileall plus manifest/ACL/view cross-checks.

**[NEW] Promote the `faizy-ci.yml` checks to the whole repository.** They are
already written, already working, and strictly better than what `addons/` gets.
Then add:

| Gate | Fails on |
|---|---|
| Syntax hygiene | any `attrs=`, `<tree>`, `states={` in `addons/` |
| ACL coverage | a concrete model with no `ir.model.access` row (`scripts/audit/acl_coverage.py`) |
| Money typing | `fields.Float` with a money-shaped name; `fields.Monetary` without `currency_field` |
| Dependency cycles | any cycle among own modules |
| Module install | `-i <module> --test-enable --stop-after-init` on a throwaway database |
| Odoo tests | the 57 existing tests actually run |

The install gate is the important one. It is the only check that proves a module
can be installed at all, and the production add-on mess documented in the audit
(§6) is exactly what happens without it.

## 8. Documentation obligations per change

Blueprint §20.1. A change is not done until:

- `docs/modules/MODULE_SPEC_<ID>.md` reflects it (template in `docs/erp-standard/templates/`)
- `docs/architecture/DATA_DICTIONARY_AS_IS.csv` is regenerated (`scripts/audit/fields.py`)
- a posting-rule entry exists if the change touches money
- an ADR exists if an alternative was rejected
- `docs/project/DECISION_REGISTER.md` records any new open decision
- `docs/05-build-log.md` gets its chronological entry (existing repo convention —
  keep it; it is the most useful document in the repository)

## 9. Response format

Every development task reports in the blueprint §21.1 format: `TASK`,
`REPOSITORY STATUS`, `PROCESS IMPACT`, `PLAN`, `IMPLEMENTED`, `VERIFIED`,
`RECONCILIATION`, `DECISIONS/BLOCKERS`, `NEXT ACTION`.

`VERIFIED` carries the actual command and its actual output, or `NOT RUN` with the
reason. There is no third option.

## 10. Prohibited

From blueprint §21.2, plus two learned in this repository:

- No claiming completion from generated code or a screenshot.
- No deleting or skipping a test to go green.
- No fabricated test output, record counts or performance figures.
- No writing to posted accounting history.
- No secrets in git — and **[NEW]** no secrets in repository *documentation*
  either. This audit originally drafted a production credential into
  `01-AS-IS-AUDIT.md`; the safety classifier caught it. Describe exposures, cite
  the host, never the value.
- **[NEW]** No reporting a measurement without re-checking it by hand when it is
  surprising. This audit's first ACL-coverage pass reported 69/106 because the
  regex matched `_rec_name` and `brand_name`. The corrected answer was 62/62 —
  the opposite conclusion. Anchor your patterns and verify your outliers.
