# Mumtaz Master Architecture

State at commit `ff1c797` plus the first platform slice on branch `ccr-620c243b-p9qlq1`, 21 Nov 2026.

## 1. Conclusion

- **There is already a control plane. It is two Odoo modules, not a separate application.** `mumtaz_tenant_manager` (tenant registry, install profiles, provisioner) and `mumtaz_control_plane` (plans, features, subscriptions, entitlement resolver), with `mumtaz_billing_stripe` on top. The target architecture completes these. It does not start a second one.
- **The tenancy model is one PostgreSQL database per customer.** That is ADR-002 and it is what the provisioner does. A second model (one company per organization inside a shared database, `mumtaz_org_config`) contradicts it and is proposed for retirement (P-01).
- **Until this slice, registration and provisioning were not connected, and a dry run marked a tenant "active" without creating anything.** Slice 1 connects them and makes "active" mean "a real database exists and was verified". The whole journey now runs for real on a local Odoo 19 rig.
- **Everything about the live server in this document is REPORTED.** Nobody in this session had server access. Which database is the control plane in production, and whether any tenant was ever provisioned through it, is UNKNOWN (P-02).
- **Three things are not safe to build on yet:** the shared-secret single sign-on (`mumtaz_sso`, audit ODOO-01), every existing ZAKI implementation, and any install profile that pulls control-plane modules into a customer database.

## 2. Status legend

| Tag | Meaning |
|---|---|
| **VERIFIED** | Read in code, or run on the local Odoo 19 + PostgreSQL 16 rig on 21 Nov 2026 |
| **REPORTED** | From a repository document or an earlier session note; not re-checked. This covers **everything about the live server** |
| **PROPOSED** | Design. Not built |
| **UNKNOWN** | Needs server evidence or an owner answer |

Decision IDs: `P-xx` are the platform decisions appended to [`docs/erp/project/DECISION_REGISTER.md`](../erp/project/DECISION_REGISTER.md); `ADR-xxx` and `D-xx` are the existing entries there; "audit D-xx", `F-xx`, `ODOO-xx` and `APP-xx` are in [`docs/infrastructure-audit/`](../infrastructure-audit/).

Related documents, not repeated here:
[`MUMTAZ_PRODUCT_CATALOGUE.md`](MUMTAZ_PRODUCT_CATALOGUE.md) ·
[`MUMTAZ_PRODUCT_INTEGRATION_MAP.md`](MUMTAZ_PRODUCT_INTEGRATION_MAP.md) ·
[`MUMTAZ_SAAS_CONTROL_PLANE.md`](MUMTAZ_SAAS_CONTROL_PLANE.md) ·
[`MUMTAZ_MODULE_REGISTRY_REVIEW.md`](MUMTAZ_MODULE_REGISTRY_REVIEW.md) ·
[`MUMTAZ_AI_ARCHITECTURE.md`](MUMTAZ_AI_ARCHITECTURE.md) ·
[`MUMTAZ_WEBSITE_IMPLEMENTATION.md`](MUMTAZ_WEBSITE_IMPLEMENTATION.md) ·
[`MUMTAZ_DESIGN_SYSTEM.md`](MUMTAZ_DESIGN_SYSTEM.md) ·
[`sites/README.md`](../../sites/README.md) ·
[`REPO_MAP.md`](../../REPO_MAP.md).

## 3. The four categories

Every system is placed in exactly one category. The category decides who may change it and how.

### 3.1 Shared Platform

Built once, used by every product.

| System | What it is today | Where | Status |
|---|---|---|---|
| Control plane | Tenant registry, install profiles, provisioner, product catalogue, registration requests | `addons/mumtaz_tenant_manager`, `addons/mumtaz_control_plane` | VERIFIED in code; tested on the local rig. Production database UNKNOWN (P-02) |
| Entitlements | Plans, features, subscriptions, per-tenant overrides, one resolver (`mumtaz.feature.access.service`) | `addons/mumtaz_control_plane` | VERIFIED. The resolver fails open for an unknown feature code or an unmapped tenant |
| Billing | Stripe client, webhook, card page, daily charge job | `addons/mumtaz_billing_stripe` | VERIFIED exists; 0 tests; not connected to the registration journey |
| Identity | Odoo sessions, one per database. `mumtaz_sso` bridges with one secret shared by all tenants | Odoo core; `addons/mumtaz_sso` | VERIFIED. SSO flaw is audit ODOO-01; module is in no install profile. Target is P-05 |
| AI layer | No shared layer. The only governed implementation is Jawhar's | `addons/mumtaz_jewellery_ai` (reference) | VERIFIED. Shared layer PROPOSED in `MUMTAZ_AI_ARCHITECTURE.md` |
| Design system | Several competing palettes; approved direction is navy / emerald / lime | `website/jewel/site/jawhar.css` (closest), `docs/design/brand-tokens-v3/`, `addons/mumtaz_theme` | VERIFIED sources; single token set PROPOSED (P-14) |
| Module registry and CI | Layer classification, generated `registry.yaml`, install CI, `sudo()` check, tenant-journey check | `registry/`, `scripts/module_registry.py`, `scripts/platform_ci.sh`, `scripts/tenant_journey_ci.sh` | VERIFIED. Ownership and profile checks PROPOSED (P-16) |

