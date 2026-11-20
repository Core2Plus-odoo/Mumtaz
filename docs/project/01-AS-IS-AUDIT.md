# Deliverable 1 — Current-system technical and functional audit

Commit audited: `1ea980a`, branch `claude/gifted-turing-jjdsb2`. All counts are
reproducible with the scripts named inline.

---

## 1. Platform determination

**[FACT] This is an Odoo 19 Community project, path (A) of the blueprint §0.** Not a
custom ERP, not merely ERP-connected. Evidence:

- 38 Odoo add-on directories under `addons/`, every one with a parseable
  `__manifest__.py` declaring `version` `19.0.x.y.z`.
- Dependencies resolve to Odoo standard apps: `mail` (15 modules), `base` (11),
  `web` (8), `account` (7), `portal` (4), `website` (4), `crm` (4), `purchase` (3),
  `stock` (2), `sale` (2), `sale_management`, `project`, `contacts`.
- `docs/ARCHITECTURE.md` states the deployment model: *"One isolated Odoo database
  per tenant"*, Odoo proxied at `127.0.0.1:8069` with longpoll on `:8072`.

**[FACT] Community, not Enterprise.** `c2p_project_tracker` was built under an
explicit no-Enterprise constraint (no `web_gantt`, `project_enterprise`,
`web_studio`, `documents`, `sign`) and no manifest anywhere depends on an
Enterprise module.

**[FACT] There is a second, non-Odoo product in this repository.**
`c2p-delivery-system/` is a FastAPI application (44 Python files, 10,934 lines)
plus a single-file operator console. It is the C2P Agency OS — an AI-assisted Odoo
*delivery* pipeline (presales → discovery → requirements → estimate → proposal →
project → functional → developer → documents → config → deploy). It talks to Odoo
over XML-RPC (`delivery_api/odoo.py`) and pushes generated modules to GitHub
(`delivery_api/github.py`). **It is a tool that builds ERPs; it is not the ERP.**
Conflating the two would be the single easiest way to wreck this engagement, so
every deliverable here treats them as two products under one roof.

Three further codebases share the repository: `faizy/` (a separate Odoo Community
instance with its own CI workflow and documented intent to split into its own
repo), `wordpress-sites/` (two WordPress themes), and `apps/` + `platform/` +
`website/` (static marketing sites and a `zaki-server` FastAPI platform API).

---

## 2. Code mass and shape

**[FACT]** Measured by `scripts/audit/inspect_addons.py` (AST + regex, read-only):

| Measure | Value |
|---|---|
| Odoo add-on modules | 38 (37 `mumtaz_*` + `c2p_project_tracker`) |
| Python lines in `addons/` | 21,772 |
| Model classes declared | 80 |
| New concrete models (`models.Model` with `_name`) | 62 |
| Abstract / transient models | 22 |
| Declared fields | 978 |
| XML data/view files | ~200 |
| `ir.model.access` rows | 222 |
| `ir.rule` records | 35 |
| Python test functions in `addons/` | **57** |
| Modules containing any test | **1 of 38** |

### 2.1 Odoo-19 syntax hygiene is clean

**[FACT]** Across all `addons/` XML and Python: **0** uses of the removed `attrs=`
attribute, **0** `<tree>` view tags (all use `<list>`), **0** field-level
`states={...}`. This is genuinely good and unusual — the codebase was written
against the v17+ conventions rather than ported carelessly from v14 patterns.

### 2.2 Money handling is correct

**[FACT]** 34 `fields.Monetary` declarations; a multi-line AST check over the full
call body found **0 without an explicit `currency_field`**. Exactly **one**
`fields.Float` carries a money-shaped name: `mumtaz.module.bundle.monthly_price`
("Monthly Price (USD)") in `addons/mumtaz_tenant_manager`. Blueprint §4.2 forbids
binary floating-point for monetary totals; this is the only violation and it is a
plan-catalogue price, not a posted amount. Low severity, trivial fix.

### 2.3 Dependency graph is acyclic but deep

**[FACT]** No dependency cycles among the 38 own modules (blueprint §5 prohibits
them). Deepest own-dependency chains: `mumtaz_super_toolkit` (9),
`mumtaz_cfo_toolkit` (8), `mumtaz_app_portal` / `mumtaz_org_config` /
`mumtaz_cfo_transactions` (7). A depth of 9 means installing one module drags in
eight others; combined with the absence of install tests (§2.4) this is where
install-order breakage will surface first.

