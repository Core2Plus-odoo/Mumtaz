# Mumtaz Product Integration Map

State at commit `ff1c797` plus the first platform slice on branch `ccr-620c243b-p9qlq1`, 21 Nov 2026.

## 1. Conclusion

- **One integration between the control plane and a product works end to end: provisioning a Mumtaz ERP tenant.** It was run for real on a local Odoo 19 rig. Everything the control plane should do with a tenant *after* provisioning (entitlements, usage, brand, sign-on) is missing.
- **Most other connections between products are broken or were never real.** The customer portal, the marketplace storefront and two of the three ZAKI applications call a backend (`zaki-server`) that was deleted from the repository. Tenants are set up to pull AI credentials every day from an API that is not in the repository.
- **Two existing mechanisms must not be reused:** the single sign-on bridge with one secret shared by every tenant (audit ODOO-01), and any service that reaches tenant databases with one administrator account (audit APP-01/02).
- **The target has one rule and one missing component.** The rule: the control plane writes to a tenant only at provisioning and never reads its business data (ADR-002). The component: a small tenant-side agent that pulls a signed entitlement and brand document and pushes usage totals.
- **Customer deployments are not integration targets.** Nothing in this map changes `Mumtaz_C2P`, `Mumtaz_IG2` or `faizy_prod`.

## 2. Status legend

| Tag | Meaning |
|---|---|
| **VERIFIED** | Read in code, or run on the local Odoo 19 + PostgreSQL 16 rig on 21 Nov 2026 |
| **REPORTED** | From a repository document or an earlier session note; not re-checked. This covers **everything about the live server** |
| **PROPOSED** | Design. Not built |
| **UNKNOWN** | Needs server evidence or an owner answer |

State values used below: **works** (run and checked in this session, or covered by tests that ran), **exists, unproven** (code is there; no test and no observed run), **broken** (cannot work as written), **missing** (no code).

Decision IDs: `P-xx`, `D-xx`, `ADR-xxx` are in [`docs/erp/project/DECISION_REGISTER.md`](../erp/project/DECISION_REGISTER.md); "audit D-xx", `ODOO-xx`, `APP-xx`, `C2P-xx`, `F-xx` are in [`docs/infrastructure-audit/`](../infrastructure-audit/).

Related, not repeated here: [`MUMTAZ_MASTER_ARCHITECTURE.md`](MUMTAZ_MASTER_ARCHITECTURE.md) · [`MUMTAZ_PRODUCT_CATALOGUE.md`](MUMTAZ_PRODUCT_CATALOGUE.md) · [`MUMTAZ_SAAS_CONTROL_PLANE.md`](MUMTAZ_SAAS_CONTROL_PLANE.md) · [`MUMTAZ_AI_ARCHITECTURE.md`](MUMTAZ_AI_ARCHITECTURE.md) · [`MUMTAZ_WEBSITE_IMPLEMENTATION.md`](MUMTAZ_WEBSITE_IMPLEMENTATION.md) · [`MUMTAZ_MODULE_REGISTRY_REVIEW.md`](MUMTAZ_MODULE_REGISTRY_REVIEW.md) · the per-integration register with idempotency and retry columns, [`docs/erp/architecture/INTEGRATION_REGISTER.md`](../erp/architecture/INTEGRATION_REGISTER.md) (INT-01 … INT-11).

## 3. Integration matrix

### 3.1 Control plane and products

