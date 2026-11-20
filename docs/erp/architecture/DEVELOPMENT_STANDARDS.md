# 07. Development standards and coding conventions (Odoo 19)

`MUST` / `SHOULD` / `MAY` as in the blueprint. Items marked **(lesson)** record a real defect or near-miss from this repository so the rule has a reason. Platform: Odoo 19.0 Community; check the installed build before relying on any API.

## 1. Repository and module layout

- A module is `addons/<prefix>_<area>/` with `__manifest__.py` (declared `depends` only; `data` ordered security → data → views → menus → cron; `version` `19.0.x.y.z`; `license`). Prefix by product: `pharma_`, `mumtaz_`, `c2p_`. Names are **generic** (no client, courier, partner or product names in code, data or docs) **(project rule)**.
- Layers: `models/` (domain), `views/` (UI), `security/` (ACL, rules, groups), `data/` (sequences, crons, noupdate config), `tests/`, `migrations/<version>/post-migrate.py`, `static/` (icons, assets).
- A tenant-optional capability lives in its **own add-on above** the lean one (for example accounting entries in `pharma_courier_cod_accounting`, not in the ledger). Demo data and demo websites sit at the top and never below.
- Menus: **one app per business area**, owned by the module that provides it, own icon; new root menu ids when re-parenting **(lesson: Odoo does not clear a menu parent when a data file drops it, and a menu with children cannot be deleted on upgrade; verify with `stage.sh rehearse-upgrade`)**.

## 2. Models and fields

- MUST give every model `_description`; every business model states its **owner** and **company scope**; MUST NOT use `_name`-less `_inherit` lists that hide ownership.
- MUST NOT define a method or attribute that shadows a reserved model attribute: `_order`, `_name`, `_table`, `_rec_name`, `_fold_name`, `_description`, `_inherit`, … **(lesson: a seeder helper named `_order` replaced the default sort order and broke module load with `can't adapt type 'method'`)**. A scan for this runs in review.
- Money: SHOULD use `fields.Monetary` with a `currency_id`; existing `Float(16,2)` money fields are a recorded gap (G-2) and MUST NOT be extended without a migration plan. Quantities use UoM precision. Never sum floats across currencies.
- Company: every transactional model MUST carry `company_id` (default `env.company`) with a consistency constraint to its parents, or record a signed single-entity decision (D-003).
- Selections: define the list as a module constant; extensions use `selection_add=` with `ondelete=` for each added value.
- Many2one to financial or stock documents: `ondelete="set null"` or `"restrict"`, **never cascade** over posted history.
- Constraints: Odoo 19 style `models.Constraint("UNIQUE(...)", "message")`; Python `@api.constrains` for rules the database cannot hold. Database constraints are authoritative; UI validation is a courtesy.
- Computed stored fields declare complete `@api.depends`; when an extension changes inputs it overrides the compute and **adds** its depends. Anything time-dependent (ageing) is refreshed by an explicit action or cron, never assumed.
- Odoo 19 specifics already encountered: `group_ids` (not `groups_id`) on users; `<list>` (not `<tree>`); `invisible="expr"` (not `attrs`); `_read_group(domain, groupby, ["__count"])`; `ir.cron` has no `numbercall`; `--without-demo` is a plain flag; `env.add_to_compute()` + `flush_all()` to force recompute.

## 3. Business actions, state and approval

- Business rules live in **model methods** (`action_*`), not in views or JS. Each action checks the caller's group **inside the method** (UI `groups=` only hides a button, it is not security) **(lesson: every Finance-only action calls `has_group` itself)**.
- State is an explicit `Selection`; transitions go through named actions that validate, then write; no free-form writes to state from the UI. Locked records enforce locks in `write()`/`unlink()` (for example reconciled remittances).
- Maker-checker: the actor who proposes cannot approve; enforced in the approving method and covered by a negative test.
- Posting: custom code MUST NOT write ledger lines directly or post silently. It creates **draft** entries through the ORM and leaves posting to an accountant; corrections use native reversal; nothing deletes or edits a posted record.
- `sudo()` MUST be narrow, justified in a comment ("why this actor lacks the right, what is created"), preceded by the permission check on the real user, and MUST keep the real user (`with_user`/`sudo()` retains uid) so `create_uid` records who acted. Every `sudo()` is listed in review.
- Idempotency: ingestion and seeding use natural keys; running twice changes nothing; reprocessing an identical row is a no-op; a changed row in a later file is a new event, not a conflict.

## 4. Security artefacts

- Every model has an `ir.model.access.csv` row per group (default deny). Models with company or owner scope get an `ir.rule`; this is currently **missing for all pharma models** (backlog PHA-SEC-001).
- Sensitive fields (salary, bank, cost, margin) use `groups=` on the field **and** are exercised by a role test.
- Secrets never enter git, fixtures, logs, prompts, deploy logs or screenshots; credentials are typed interactively on the target host and are never recorded **(project rule, followed throughout the pharma deployment)**.

## 5. Tests (an executed pass is the only evidence)

- Tag: `@tagged("post_install", "-at_install", "<area>")`. Run on a **throwaway database** with the same module list as production, never against production data.
- Fixtures are synthetic and prefixed so they cannot collide with seeded demo logins **(lesson: `demo_*` logins collided with seeded users)**.
- Each module ships tests for: happy path, partial/cancel/reversal, guard failures per role, duplicate/idempotent input, constraint violations, and (for money) arithmetic invariants.
- Do not assert on defaults you do not control (for example whether an internal user can read journal entries) **(lesson)**; assert on the behaviour you implemented.
- A failing test is fixed by fixing the code or the test's premise, never by skipping it. Report `0 failed, 0 error(s) of N`, the command, the date and the build; use `NOT RUN` otherwise.
- Odoo-specific cache note: after a rolled-back transaction, read config parameters by SQL, not the ORM cache **(lesson)**.

## 6. Migrations and upgrades

- Every schema or data-file change that affects an existing database bumps the module version and, if data must be transformed, adds `migrations/<new version>/post-migrate.py`. Seeders are idempotent so `-u` re-runs them safely.
- Backfills are **SQL on custom columns only** (for example tagging COD entries), never on amounts or posted accounting fields.
- Before any live upgrade: dump, `stage.sh test-combined` green, `stage.sh rehearse-upgrade` PASSED, then a named owner go; the upgrade re-runs neutralize on a neutralized database. Roll back by restoring the printed dump.

## 7. UI

- Prefer standard list/form/pivot/search views and server actions; no custom OWL unless a standard component cannot do the job. Labels use `_()`; Arabic/RTL where the product scope says so.
- Every list that represents work has a search view with owner and step filters; every KPI drills to the records behind it.

## 8. Git, CI and review

- Work on an issue-linked branch; nothing reaches `main` without the owner; production deploys come from `main` only. Commit messages explain *why*, state what was verified, and end with the attribution trailer.
- CI MUST run for every pull request: manifest lint, flake8 (repo `.flake8`), bandit, and the module's Odoo tests (currently only jewellery has the Odoo-test workflow; pharma needs it, backlog PHA-CI-001).
- Review checklist: reserved-name scan, `sudo()` list, ACL/rule diff, migration reviewed, no secrets, tests executed (not assumed), docs and dictionary updated.

## 9. Documentation duties per change

Module spec (`templates/MODULE_SPEC_TEMPLATE.md`), data-dictionary rows, requirement and test IDs in the register, ADR for any architectural choice, deploy-log entry with evidence for any environment change, changelog line.
