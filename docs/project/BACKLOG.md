# Deliverable 12 — Prioritized implementation backlog with acceptance criteria

Ordered by **business risk × dependency position**, not by effort. Every item has
a GIVEN/WHEN/THEN acceptance criterion, because blueprint §15.3 forbids calling
anything done without evidence.

Priority: **P0** act now · **P1** next wave · **P2** scheduled · **P3** on decision

---

## P0 — No dependencies, no decisions needed, start now

### `SEC-000` · Close the production exposure
**Wave 0.5 · Ops, not code · Highest severity in the audit**

The production VPS permits direct inbound access to the Odoo application ports
from any address, and an internet-reachable instance can select a live business
database protected only by a default-strength administrator credential. Reported
in three prior sessions; unremediated.

> **GIVEN** the production VPS
> **WHEN** the Odoo application ports are reached from an address outside the host
> **THEN** the connection is refused by the firewall (only 80 and 443 are public)
> **AND** no database is reachable with a default or dictionary administrator password
> **AND** the rotated credential is stored in the secret manager, never in git

*Evidence:* firewall rule listing, a refused external connection, a password-change confirmation. No credential value in any artefact.

### `SEC-001` · Rename one of the two "Super Admin" groups
**Wave 0.5 · ~1 hour**

`mumtaz_core.group_mumtaz_super_admin` ("Mumtaz / Super Admin") and
`mumtaz_control_plane.group_mumtaz_super_admin` ("Mumtaz Super Admin") are
different groups whose names differ by a slash. Credential field access depends on
picking the right one.

> **GIVEN** an administrator on the Settings → Groups screen
> **WHEN** they search for an administrative group
> **THEN** every group name states unambiguously what it governs
> **AND** no two groups in different modules share a display name or an XML id
> **AND** a CI check fails on a duplicate group display name

### `MON-001` · Certificate-expiry and uptime monitoring
**Wave 0.5**

One hosted domain's certificate has already been observed renewing out of step
with the others. A silent renewal failure becomes a client-visible outage — which
has already happened once, during a live prospect evaluation.

> **GIVEN** any hosted domain
> **WHEN** its certificate is within 14 days of expiry, or it fails an HTTP check
> **THEN** an alert reaches an on-call human before a client notices
> **AND** the check covers apex **and** `www` for every domain

### `OPS-001` · Resolve the production add-on layout
**Wave 0.5 · Blocks `DEC-001`**

Two identical 37-module checkouts plus a third; `/opt/mumtaz/addons` not on the
`addons_path`; `c2p_master_agent` installed with no source in any checkout.

> **GIVEN** the production host
> **WHEN** `addons_path` is read from the active Odoo config
> **THEN** exactly one checkout per instance is listed, and it is the git checkout
> **AND** every installed module resolves to source in that checkout, or is uninstalled
> **AND** the layout is recorded in `docs/operations/DEPLOYMENT_RUNBOOK.md`

---

## P1 — Wave 1: prove what exists

### `DEC-001` · Installed-module baseline for all five instances
**Blocks Waves 1–2 · Must run on the VPS · ~half a day**

> **GIVEN** each of the five Odoo instances
> **WHEN** the baseline is captured
> **THEN** `docs/project/INSTALLED_BASELINE.md` states, per instance: database,
> `dbfilter`, Odoo version, and every installed module with its version
> **AND** each of the 38 repository modules is marked installed-where or nowhere
> **AND** the 40 models with no `ir.rule` are each classified as *isolated by database boundary* or *exposed*

### `CI-001`–`CI-003` · Working CI gates
**Depends on DEC-001**

`faizy-ci.yml` already runs compileall plus manifest/ACL/view cross-checks — the
strictest checks in the repository — and they apply only to `faizy/`. Promote
them, then add install, test, hygiene, ACL-coverage, money-typing, cycle and
secret gates.

> **GIVEN** a pull request touching `addons/`
> **WHEN** CI runs
> **THEN** every touched module installs on a clean database and its tests execute
> **AND** the build fails on any `attrs=`, `<tree>` or `states={`
> **AND** the build fails on a concrete model with no `ir.model.access` row
> **AND** the build fails on `Float` with a money-shaped name, or `Monetary` without `currency_field`
> **AND** the build fails on a credential in source **or documentation**