### 3.2 Commercial Products

Things an outside organization can, or will be able to, subscribe to. Detail and evidence per product: [`MUMTAZ_PRODUCT_CATALOGUE.md`](MUMTAZ_PRODUCT_CATALOGUE.md).

| Product | Domain | Delivery | Catalogue status | Status of this row |
|---|---|---|---|---|
| Mumtaz ERP | erp.mumtaz.digital | Own Odoo database per customer | Pilot | VERIFIED (seed data and local journey) |
| Jawhar (jewellery edition) | jewel.mumtaz.digital | Own Odoo database per customer | Pilot | VERIFIED code and tests; instance REPORTED staging |
| Mumtaz Pharma | pharma.mumtaz.digital | Own Odoo database per customer | Planned | REPORTED (code is on `pharma-*` branches, not on `main`) |
| ZAKI | zaki.mumtaz.digital | Inside another product | Planned | VERIFIED: no implementation is safe to expose |
| Marketplace | marketplace.mumtaz.digital | Shared service | Planned | VERIFIED module exists; topology undecided (P-12) |
| Delivery OS | delivery.mumtaz.digital | Shared service (FastAPI + SQLite) | Planned | VERIFIED code; REPORTED in internal production use; not subscribable (P-13) |

### 3.3 Customer Deployments

Running systems that belong to one customer. They are **not products** and are **not in the control-plane catalogue**.

| Deployment | What it is | Rule |
|---|---|---|
| C2P internal ERP — database `Mumtaz_C2P`, core2plus.com | The group's own CRM and ERP. An **internal customer** of the platform | REPORTED production. Its `c2p_*` modules are customer code, not reusable code. 25 CRM rules live only in the database |
| IG2 — database `Mumtaz_IG2`, ig2.mumtaz.digital | An **external client's** accounting system | REPORTED production, no staging. **No automatic change.** Nothing is applied without compatibility testing and the client's approval. Its code is on a feature branch, not `main` |
| Faizy — database `faizy_prod`, myfaizy.com | An **independent venture** on its own branch and its own database role | REPORTED production. It is **not forced into the ERP architecture**; it only shares the server and, for now, the repository (D-12) |

`Mumtaz_C2P` and `Mumtaz_IG2` are never merged. A demo or pilot tenant of a product (for example `jewel_demo`, `mumtaz_pharma`) is an environment of that product, not a customer deployment.

### 3.4 Supporting Websites and Operations

| System | What it is | Status |
|---|---|---|
| mumtaz.digital | Corporate site. Canonical implementation is `addons/mumtaz_website_builder` (native Odoo 19 Website Builder); not yet published. Three older static copies exist | VERIFIED code; what is live is UNKNOWN (P-10, D-09) |
| WordPress sites (odditytrend.com, youngcraze.com) | Unrelated content sites | REPORTED; hosting next to client ledgers is audit D-12 |
| Operations scripts | `ops/deployment/`, `scripts/`, `deploy/`, GitHub workflows | VERIFIED in the repository; which of them deploy anything real is UNKNOWN |
| `platform/` | A stalled rebuild (FastAPI ZAKI backend, marketing page, a control panel whose source is absent) | VERIFIED. Not continued |
| `sites/app.mumtaz.digital/portal` | Static customer portal whose backend (`zaki-server`) was deleted in PR #124 | VERIFIED. Not continued |

## 4. Current state

### 4.1 What exists in code (VERIFIED)