### 2.4 Test coverage is the gravest technical finding

**[FACT]** All 57 test functions live in `addons/c2p_project_tracker/tests/`
(`test_commercials`, `test_dashboard`, `test_health`, `test_hygiene`,
`test_security`, `test_sync`, plus `common.py`). **The other 37 modules — 21k lines
including subscription billing, Stripe integration, e-invoicing and the
multi-tenant control plane — contain zero automated tests.**

**[FACT] And the 57 that exist have never been executed.** They were written in a
prior session; the repository contains no run output, and the install runbook
`addons/c2p_project_tracker/scripts/backup_and_install.md` was never carried out.
Under blueprint §15.3 and §21.2 the honest status of every test in this repository
is **NOT RUN**.

`c2p-delivery-system/delivery_api/tests/test_phase1.py` holds a further 28 test
functions, also with no recorded run.

---

## 3. Security posture

Full matrix in [`../architecture/SECURITY_MATRIX.md`](../architecture/SECURITY_MATRIX.md). Audit-level findings:

### 3.1 Model access control: complete

**[FACT]** All **62 of 62** concrete models have at least one `ir.model.access`
row. (An earlier pass of my own script reported 69/106 coverage; that pass was
wrong — its regex `_name\s*=` also matched `_rec_name`, `brand_name` and
`company_name`, inventing models that do not exist. The corrected script anchors
the match to line start. The clean result stands.)

### 3.2 Row-level access control: 40 of 62 models have none

**[FACT]** Only 22 of 62 concrete models are covered by any `ir.rule`.
Hand-verified for the two worst cases rather than trusted from the parser:

```
$ grep -rn 'ir\.rule' addons/mumtaz_control_plane/   → no matches
$ grep -rln 'ir\.rule' addons/mumtaz_lead_nurture/   → no matches
```

`mumtaz_control_plane` declares 16 models — `mumtaz.subscription`, `mumtaz.plan`,
`mumtaz.subscription.billing.record`, `mumtaz.tenant.feature`,
`mumtaz.usage.metric`, `mumtaz.commercial.operation` and more — with an 11.8 KB
ACL CSV, a `security.xml` defining 5 groups, and **not one record rule**.

**This is not automatically a leak**, and that nuance matters: with one Odoo
database per tenant (`docs/ARCHITECTURE.md` §2), tenant isolation is enforced by
the database boundary, so a tenant-scoped model needs no `ir.rule`. The question
is which of these modules is installed **where**:

- If `mumtaz_control_plane` lives only in a dedicated control-plane database, the
  absence of rules is defensible.
- If it is installed **inside tenant databases**, then every user of a tenant with
  read access to `mumtaz.subscription` can read **all** subscription, plan and
  billing rows present in that database.

**[DECISION DEC-001]** resolves this, and it cannot be resolved from source code.

### 3.3 Of the 35 rules that exist, the domains are sound

**[FACT]** 17 of 35 use `[('company_id', 'in', company_ids)]` — the correct
multi-company form (not `= user.company_id.id`, which breaks when a user has
several allowed companies). One rule still uses the single-company form and one
uses the `'|', ('company_id','=',False)` shared-record form. Nine use
`[(1,'=',1)]`; all nine are hand-checked as deliberate manager/admin escalation
rules bound to a specific group (`mumtaz_core.group_mumtaz_manager`,
`base.group_system`, `account.group_account_manager`,
`mumtaz_control_plane.group_mumtaz_billing_admin`), which is the standard Odoo
pattern and correct.

### 3.4 Field-level security protects credentials but not commercial data

**[FACT]** 23 fields carry `groups=`: 11 with a literal group string and 12 via
the `COMMERCIAL_GROUP` constant in `c2p_project_tracker`. (My first count said 11
— it missed the 12 because a non-literal kwarg returns no AST constant.)

The 11 literal ones are all **credential-holding fields** across
`mumtaz_core.settings`, `mumtaz.einvoice.config`, `mumtaz.tenant` — platform
tokens, provider API keys, ZATCA signing material, FBR and tenant admin
credentials, Stripe customer references. Restricting them to `base.group_system`,
`account.group_account_manager` and the billing-admin groups is correct and
commendable.