### `PRJ-002` · Install and actually run `c2p_project_tracker`
**Depends on DEC-001, CI-002**

The best-engineered module in the repository: 89 fields, 2 OWL dashboards, 2 QWeb
PDFs, 5 constraints, 57 tests — **never installed, never run, never rendered.**

> **GIVEN** a restored copy of the production database with crons and mail servers disabled
> **WHEN** the module is installed per `addons/c2p_project_tracker/scripts/backup_and_install.md`
> **THEN** installation completes with no error
> **AND** all 57 tests execute, with pass/fail recorded verbatim — not summarised
> **AND** both dashboards render, in light and dark mode
> **AND** both PDFs render on wkhtmltopdf 0.12.x with correct pagination
> **AND** a non-manager user receives **no** `contract_value` key in the dashboard payload (absent, not zero)

### `TEST-001` · First tests for `mumtaz_core` and `mumtaz_tenant_manager`
**Depends on CI-002**

The two most-depended-upon own modules (8 and 6 dependents). Both untested. A
breaking change in either reaches most of the platform.

> **GIVEN** either module
> **WHEN** its test suite runs
> **THEN** every concrete model has a create/read/write/unlink test per intended role
> **AND** each has a negative test proving an unauthorised role is refused server-side
> **AND** credential fields are unreadable by every role that lacks the restricting group

### `DOC-001` · Fill the data-dictionary governance columns

`DATA_DICTIONARY_AS_IS.csv` has 978 rows; `security_class`, `source_of_truth`,
`audit_policy` and `test_id` are empty because they are business decisions.

> **GIVEN** the 978-row dictionary
> **WHEN** the governance workshop concludes
> **THEN** every field has a security class (public/internal/confidential/restricted) and a named data owner
> **AND** every restricted field either carries `groups=` or has a recorded exception

---

## P2 — Wave 2: the financial spine

### `ARCH-001` · The §7.1 entity mixin
**Blocks FIN-002, INT-001, all migration**

Five §7.1 concepts are absent from all 62 models: `version`, `approval_state`,
`source_system`/`source_record_id`, `correlation_id`. Add once as an
`AbstractModel`, not 5 × 62 times.

> **GIVEN** a model inheriting the mixin
> **THEN** it has `source_system`, `source_record_id`, `version`, `approval_state`, `approved_by`, `approved_at`, `correlation_id`
> **AND** `(source_system, source_record_id)` is unique where both are set
> **AND** `version` increments on write and a stale write is refused
> **AND** a constraint makes `approved_by == create_uid` impossible
> **AND** tests cover the concurrency and self-approval refusals

### `FIN-001` · The posting catalogue
**Depends on DEC-004 · Blocks FIN-002, BI-001**

Blueprint §20.1 item 5. Does not exist.

> **GIVEN** any money event in scope
> **THEN** `docs/architecture/ACCOUNTING_POSTING_RULES.md` records source event → debit/credit accounts → tax treatment → cash/AR/AP/stock/project effect → reversal method
> **AND** a qualified accountant has signed it
> **AND** every entry maps to a test asserting the posting

### `FIN-002` · Derive `amount_received` from the ledger
**Depends on FIN-001, PRJ-002 · The project's keystone item**

`project.project.amount_received` is typed by a human. A commercial dashboard
built on hand-entered receipts will disagree with the accounts, and the first time
it does, the dashboard loses its credibility permanently.

> **GIVEN** a project with `c2p_sale_order_id` set
> **WHEN** `amount_received` is read
> **THEN** it equals the sum of reconciled payments on invoices linked to that order
> **AND** the user can drill from the figure to those payments and their journal entries
> **AND** a hand-entered override is visibly flagged as an override
> **AND** a reconciliation test asserts the figure against the trial balance

### `FIN-003` · A true project margin
**Depends on PRJ-001, FIN-002**

`consultants_margin` subtracts subcontract cost but not labour — there are no
timesheets. It is revenue presented as margin.

> **GIVEN** a project with logged timesheets
> **THEN** margin = recognised revenue − subcontract cost − labour cost
> **AND** the labour component drills to the timesheet entries behind it