```
                          addons/  (58 Odoo 19 Community modules + 2 Faizy)
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │ CONTROL DATABASE profile                  CUSTOMER DATABASE profiles         │
 │ ┌──────────────────────────────┐          ┌──────────────────────────────┐   │
 │ │ mumtaz_tenant_manager        │ creates  │ mumtaz_erp  (slice 1)        │   │
 │ │   mumtaz.tenant              │────────► │   base mail contacts crm     │   │
 │ │   mumtaz.module.bundle       │ one DB   │   sale_management purchase   │   │
 │ │   Dry-run / Real provisioner │ each     │   stock account              │   │
 │ │ mumtaz_control_plane         │          │   mumtaz_financial_reports   │   │
 │ │   mumtaz.product   (slice 1) │          ├──────────────────────────────┤   │
 │ │   mumtaz.signup.request  "   │          │ Jawhar: 13 mumtaz_jewellery_*│   │
 │ │   mumtaz.plan / .feature     │          │   (no install profile yet)   │   │
 │ │   mumtaz.subscription        │          ├──────────────────────────────┤   │
 │ │   feature access service     │          │ 5 older bundles: 4 of them   │   │
 │ │ mumtaz_billing_stripe        │          │ pull the tenant registry into│   │
 │ │ mumtaz_subdomain_routing     │          │ the customer database        │   │
 │ └──────────────────────────────┘          └──────────────────────────────┘   │
 │ Not in any profile: mumtaz_sso (flawed), mumtaz_org_config (other tenancy    │
 │ model), four portal modules, eight AI/CFO modules, c2p_* (customer code)     │
 └──────────────────────────────────────────────────────────────────────────────┘
 Outside Odoo:  c2p-delivery-system/ (FastAPI + SQLite)   apps/jawhar-web (React)
                sites/* (static sites, node ZAKI app)      platform/ (stalled rebuild)
```

Facts behind the diagram:

| Fact | Evidence | Status |
|---|---|---|
| The real provisioner creates an isolated database, installs a profile and sets up the administrator | Run on the local rig with the old `starter` bundle and with `mumtaz_erp` | VERIFIED |
| With the old `starter` bundle the customer database received `mumtaz_tenant_manager` and the five bundle price rows | `mumtaz_sme_profile` depends on it; observed in the provisioned database | VERIFIED |
| No link existed between an organization's registration and a tenant record | `grep` for `mumtaz.tenant` in `mumtaz_org_config`, `mumtaz_organization`, `mumtaz_onboarding` returned nothing | VERIFIED |
| Before slice 1 a dry run set the tenant to `active`; and on a server with real provisioning enabled, the wizard's ticked "Dry Run" box still created a database | `wizards/provision_wizard.py` at `ff1c797` never read `dry_run` | VERIFIED |
| No `mumtaz.plan` record was seeded, and no bundle was a general ERP | `data/feature_baseline.xml`, `data/mumtaz_bundle_data.xml` at `ff1c797` | VERIFIED |
| Three bundles list `account_accountant`, which is not in Odoo 19 Community; it is skipped silently | `MUMTAZ_MODULE_REGISTRY_REVIEW.md` §7.1, §7.4 | VERIFIED |
| The layer rule holds: one known upward dependency | `python3 scripts/module_registry.py --check` | VERIFIED |

### 4.2 What is reported about the server (REPORTED — not re-checked)

```
 One VPS, Ubuntu 24.04, nginx in front, one PostgreSQL, mostly one shared database role
 ┌───────────────┬──────────────────────────────┬─────────────────────────────────┐
 │ Service       │ Database                     │ Category                        │
 ├───────────────┼──────────────────────────────┼─────────────────────────────────┤
 │ odoo, odoo4   │ Mumtaz_C2P                   │ Customer deployment (internal)  │
 │ odoo2         │ Mumtaz_ERP                   │ Product: Mumtaz ERP (flagship)  │
 │ odoo3         │ Mumtaz_IG2                   │ Customer deployment (client)    │
 │ faizy-odoo    │ faizy_prod (own role)        │ Customer deployment (venture)   │
 │ odoo-pharma   │ mumtaz_pharma                │ Product environment (staging)   │
 │ Jewel (Docker)│ jewel_demo                   │ Product environment (staging)   │
 │ delivery API  │ SQLite files                 │ Product: Delivery OS (internal) │
 └───────────────┴──────────────────────────────┴─────────────────────────────────┘
 Production Odoo checkouts run a feature branch, not main.
```