The 12 constant-driven ones are `c2p_project_tracker`'s commercials
(`contract_value`, `amount_received`, `subcontract_value`, `consultants_margin`, …).

**[FACT] Everywhere else, no field-level restriction exists.** In particular
`mumtaz_media_buying` exposes `media_cost`, `commission_amount`, `net_revenue`,
`service_fee` and `gross_rate` (65 fields, 11 Monetary) with **no `groups=`**, so
any user who can read a media plan can read the agency's margin on it. Blueprint
§10.1 requires field-level restrictions for cost and margin. This is a real,
cheap-to-fix gap.

**[FACT]** 0 fields are `company_dependent` — consistent with DB-per-tenant.

### 3.5 `sudo()` concentration

**[FACT]** 196 `.sudo()` call sites. Heaviest: `mumtaz_app_portal` (23),
`mumtaz_portal_routing` (23), `mumtaz_control_plane` (21),
`mumtaz_billing_stripe` (16), `c2p_project_tracker` (12), `mumtaz_marketplace`
(12), `mumtaz_api` (9), `mumtaz_core` (9), `mumtaz_vendor_portal` (9). Portal
controllers legitimately need `sudo()` to serve records to portal users, so a high
count is not prima facie wrong — but blueprint §17.1 requires each one be audited
for accidental cross-scope reads, and **none has been**. `c2p_project_tracker` is
the one module where the `sudo()` calls are deliberately designed and documented
(controlled cross-company aggregation returning aggregates only, gated by
`_check_member()`), which is the pattern the other eight should be measured
against.

### 3.6 Operational exposure carried over from prior sessions

**[FACT, prior session]** The production VPS firewall permits direct inbound
access to the Odoo application ports from any address, and at least one
internet-reachable instance can select a live business database that is still
protected only by a default-strength administrator credential. This was reported
in three previous sessions and has not been remediated.

Specifics are deliberately **not** recorded in this repository — the exposure is
live, and the repository's own rule is that secrets never enter git. The ports,
instance and credential state are in the session history and should be handled
directly on the host.

**This is the highest-severity item in the audit.** It is an operations fix, not a
code fix, and it does not depend on any decision below. See `BACKLOG.md` item
`SEC-000`.

---

## 4. Financial-integrity posture

**[FACT] The one module that touches posting does it the standard way.**
`mumtaz_einvoicing` (2,208 lines) extends rather than replaces:

```python
# addons/mumtaz_einvoicing/models/mumtaz_einvoice.py:13-15
"""Extends account.move with e-invoicing fields and submission logic."""
_inherit = 'account.move'
# :433-435
def action_post(self):
    result = super().action_post()
```