### `PRJ-001` · Install standard `hr_timesheet`
**Depends on DEC-005 · Highest value per hour in the backlog**

Standard Odoo Community, integrates with `project` out of the box. Configuration,
not development. Unlocks FIN-003 and all project costing.

> **GIVEN** `hr_timesheet` installed and configured
> **WHEN** a delivery member logs time against a task
> **THEN** it appears in project cost and in the labour component of margin
> **AND** a member cannot read another member's rate

### `INT-001` · Idempotency for webhooks and submissions
**Depends on ARCH-001**

No outbox, no idempotency key, no dead-letter model anywhere. A replayed Stripe
webhook can double-apply a subscription change; a retried e-invoice can
double-submit to a tax authority.

> **GIVEN** a webhook or submission delivered twice with the same external id
> **THEN** the second delivery is a no-op and is logged as a duplicate
> **AND** a malformed payload lands in a dead-letter record, inspectable and replayable
> **AND** a test replays each registered integration's payload and asserts single-effect

### `SEC-005` · Field-level security on commercial data
**~2 hours**

`mumtaz_media_buying` exposes `media_cost`, `commission_amount`, `net_revenue`,
`service_fee`, `gross_rate` with no `groups=`. Any user who can read a media plan
reads the agency's margin.

> **GIVEN** a `media_user` without the manager group
> **WHEN** they read a media plan via UI, `read()`, `read_group` or export
> **THEN** cost, commission and margin are absent from the response
> **AND** a negative test asserts it for each access path, export included

### `FIN-004` · `monthly_price` from `Float` to `Monetary`
**~15 minutes** — the only money-typing violation in 978 fields.

> **GIVEN** `mumtaz.module.bundle` **THEN** `monthly_price` is `Monetary` with an explicit `currency_field`

### `BI-001` · The semantic metric layer
**Depends on FIN-001 · Blocks every executive dashboard**

Without a `MetricDefinition` model, two dashboards will compute "revenue"
differently and nobody will know which is right.

> **GIVEN** a KPI on any dashboard
> **THEN** it resolves to one named `MetricDefinition` stating formula, company scope, currency, period and whether eliminations are applied
> **AND** every tile drills to the records behind it
> **AND** a test asserts the tile value equals its drill-down result

---

## P3 — On decision

| ID | Item | Blocked by |
|---|---|---|
| `SEC-002` | Classify every AI agent action (read/recommend/draft/act-with-approval) | — (start in Wave 4; `mumtaz_ai` touches `account` **today** with no gate) |
| `SEC-003` | Named service identity per AI agent, minimum groups | SEC-002 |
| `SEC-004` | Global AI kill switch, checked before every outbound call | — |
| `ARCH-002` | Invert `portal_routing → cfo_base` layering violation | — |
| `ARCH-003` | Migrate `media.plan` onto `sale.order` + pricelists | DEC-001 (may hold live data) |
| `ARCH-004` | Consolidate the 8 scaffolding modules into `mumtaz_core` + `mumtaz_ui` | DEC-001 |
| `APR-001` | Approval workflow — Automation Rules first, model only if that fails | DEC-006 |
| `L2C-001` | Configure and test quote-to-cash with the §6.1 variants | Wave 2 exit |
| `P2P-001` | 3-way match + budget check via standard Odoo | DEC-005 |
| `MIG-001`/`002` | CRM dataset audit; apply the written-but-unapplied CRM patches | owner go-ahead + backup |
| `UX-001`–`005` | RTL audit, token split, contrast check, report drill-down, CEO-dashboard decision | — |
| `DEC-003` | Agency OS write scope against client production | owner |

---

## The next smallest safe task

Blueprint §21 Step G requires naming one.

**`SEC-000` — close the production exposure.** It has no dependencies, needs no
decision, no design and no code. It is a firewall rule and a password change. It
is the only item in this backlog where every hour of delay carries real risk to
live client data, and every control described across these twelve deliverables is
theatre until it is done.

**The first *development* task**, once that is closed, is `PRJ-002` — install
`c2p_project_tracker` and run its 57 tests. Not because the module is urgent, but
because it converts the repository's largest piece of untested work into either
evidence or a bug list, and it builds the disposable-test-database capability that
every later wave needs.
