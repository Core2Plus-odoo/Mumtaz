# Mumtaz current-system audit — reconciliation

Written 21 Nov 2026. This is a pointer and a delta, not a second audit.

## Conclusion

1. The current state is already documented in two places. They stay authoritative; this file does not repeat them.
2. This session added one thing those audits could not: it **ran** the control-plane code on a real Odoo 19 with PostgreSQL 16. The provisioner works, but six defects around it meant the platform could report a tenant as live when nothing existed, or create a database when told not to.
3. Slice 1 on this branch fixes the defects on the path "register organization → choose Mumtaz ERP → entitlement → staging tenant → open workspace". The server itself is still unseen: every statement about it remains REPORTED.

## Status legend

| Tag | Meaning |
|---|---|
| **VERIFIED** | Read in code at the cited path, or run on the local Odoo 19 rig on 21 Nov 2026 |
| **REPORTED** | From a repository document or an earlier session note. Includes everything about the live server |
| **PROPOSED** | Recommended, not built or not decided |
| **UNKNOWN** | Needs server evidence or an owner decision |

## 1. Authoritative documents

| Subject | Document | Tag for its content |
|---|---|---|
| Infrastructure, security, databases, deployment, backups, risks, remediation | [`docs/infrastructure-audit/`](../infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md) (16 files, read-only audit of 21 Nov 2026) | Code findings VERIFIED; server findings REPORTED |
| ERP capability by business domain | [`docs/erp/00-AUDIT.md`](../erp/00-AUDIT.md) and [`01-CAPABILITY_MATRIX.md`](../erp/01-CAPABILITY_MATRIX.md) | VERIFIED in code; live environments REPORTED |
| Repository layout | [`REPO_MAP.md`](../../REPO_MAP.md), [`sites/README.md`](../../sites/README.md), `registry.yaml` | VERIFIED |
| What changed on `main` after the infrastructure audit | [`15_DECISIONS_AND_APPROVALS.md`](../infrastructure-audit/15_DECISIONS_AND_APPROVALS.md), table "Changes on main after the audit" | VERIFIED |

## 2. What this session added on 21 Nov 2026

All rows VERIFIED on the local rig (Odoo 19.0 Community from source, PostgreSQL 16) unless a different tag is given. "Before" is `main` at `ff1c797`.

| # | Finding (before) | Fixed in slice 1? | Still open |
|---|---|---|---|
| a | **The real provisioner works.** With `MUMTAZ_REAL_PROVISIONING=1` it created a separate database, installed the bundle, and the tenant administrator could sign in. **But** it called a database-manager function that refuses to run when the server hides its database list — the setting a multi-tenant server should use, and the one REPORTED for the main Odoo unit and the client instance. It also treated a failed database initialisation as success, because the Odoo function it called logs its own errors and returns normally | **Yes.** Provisioning no longer depends on the database manager being exposed; the end-to-end check runs with the database list hidden. After creating the database the provisioner now checks that Odoo initialised it, that every requested module is installed and that the administrator login is set | Never run on the production server (decision P-03) |
| b | **The "Dry Run" checkbox was never read.** The provision wizard chose its provisioner from the server setting alone. On a server allowed to create databases, a ticked "Dry Run" still created one. On a server not allowed to, the simulated run **marked the tenant active** although nothing existed. The scheduled worker did the same | **Yes.** The checkbox decides: ticked never creates anything; unticked creates a real database or refuses. A simulated success leaves the tenant in draft. One method is the only place a tenant becomes active after provisioning | The separate "Mark Active" button still lets an operator activate a tenant by hand; left alone because manually built tenants may rely on it (UNKNOWN) |
| c | **"Platform Manager" could start provisioning.** The group's description says it cannot provision, but its members may edit tenant records, and the queue method had no check of its own, so it was callable over RPC | **Yes.** Queueing and the wizard now require Platform Administrator (or system administrator). Tested | — |
| d | **Customer databases received control-plane modules.** A tenant provisioned with the `starter` bundle ended up with `mumtaz_tenant_manager` installed — the tenant registry model and the five-row bundle price list inside the customer's database — pulled in by `mumtaz_sme_profile`. Four of the five existing bundles have this problem. Three bundles also name an Enterprise-only module (`account_accountant`) that the installer skips without saying so | **Partly.** A new install profile `mumtaz_erp` contains only standard Odoo 19 Community apps plus `mumtaz_financial_reports`. A test fails if its dependency closure ever reaches a control-plane module, or if it names a module that does not exist; the end-to-end check confirms the tenant database has no control-plane tables | The five older bundles are unchanged (their data is protected from upgrade and may be in use). Detail: [`MUMTAZ_MODULE_REGISTRY_REVIEW.md`](MUMTAZ_MODULE_REGISTRY_REVIEW.md) |
| e | **Two tenancy models, not connected.** `mumtaz.tenant` is database-per-tenant. `mumtaz.org` (in `mumtaz_org_config`) is company-per-organization in one shared database, and its public signup creates a company there. Nothing linked a registration to a tenant record or to provisioning | **For the ERP journey, yes.** A registration request in the control plane now leads, through a person's approval, to an organization contact, a staging tenant, a trial subscription and provisioning. It uses `mumtaz.tenant` only | `mumtaz_org_config` and its public signup are untouched. Choosing database-per-tenant as the only model, and migrating or retiring `mumtaz.org`, is decision P-01 |
| f | **No plans; entitlement fails open.** Eight features were seeded but no plan, so no subscription could grant anything. The entitlement resolver answers "allowed" when asked about a feature code that is not registered | **Partly.** A product catalogue and one plan ("Mumtaz ERP — staging trial") are seeded, with ZAKI and Marketplace switched off explicitly rather than left undefined. Provisioning is refused when the resolver does not grant the product's access feature | The resolver's fail-open behaviour for unknown codes is unchanged, because four other modules call it (`mumtaz_api_gateway`, `mumtaz_cfo_base`, `mumtaz_marketplace`, `mumtaz_voice`). Paid plans and prices are undecided (decision D-11) |
| g | Three read-only evaluations were made of areas with several competing implementations | No code change | See section 3 |