`_inherit` on `account.move` with `super().action_post()` is exactly blueprint
§17.1 ("preserve native invoice, stock valuation, payment and ledger
mechanisms"). No module creates `account.move` records to simulate posting, and
no module writes to posted entries.

**[FACT] But there is no posting catalogue.** Blueprint §20.1 item 5 requires a
documented source-event → debit/credit → tax → reversal map. None exists in this
repository. `mumtaz_financial_reports` (375 lines, 4 posting references, one OWL
asset) renders reports with no documented lineage from the figures to the records
behind them, which breaks §11.1's "avoid magic totals".

**[FACT] Two independent CFO stacks exist.** `mumtaz_cfo_base` /
`_ingestion` / `_transactions` / `_toolkit` (969 lines, 11 models) sit alongside
standard `account`, and `mumtaz_zaki` plus `mumtaz_voice` also touch `account`.
Whether the CFO models are a *subledger* (fine), a *staging area for ingestion*
(fine), or a *parallel ledger* (a §4.2 "single authoritative owner" violation)
cannot be determined without reading all four modules against live data. Flagged
as `DEC-004`.

---

## 5. Multi-tenancy

**[FACT]** `docs/ARCHITECTURE.md` §2 documents DB-per-tenant with a central
`zaki-server` registry holding `users.tenant_db` and `odoo_uid`, and states
*"there is no cross-tenant query path"*.

**[FACT]** The code carries three *different* tenancy mechanisms simultaneously:
`mumtaz_tenant_manager` (`mumtaz.tenant` model, 4 models, 909 lines),
`mumtaz_subdomain_routing` + `mumtaz_portal_routing` (host-based routing, 1,093
lines, 27 `sudo()` calls between them), and two `ir.rule` records filtering on
`('tenant_id','in', user.partner_id.parent_id.mapped('id'))`. Blueprint §4.3
demands that tenant, legal company, business unit, branch and project be
*distinct, non-interchangeable* scopes. Three parallel mechanisms is how they stop
being distinct. Needs a single documented answer — `DEC-002`.

---

## 6. Delivery and operations

**[FACT]** 6 GitHub Actions workflows: `ci.yml` (manifest validation),
`test.yml` (flake8 `E9,F63,F7,F82` + a Postgres service), `faizy-ci.yml`
(compileall + manifest/ACL/view cross-checks — notably the **strictest** checks in
the repo, and they run only on `faizy/`), `deploy-staging.yml` (auto on
`develop`), `deploy-production.yml` (manual `workflow_dispatch`, with a pre-deploy
backup and a health check), `backup.yml` (nightly 02:00).

**[FACT] CI runs no Odoo tests.** `test.yml` starts Postgres but the lint job only
runs flake8's error subset; no job installs a module into a database or executes
the 57 tests. So the one tested module's tests cannot regress anything, because
nothing runs them.

**[FACT]** Production deploy is `bash /opt/mumtaz/c2p-delivery-system/deploy/update.sh`
on the VPS, pulling `main`. `CLAUDE.md` documents two hard-won gotchas:
`web/index.html` must be a **symlink** to the console (a copy goes stale silently)
and the service env file is `delivery_api/.env`, not the repo root.

**[FACT, prior session]** Production's add-on layout is broken: two identical
37-module checkouts, a third containing `c2p_appointment`, `c2p_master_agent`
installed with **no source in any checkout**, and `/opt/mumtaz/addons` not on the
`addons_path` at all. Module shadowing was measured. Until this is resolved,
nothing in `addons/` can be assumed to be what production runs — which is why
`DEC-001` gates Waves 1–2.

---

## 7. Functional assessment

See [`02-CAPABILITY-MATRIX.md`](02-CAPABILITY-MATRIX.md) for the full
Existing / Partial / Missing / Unknown grid against blueprint §5.

The short version: **the platform layer is heavily built and the transactional
spine is almost entirely absent.** Of 21,772 lines, the overwhelming majority
implement tenancy, subscriptions, branding, routing, portals, lead generation and
AI/voice assistants. Quote-to-cash and procure-to-pay — the two flows blueprint
§19 Wave 2 says must be proven end-to-end before anything else — are represented
only by `depends` entries on `sale`, `purchase`, `stock` and `account`. No module
implements or tests an order→delivery→invoice→payment→GL chain.

This is the central finding of the audit. The repository is a **SaaS control
plane and growth engine wrapped around an un-proven ERP core**.

---

## 8. Audit verdict

| Dimension | Verdict |
|---|---|
| Platform determination | Clear and unambiguous — Odoo 19 Community |
| Odoo framework discipline | **Strong.** Clean v19 syntax, `_inherit` + `super()`, no core forks, no SQL-bypass, acyclic deps |
| Money correctness | **Strong.** 34/34 Monetary with currency_field; 1 trivial Float to fix |
| Model-level security | **Complete.** 62/62 ACL |
| Row-level security | **Unverifiable from code** — depends on DEC-001; 40/62 models have no rule |
| Field-level security | **Weak.** Credentials protected; cost/margin/commission not |
| Financial integrity | **No evidence either way.** Correct patterns, zero posting catalogue, two CFO stacks of unclear role |
| Transactional spine (L2C / P2P) | **Absent** |
| Test evidence | **None.** 57 tests exist, 0 executed, 37 of 38 modules untested, CI runs no Odoo tests |
| Documentation | **Unusually good** for narrative/history; **absent** for the blueprint's required artefacts |
| Production hygiene | **Poor.** Open ERP ports, default-strength admin credential, duplicate checkouts, orphan installed module |

**The engineering instincts in this codebase are better than its engineering
evidence.** The patterns are right; almost nothing has been proven to work. That
is a far better starting position than the reverse, and it sets the priority:
*prove what exists before building what does not.*