| # | Pair | Direction | Mechanism today | State | Target mechanism (PROPOSED) | Must never happen |
|---|---|---|---|---|---|---|
| 1 | Control plane → ERP tenant: **provisioning** | CP → tenant, once | In-process: the provisioner creates the database, installs the `mumtaz_erp` profile, sets the administrator, company name and base address, verifies, and issues Odoo's one-time invitation link (`addons/mumtaz_tenant_manager/services/provisioning.py`) | **works** — VERIFIED on the local rig by `scripts/tenant_journey_ci.sh`; not run on any server (P-03) | Same, run by the queue worker on the control-plane instance, with a database role per tenant (P-17) and localisation by country (P-06) | A tenant marked active without a verified database. An automatic drop of a half-built database. A control-plane module installed in the tenant |
| 2 | Control plane → ERP tenant: **entitlements** | should be tenant ← CP | The resolver `mumtaz.feature.access.service` reads `mumtaz.tenant` and `mumtaz.subscription` in its own database. It only works where control-plane tables sit in the same database as the caller. `mumtaz.erp.module.access` toggles user groups locally | **missing** across databases — VERIFIED. Callers treat "control plane absent" as "allowed" (`mumtaz_cfo_base`, portals) | Tenant agent pulls a signed entitlement document for its tenant code; features are gated in the tenant and fail closed when the document is absent or expired | The control plane logging into a tenant to switch features. A feature treated as granted because nothing was defined |
| 3 | ERP tenant → control plane: **usage** | tenant → CP | `mumtaz.usage.metric` exists in the control plane; nothing in `addons/` writes rows to it | **missing** — VERIFIED | Tenant agent pushes daily totals (users, AI tokens, storage). Totals only | Row-level business data leaving the tenant |
| 4 | Control plane → tenant: **AI credentials** | tenant ← CP (pull) and CP → tenant (push) | `mumtaz_core` pulls keys daily from `app.mumtaz.digital/api/v1/tenant/<code>/credentials` and accepts a push at `/mumtaz/platform/push-credentials` (`auth="none"`, token check). The serving side is not in the repository | **broken** — VERIFIED (client only). Whether anything answers in production is UNKNOWN | Platform-paid model key held in the service environment, never in a tenant database; metered through item 3 (`MUMTAZ_AI_ARCHITECTURE.md`, decision in its §8) | Provider keys stored in plain text in tenant databases. A token-only route that can overwrite them |
| 5 | Control plane ↔ **Jawhar** tenant | none | No Jawhar manifest depends on a platform module; there is no Jawhar install profile | **missing** — VERIFIED | A `jawhar` install profile plus the tenant agent and a thin bridge module depending only on `mumtaz_jewellery` and the agent | The Jawhar modules depending on `mumtaz_tenant_manager` or `mumtaz_control_plane` |
| 6 | Control plane ↔ **Pharma** tenant | none | Code is not on `main` | **missing** — REPORTED | As Jawhar, after the code is reviewable | — |
| 7 | Host name → tenant database | request routing | `mumtaz_subdomain_routing` patches Odoo's database filter and looks the host up in the control database's `mumtaz_tenant` table, where `state = 'active'`; off unless an environment switch is set | **exists, unproven** — VERIFIED code, 0 tests; whether it is enabled in production is UNKNOWN | Keep the approach; test it; route only tenants whose provisioning was verified (now guaranteed by slice 1 for provisioned tenants; the manual "Mark Active" button still bypasses it) | A host resolving to another tenant's database. A suspended tenant still routed |

### 3.2 Between products