The first functional milestone was then proven end to end with nothing mocked: `scripts/tenant_journey_ci.sh` registers an organization, approves it, checks the entitlement, provisions a real `stg_` database, starts Odoo on it and signs in over HTTP through a one-time link. The same script proves that a server not allowed to create databases ends the journey with no database and no active tenant. It runs in CI in the platform install workflow.

## 3. The three evaluations

**ZAKI and AI** — [`MUMTAZ_AI_ARCHITECTURE.md`](MUMTAZ_AI_ARCHITECTURE.md). None of the three applications behind `zaki.mumtaz.digital` is safe to expose: two depend on a back end that was deleted, and the third has no authentication and one shared administrator account for every tenant. The only code with real governance is the Jawhar AI module. The recommended single architecture runs ZAKI inside each tenant's Odoo, with tools executing as the signed-in user. VERIFIED in code; which implementation is live is UNKNOWN.

**Website and brand** — [`MUMTAZ_WEBSITE_IMPLEMENTATION.md`](MUMTAZ_WEBSITE_IMPLEMENTATION.md) and [`MUMTAZ_DESIGN_SYSTEM.md`](MUMTAZ_DESIGN_SYSTEM.md). `mumtaz_website_builder` is the only native Odoo Website Builder implementation and is the canonical candidate. It is not publishable yet: the hero shows an illustrated mock rather than the product, it now carries prices and claims that are undecided, and it has no Arabic or right-to-left work. Where it should run is not decided (P-10). The repository holds about ten competing colour and font sources; most are gold-first, which the approved navy/emerald/lime direction replaces. VERIFIED in code; what the live site serves is UNKNOWN.

**Module governance** — [`MUMTAZ_MODULE_REGISTRY_REVIEW.md`](MUMTAZ_MODULE_REGISTRY_REVIEW.md). The six-layer rule holds for declared dependencies, with one known exception. It cannot see ownership, products, install profiles or undeclared dependencies, and those are where the real problems are: control-plane modules reaching tenant databases, customer names in reusable code, and bundles that do not match any real product. VERIFIED in code; which modules are installed in which database is UNKNOWN.

## 4. Findings from the earlier audits whose status changed

| Finding | Status now | Tag |
|---|---|---|
| ODOO-35 — a bundle names an Enterprise module that is skipped silently | Still true for the older bundles. The new provisioner check fails the run when a requested module is not installed, so the gap is no longer silent | VERIFIED |
| Audit 06 §2.2 — "repair before any further tenant is provisioned; pick one tenancy model" | Provisioning path repaired and tested for the ERP profile; the tenancy decision is still open (P-01) | VERIFIED / PROPOSED |
| ODOO-01 — shared sign-on secret | Unchanged. The new journey does not use it: the administrator signs in through Odoo's own one-time invitation link, and the ERP profile does not install `mumtaz_sso` | VERIFIED |
| ODOO-06 — Faizy identity documents readable by any customer | Fixed in code on `main` (PR #182) and on the Faizy production branch (PR #184). Whether the server was upgraded is UNKNOWN | VERIFIED code |

## 5. What is still unknown

Everything on the server: which database is the control plane, which modules each database has installed, whether any tenant was ever provisioned through `mumtaz.tenant`, which website and which ZAKI are served, and whether any backup exists. The read-only verification pack in [`13_REMEDIATION_BACKLOG.md`](../infrastructure-audit/13_REMEDIATION_BACKLOG.md) answers these. See [`MUMTAZ_DEPLOYMENT_REGISTRY.md`](MUMTAZ_DEPLOYMENT_REGISTRY.md) section 7.