Source: [`docs/infrastructure-audit/06_ODOO_INSTANCES_AUDIT.md`](../infrastructure-audit/06_ODOO_INSTANCES_AUDIT.md) and [`sites/`](../../sites/). The open critical findings there (exposed ports and plain HTTP for IG2, F-01; no verified backup, F-02; shared sign-on secret, F-23) are unchanged by this work.

UNKNOWN, and needed before anything is enabled in production:

- Which database holds `mumtaz.tenant` rows, and how many (P-02).
- What is installed in each database (`ir_module_module`). Every merge, retirement or rename of a module is blocked on this.
- Whether the Odoo services run with the database manager hidden (`list_db = False`). A code comment in `mumtaz_sso` implies they do. The pre-slice provisioner could not have worked on such a server; the slice-1 provisioner does (VERIFIED locally with `--no-database-list`).
- Worker time limits on the instance that would run provisioning. A general ERP database took about two minutes to build on the local rig.

## 5. Target architecture (PROPOSED)

```
        mumtaz.digital (Odoo Website Builder, own database)        ── P-10
              │ registration form (closed by default)   │ leads → CRM
              ▼
 ┌─────────────────────── CONTROL PLANE (one Odoo database) ────── P-02 ─────────┐
 │ organizations (res.partner, P-04) · product catalogue · plans · subscriptions │
 │ entitlements (one resolver, fail closed) · billing (Stripe) · tenant registry │
 │ install profiles · provisioning queue + worker · white-label brand records    │
 └───────┬───────────────────────────┬───────────────────────────┬───────────────┘
         │ writes ONLY at            │ signed entitlement +      │ usage totals
         │ provisioning              │ brand document (pull)     │ (push)
         ▼                           ▼                           ▲
 ┌───────────────┐   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
 │ ERP tenant A  │   │ ERP tenant B  │   │ Jawhar tenant │   │ Pharma tenant │
 │ own database  │   │ own database  │   │ own database  │   │ own database  │
 │ own DB role   │   │ (P-17)        │   │ + edition     │   │ + edition     │
 │ tenant agent ─┼───┼─ tenant agent ┼───┼─ tenant agent ┼───┼─ tenant agent │
 │ ZAKI embedded │   │               │   │ ZAKI tools    │   │               │
 └───────────────┘   └───────────────┘   └───────────────┘   └───────────────┘
   Shared services, each with its own store:  Marketplace (P-12) · Delivery OS (P-13)
   Never touched by the control plane:  Mumtaz_C2P · Mumtaz_IG2 · faizy_prod
```

| Element | Design | Built? |
|---|---|---|
| One control plane | The Odoo modules `mumtaz_tenant_manager` + `mumtaz_control_plane` + `mumtaz_billing_stripe`, in one control database | Core VERIFIED; billing link PROPOSED |
| Database per tenant | One PostgreSQL database per customer per product environment. Multi-company inside a tenant only for one owner's legal entities (ADR-002, ADR-003) | VERIFIED for creation; per-tenant database role PROPOSED (P-17) |
| Control plane never reads tenant business data | It writes to a tenant database only at provisioning (admin user, company name, base address). After that the tenant calls out; the control plane does not call in | Provisioning part VERIFIED; rule for later stages PROPOSED |
| Tenant agent | A small tenant-side module holding the tenant code and a per-tenant key. It pulls a signed entitlement and brand document, gates features locally, and pushes usage totals. It depends on neither control-plane module | PROPOSED. Not built. It is the prerequisite for selling Jawhar, ZAKI metering and white-label through the control plane |
| No second control plane | `platform/` (stalled rebuild) and `sites/app.mumtaz.digital/portal` (backend deleted) are kept as reference only, then retired | PROPOSED |
| No unnecessary microservices | New platform logic goes into Odoo modules. Separate services are justified only where they exist and work | PROPOSED |
| Delivery OS | Stays FastAPI + SQLite until evaluated as a subscribable product (P-13). Its Odoo bridge stays XML-RPC with per-connection credentials | VERIFIED as-is |
| Identity | Odoo is the identity authority per database. First sign-in uses Odoo's own one-time invitation link. Cross-product sign-on is redesigned, not patched (P-05) | Invitation link VERIFIED; SSO PROPOSED |
| AI | One shared, permission-aware layer; tools run as the signed-in user; no admin credential and no free SQL for agents | PROPOSED — `MUMTAZ_AI_ARCHITECTURE.md` |
| Website | Native Odoo Website Builder in its own database; holds no tenant data | Module VERIFIED; hosting PROPOSED (P-10) |