| # | Pair | Direction | Mechanism today | State | Target mechanism (PROPOSED) | Must never happen |
|---|---|---|---|---|---|---|
| 8 | ERP ↔ **ZAKI** (embedded) | inside the tenant | `mumtaz_zaki` reads the ledger through the ORM and serves `/zaki/api/snapshot` to accounting users. No model call. Cash figure is always 0; figures cover all companies under `sudo()` | **exists, wrong numbers** — VERIFIED by reading; access check covered by 2 tests | Tools run as the signed-in user through the ORM, with company scope, a run log, and a grounding check. See `MUMTAZ_AI_ARCHITECTURE.md` §5 | An agent with an administrator login or free SQL. A figure in an answer that no tool supplied |
| 9 | ZAKI **standalone** ↔ tenant | external app → tenant | Three applications. Two depend on the deleted `zaki-server`. The third (`platform/zaki`) uses one Odoo administrator for every tenant and has no authentication | **broken** / **unsafe** — VERIFIED; what is served at the domain is UNKNOWN | A thin client that signs the user into their own tenant and calls the same `/zaki/api/*` routes (P-11) | One shared administrator credential across tenants (audit APP-01/02). A model key in the browser |
| 10 | ERP ↔ **Marketplace** | tenant ↔ shared service | `mumtaz_marketplace` lives inside an Odoo database and hard-depends on both control-plane modules; the storefront calls the deleted API | **broken** across tenants — VERIFIED | One shared marketplace database; a tenant opts in by entitlement and uses an authorised API to publish a catalogue, send an RFQ and receive answers (P-12) | A tenant's records visible to another tenant without opt-in. Cross-company writes (ODOO-08) |
| 11 | **Delivery OS** ↔ Odoo | both | XML-RPC with a per-connection credential stored encrypted in the console; writes to a live Odoo pass approval gates (`policy.py`). INT-10 | **exists** — VERIFIED code; REPORTED in use | Unchanged until Delivery OS is evaluated as a product (P-13). Fix C2P-01/02/03 first | An ungated write to a live customer database. Stored credentials redirected to another host |
| 12 | Delivery OS → GitHub | out | Token stored encrypted; generated modules pushed to the addons repository. INT-11 | **exists** — VERIFIED code | Unchanged; generated code is customer code and must not land in a reusable profile | — |
| 13 | Jawhar web app ↔ Jawhar Odoo | in | `/jawhar/v1` JSON door with Odoo session and audit log. INT-01 | **works** — VERIFIED by the Jawhar test suite | Keep; it is the pattern for a product API | — |

### 3.3 Website, billing, statutory

| # | Pair | Direction | Mechanism today | State | Target mechanism (PROPOSED) | Must never happen |
|---|---|---|---|---|---|---|
| 14 | Website → control plane: **registration** | site → CP | `POST /mumtaz/cp/signup` (JSON) in `addons/mumtaz_control_plane/controllers/signup.py`. Closed unless the system parameter `mumtaz_control_plane.public_signup` is `1`. Creates a pending request only; hourly cap, duplicate suppression, honeypot | **works** — VERIFIED by tests and the journey check. No website form calls it yet | The website form posts to it once P-08 is decided; add e-mail verification and a captcha before opening | The public route creating a tenant, a subscription or a database. Registration telling a visitor whether an e-mail is already registered |
| 15 | Website → CRM: **leads** | site → CRM | New page: native website form creating `crm.lead`, validated in `addons/mumtaz_website_builder/controllers/website_form.py`. Old static site: `mumtaz_api` routes `/api/mumtaz/v1/demo` and `/contact`. Another static copy posts to a path with no backend in the repository | New form **works** in tests (VERIFIED); what the live site does is UNKNOWN | One lead door on the website's own database; decide whether leads stay there or are pushed to the group CRM (P-10) | Website leads firing the 25 database-stored CRM rules in `Mumtaz_C2P` unreviewed |
| 16 | Website → **prices** | CP → site | `mumtaz_website` reads `mumtaz.plan` if present, otherwise shows hard-coded figures; the new builder page carries its own literal prices | **inconsistent** — VERIFIED | The website reads plans from one source record (P-09) | Two price lists in public at once |
| 17 | Billing ↔ **Stripe** | out, and webhook in | `mumtaz_billing_stripe`: client, `/mumtaz/stripe/webhook` (public, signature check), card pages, daily charge job. INT-06 | **exists, unproven** — VERIFIED code, 0 tests; whether live keys are configured is UNKNOWN | Connect to the subscription created at approval; dedupe on the Stripe event id; test before any real charge. Two of its methods are callable over RPC (audit ODOO-03) and must be closed first | A charge without a test trail. Payment changes without the owner's authorisation |
| 18 | E-invoicing ↔ **tax authorities** | out | `mumtaz_einvoicing`: UAE builds a QR code and validates a tax number, with no network call; KSA (ZATCA) and Pakistan (FBR) clients exist and post on invoice confirmation. INT-07, INT-08 | **exists, unproven** — VERIFIED code, 0 tests; whether any real invoice was cleared is UNKNOWN | Sandbox tests and idempotent retry first (ERP backlog item 11); decide native `l10n_sa_edi` against the custom client (ADR-006) | A public claim of automatic submission that the code does not make. Network calls inside invoice posting without a failure path |
| 19 | Identity / **SSO** | CP → tenant | `mumtaz_sso`: `/mumtaz/sso?token=…`, HMAC with a secret the provisioner plants in every tenant from one environment variable | **unsafe** — VERIFIED; in no install profile | See section 5 (P-05) | One secret that opens every tenant |

### 3.4 Customer deployments — no integration by design

| System | Today | Rule | Tag |
|---|---|---|---|
| `Mumtaz_C2P` (C2P internal ERP) | Uses `c2p_*` modules and database-stored CRM rules; Delivery OS can connect to it over XML-RPC | An internal customer. No platform change is applied automatically. Never merged with IG2 | REPORTED |
| `Mumtaz_IG2` (external client) | Uses `mumtaz_financial_reports` from `main` and client code on a feature branch | **No automatic change of any kind.** A change to a shared module that IG2 uses needs a compatibility test on a copy of its database and the client's approval before deployment | REPORTED |
| `faizy_prod` (Faizy) | Own modules, own branch, own database role | Independent. Not connected to the control plane, entitlements or the ERP profiles | REPORTED |

One consequence for the platform: `mumtaz_financial_reports` is in the new ERP profile **and** in use at IG2. A change to that module is a change to a client system and follows the IG2 rule.

## 4. The registration journey

`Register organization → Choose Mumtaz ERP → Assign entitlement → Provision isolated staging tenant → Open ERP workspace`

```
 Visitor            Website            Control plane (Odoo)                     Tenant database
    │  fill form       │                      │                                      │
    │─────────────────►│  POST /mumtaz/cp/signup (closed by default)                 │
    │                  │─────────────────────►│ 1 request = new                      │
    │                  │                      │                                      │
 Platform admin ──────────── Approve ────────►│ 2 organization (res.partner)         │
                                              │   tenant record: staging, draft      │
                                              │   trial subscription = entitlement   │
 Platform admin ──────────── Provision ──────►│ 3 entitlement checked, then queued   │
                                              │                                      │
                          scheduled worker ──►│ 4 create database ──────────────────►│ created
                                              │   install profile, set admin ───────►│ installed
                                              │   verify ───────────────────────────►│ checked
                                              │   one-time invitation link ◄─────────│ issued
                                              │ 5 tenant = active, request = ready   │
 Administrator ◄──── link passed on by an operator (not e-mailed yet)                │
    │  open link, choose password ──────────────────────────────────────────────────►│ signed in
    │  /odoo ───────────────────────────────────────────────────────────────────────►│ workspace
```