## 6. Module ownership

Owner groups are PROPOSED; the module-to-group assignment is from [`MUMTAZ_MODULE_REGISTRY_REVIEW.md`](MUMTAZ_MODULE_REGISTRY_REVIEW.md) §4, where each module's evidence, tests and disposition are listed. 60 modules in total.

| Owner group | Category | Modules | Count |
|---|---|---|---|
| platform-core | Shared Platform | `mumtaz_core`, `mumtaz_base`, `mumtaz_branding`, `mumtaz_theme` | 4 |
| platform-saas | Shared Platform | `mumtaz_tenant_manager`, `mumtaz_control_plane`, `mumtaz_billing_stripe`, `mumtaz_api_gateway`, `mumtaz_sso`, `mumtaz_subdomain_routing`, `mumtaz_portal_routing`, `mumtaz_app_portal`, `mumtaz_org_config`, `mumtaz_sme_profile`, `mumtaz_onboarding`, `mumtaz_portal` | 12 |
| erp-generic | Product: Mumtaz ERP | `mumtaz_financial_reports`, `mumtaz_einvoicing`, `mumtaz_crm_starter`, `mumtaz_customer_portal`, `mumtaz_vendor_portal`, `mumtaz_media_buying` | 6 |
| jawhar | Product: Jawhar | `mumtaz_jewellery` and its 14 companion modules (`_vip`, `_owner`, `_sale`, `_crm`, `_ai`, `_kiosk`, `_api`, `_outreach`, `_aml`, `_stores`, `_channels`, `_client`, `_website`, `_demo`) | 15 |
| zaki-ai | Product: ZAKI | `mumtaz_zaki`, `mumtaz_ai`, `mumtaz_voice`, `mumtaz_cfo_base`, `mumtaz_cfo_ingestion`, `mumtaz_cfo_transactions`, `mumtaz_cfo_toolkit`, `mumtaz_super_toolkit` | 8 |
| marketplace | Product: Marketplace | `mumtaz_marketplace`, `mumtaz_organization` | 2 |
| website | Supporting: mumtaz.digital | `mumtaz_website_builder`, `mumtaz_website`, `mumtaz_api` | 3 |
| c2p-customer | Customer deployment: C2P | `c2p_project_tracker`, `c2p_command_center`, `c2p_proposal`, `c2p_appointment`, `c2p_master_agent` | 5 |
| ig2-customer | Customer deployment: IG2 | `mumtaz_ceo_dashboard` as shipped (client branding in code) | 1 |
| internal-tooling | Operations | `mumtaz_lead_scraper`, `mumtaz_lead_nurture` | 2 |
| faizy | Customer deployment: Faizy | `faizy_core`, `faizy_website` | 2 |

No module on `main` belongs to Pharma (its code is on `pharma-*` branches, REPORTED) or to Delivery OS (not Odoo).

Rules that follow from ownership (PROPOSED, to be enforced by the registry — P-16):

1. A customer database may contain only erp-generic modules, one product's edition modules, and later the tenant agent. Never a platform-saas module.
2. Nothing depends on a customer owner, on internal-tooling, on website or on faizy.
3. A module that names a client, a client database or client staff is customer code and stays out of every reusable profile (P-15).
4. New reusable modules use the `mumtaz_` prefix. An installed module is never renamed in place.

## 7. What slice 1 built (VERIFIED)

Branch `ccr-620c243b-p9qlq1`. Design detail is in [`MUMTAZ_SAAS_CONTROL_PLANE.md`](MUMTAZ_SAAS_CONTROL_PLANE.md).

| Piece | Where | What it guarantees |
|---|---|---|
| Product catalogue | `mumtaz.product` in `addons/mumtaz_control_plane/models/product.py`; seed in `data/product_catalogue.xml` | Each product has a status and the evidence for it. A Planned product cannot be opened to registration |
| Registration request | `mumtaz.signup.request` in `models/signup_request.py` | One record carries the journey: new → approved → provisioning → ready, or failed / rejected |
| Public intake | `POST /mumtaz/cp/signup` in `controllers/signup.py` | Closed unless a system parameter opens it. It can only create a pending request; hourly cap, duplicate suppression, honeypot |
| Approval | `action_approve` | A person's decision. Creates the organization (`res.partner`), a staging tenant record and a trial subscription. No database yet |
| Entitlement gate | `action_provision` → `mumtaz.feature.access.service` | Provisioning is refused unless the subscription grants the product's access feature today |
| Honest provisioning | `addons/mumtaz_tenant_manager/services/provisioning.py`, `models/tenant_provisioning.py` | A dry run is marked simulated and leaves the tenant in draft. Only a real run that passed verification sets `active`. A failed run that left a database behind is flagged and never dropped automatically |
| Works with the database manager hidden | same file | Database creation no longer depends on `list_db` |
| Who may provision | `_check_can_provision`, `_check_can_decide` | Platform administrators only, checked in the methods, not only in the access file |
| First sign-in | `_issue_access_link` | Odoo's own time-limited invitation link, void after first sign-in. No password stored on the control record, no shared SSO secret |
| Staging marker | `environment` field and `stg_` database prefix | Staging databases are identifiable by name to backup and clean-up tooling |
| ERP install profile | `bundle_mumtaz_erp` in `data/mumtaz_bundle_data.xml` | Standard Community apps plus `mumtaz_financial_reports`; no control-plane module, no `mumtaz_sso` |
| Tests | `addons/mumtaz_tenant_manager/tests/`, `addons/mumtaz_control_plane/tests/` | 30 tests, 0 failed, on a fresh Odoo 19 database on the local rig |
| End-to-end check | `scripts/tenant_journey_ci.sh` (+ `scripts/tenant_journey/`), added to `.github/workflows/platform-odoo-install.yml` | Creates a real tenant database, signs in over HTTP through the one-time link, checks isolation in PostgreSQL, and proves the dry path creates nothing. Passed on the local rig; result of the first GitHub run is UNKNOWN at the time of writing |

Not built in slice 1, and not to be read into it: e-mail delivery of the link, payment, a customer-facing registration page, the tenant agent, localisation by country, production enablement (P-03).

## 8. Architecture rules

1. One control plane. Complete the existing modules; do not start another.
2. One database per tenant. No tenant shares a database with another tenant or with the control plane.
3. The control plane writes to a tenant only at provisioning and never reads its business data.
4. A status is set from evidence. "Active", "Available" and "Ready" mean something was created and checked, not that a screen looks right.
5. Nothing destructive is automatic. No database is dropped, renamed or merged by code.
6. Customer deployments are outside the platform's change path. C2P is an internal customer; IG2 changes need the client's approval; Faizy is independent.
7. Standard Odoo first, then configuration, then a module that inherits. Customer code never goes into a reusable profile.
8. Agents get scoped tools as the signed-in user. No administrator credential, no free SQL, human approval for anything consequential.
9. Every platform change ships with tests, passes `module_registry.py --check`, `check_sudo.py`, `flake8`, `platform_ci.sh` and `tenant_journey_ci.sh`, and goes through a feature branch.
10. Production is changed only with a verified backup, a rollback written down, and a named approval.

## 9. Top structural risks

| # | Risk | Status | Where it is handled |
|---|---|---|---|
| 1 | No verified backup of any database; a provisioning platform multiplies databases | REPORTED (F-02) | P-17; audit backlog B-01…B-07 |
| 2 | One shared database role and one shared SSO secret across tenants: a single leak crosses every tenant | REPORTED (F-23, ODOO-01); code VERIFIED | P-05, P-17 |
| 3 | Two tenancy models in code; a registration could land in either | VERIFIED | P-01 |
| 4 | Older bundles put the tenant registry and price list inside customer databases | VERIFIED on the local rig | `MUMTAZ_MODULE_REGISTRY_REVIEW.md` §5.6; P-06, P-16 |
| 5 | The entitlement resolver fails open for unknown features, so "no entitlement defined" reads as "allowed" for some callers | VERIFIED | `MUMTAZ_SAAS_CONTROL_PLANE.md`; fix with the tenant agent |
| 6 | Production runs a feature branch, not `main`; what is installed where is unrecorded | REPORTED / UNKNOWN | P-02; audit V-pack |
| 7 | Client and staff data sit in reusable code in a public repository | VERIFIED | P-15 |
| 8 | Three price lists and unverified public claims on the new website page | VERIFIED | P-09 |
| 9 | Provisioning runs inside one Odoo worker; a long build can hit the worker time limit and leave a half-built database | VERIFIED behaviour (flagged, not dropped); limits on the server UNKNOWN | P-03 |
| 10 | The control plane, the flagship ERP and several customer systems share one server | REPORTED | Audit D-04; P-02 |