| Step | What happens | Built | Tested | Tag |
|---|---|---|---|---|
| 0 | A form on mumtaz.digital collects organization, contact, e-mail, product | No. No page calls the route | — | PROPOSED |
| 1 | `/mumtaz/cp/signup` records a pending request; nothing else | Yes | Unit tests (`TestSignupRoute`, public-intake tests) and the journey check | VERIFIED |
| 1a | E-mail verification and captcha before a request is accepted | No | — | PROPOSED (P-08) |
| 2 | A Super Admin approves: organization as `res.partner`, staging tenant record (`stg_<code>`), trial subscription on `erp_staging_trial` | Yes | `test_approval_creates_organization_staging_tenant_and_entitlement` and others | VERIFIED |
| 2a | Entitlement resolved by the shared service: ERP granted, ZAKI and Marketplace not granted | Yes | Unit tests and the journey check | VERIFIED |
| 3 | Provision is refused without approval or without a current entitlement; otherwise the tenant is queued | Yes | `test_no_provisioning_before_approval`, `test_no_provisioning_without_entitlement` | VERIFIED |
| 4 | The worker creates the database, installs the profile, verifies it and gets the invitation link | Yes | Journey check: real database, all nine modules installed | VERIFIED on the local rig |
| 4a | On a server not allowed to create databases the same step creates nothing and the request returns to approved | Yes | Journey check (dry path) and `test_dry_run_does_not_make_the_request_ready` | VERIFIED |
| 4b | A failed run leaves the database in place, flags it, and blocks a blind retry | Yes | `test_failed_run_blocks_a_blind_retry` | VERIFIED |
| 5 | Tenant active, request ready, workspace address shown | Yes | Unit tests and the journey check | VERIFIED |
| 6 | The administrator opens the link, sets a password and lands in the web client; the link is dead afterwards | Yes | Journey check over HTTP | VERIFIED on the local rig |
| 6a | The link is e-mailed to the administrator | No. An operator copies it from the tenant record | — | PROPOSED |
| 6b | The workspace address resolves on the internet (DNS wildcard, nginx, certificate, host routing) | Routing module exists | Not tested | UNKNOWN on the server (P-03) |
| 7 | Payment, conversion from trial to paid, production tenant | No | — | PROPOSED (P-07, P-09) |
| 8 | Real provisioning enabled on a production control plane | No | — | Needs P-02, P-03, P-17 and a named approval |

Isolation checks made by the journey script directly in PostgreSQL (VERIFIED): the tenant database has no `mumtaz_tenant`, `mumtaz_subscription` or `mumtaz_plan` table; the control database has no `crm_lead` or `account_move` table; the tenant administrator is not a user of the control database; the tenant database has exactly one internal user.

## 5. Identity

| Topic | Today | Tag |
|---|---|---|
| Authority | Each Odoo database authenticates its own users. There is no account that spans products | VERIFIED |
| First sign-in to a new tenant | Odoo's own invitation link: signed with the tenant database's secret, time-limited, void after the first sign-in. The control plane stores the link for platform administrators only and never holds a password | VERIFIED (slice 1) |
| `mumtaz_sso` | One HMAC secret from one environment variable is planted in every tenant database at provisioning. Whoever holds it can mint a session for any user in any tenant. Audit ODOO-01 / F-23 | VERIFIED |
| Where `mumtaz_sso` is installed | In no install profile. Whether any live database has it is UNKNOWN | VERIFIED / UNKNOWN |
| The secret is still planted | `_apply_settings` still writes the parameter when the environment variable is set. Without the module installed it has no effect. Left unchanged in slice 1 because the consumer side is unknown | VERIFIED |
| Other identity stores | The Delivery OS has its own administrator login (JWT). The deleted `zaki-server` held users in SQLite. Faizy and the Jawhar client app have their own customer sessions | VERIFIED code / REPORTED |

Target (PROPOSED, decision P-05). Two options, in order of preference:

1. **Standard single sign-on with the control plane as identity provider** (OpenID Connect through Odoo's `auth_oauth` on the tenant side). No custom token format; a per-tenant client secret; revocable.
2. **Keep an HMAC bridge, repaired:** a secret generated per tenant at provisioning and stored only in that tenant and the control plane, single-use tokens with a short life, the audience (database) bound into the signature, and tests for replay and cross-tenant use.

Until one is built and tested, sign-in is per tenant with the tenant's own password, and `mumtaz_sso` stays out of every profile. Managers should use Odoo's `auth_totp` (ADR-009).

## 6. Data ownership

One source of truth per kind of data. "Today" is VERIFIED from code unless marked; the target column is PROPOSED where it differs.

| Data | Source of truth today | Target | Notes |
|---|---|---|---|
| Organizations (the customer of record) | Four candidates: `mumtaz.org` (company-per-org), `mumtaz.sme.profile`, `mumtaz.organization` (a public directory, a different concept), and since slice 1 `res.partner` in the control database linked from `mumtaz.tenant.customer_partner_id` | `res.partner` in the control database (P-04); retire `mumtaz.org` (P-01) | Row counts in the live databases are UNKNOWN and decide the migration effort |
| Tenants and their environments | `mumtaz.tenant` in the control database | Same | Which live database holds it is UNKNOWN (P-02) |
| Product catalogue and plans | `mumtaz.product`, `mumtaz.plan` in the control database | Same; the website reads from it | Prices undecided (P-09) |
| Subscriptions | `mumtaz.subscription` in the control database | Same; Stripe is the payment processor, not the record of what a customer is entitled to | Stripe link untested |
| Entitlements | Computed by `mumtaz.feature.access.service` in the control database from plan + subscription + overrides | Same source; the tenant holds a signed, expiring copy | Copy mechanism not built |
| Users and passwords | Each tenant database (`res.users`) | Same; the control plane holds only the administrator's e-mail | The control plane never stores a tenant password (VERIFIED) |
| Ledgers, stock, sales, purchases | Each tenant database (Odoo `account`, `stock`, `sale`, `purchase`) — ADR-004 | Same. Never copied to the control plane | The CSV shadow ledger in `mumtaz_cfo_*` does not post and is not a ledger |
| Leads from the website | `crm.lead` in whichever database runs the website | The website's own database, or pushed to the group CRM (P-10) | Where the live site's leads go today is UNKNOWN |
| AI run logs | `jewellery.ai.run` in a Jawhar tenant; `mumtaz.core.log` (editable by managers) elsewhere; `agent_runs` in the Delivery OS store | One read-only run log per tenant from the shared AI core; token totals pushed to the control plane as usage | `MUMTAZ_AI_ARCHITECTURE.md` |
| Usage totals | `mumtaz.usage.metric` in the control database; nothing writes to it | Written from tenant-agent pushes | — |
| Brand (white-label) | `mumtaz.brand` in the control database; nothing renders it | Same source; the tenant holds a copy delivered with the entitlement document | P-14 |
| Delivery engagements and knowledge | SQLite stores of the Delivery OS | Unchanged until P-13; Odoo stays the system of record for anything financial (ADR-001) | No backup today (C2P-14) |
| Module ownership and install profiles | `registry/classification.json`, `registry.yaml`, bundle records | The registry, extended with owners and profiles and checked in CI (P-16) | — |

## 7. Rules for every integration

1. The control plane writes to a tenant only at provisioning. Afterwards the tenant calls out.
2. No credential is shared between tenants: no shared administrator, no shared secret, and in time no shared database role (P-17).
3. Aggregates may leave a tenant; business records may not.
4. A missing or expired entitlement means "not granted".
5. A public route can only create a request for a person to review.
6. Every outbound integration is listed in `docs/erp/architecture/INTEGRATION_REGISTER.md` with its idempotency key and retry behaviour before it carries real data.
7. An agent uses scoped tools as the signed-in user; anything that posts, pays or sends needs a person's approval.
8. Nothing in this map is applied to `Mumtaz_C2P`, `Mumtaz_IG2` or `faizy_prod` without the approvals named in section 3.4.

## 8. Could not determine

- Which database is the control plane in production, and whether `mumtaz_subdomain_routing` or `mumtaz_sso` is enabled or installed anywhere.
- Whether anything answers at the credential-sync address tenants call, and whether any tenant database holds a provider key.
- Whether Stripe is configured with live keys, and whether any charge has ever been made.
- Whether any e-invoice was ever cleared by a tax authority through this code.
- What is served at zaki.mumtaz.digital, app.mumtaz.digital and marketplace.mumtaz.digital, and where the live website's enquiries go.
- Worker time limits, the `list_db` setting and DNS/certificate arrangements on the instance that would run provisioning.
