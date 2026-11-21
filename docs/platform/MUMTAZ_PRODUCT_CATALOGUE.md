# Mumtaz Product Catalogue

State at commit `ff1c797` plus the first platform slice on branch `ccr-620c243b-p9qlq1`, 21 Nov 2026.

## 1. Conclusion

- **Six products, none of them "Available".** Two are **Pilot** (Mumtaz ERP, Jawhar) and four are **Planned** (Pharma, ZAKI, Marketplace, Delivery OS). "Available" means sold, provisioned and supported in production; nothing meets that today.
- **Only Mumtaz ERP can be requested through the control plane**, and only as a staging trial. That path was proven end to end on a local Odoo 19 rig; it has not run on the production server.
- **C2P, IG2 and Faizy are not products.** They are customer deployments and are deliberately absent from the control-plane catalogue.
- **White-label is a capability across products, not a product.** A brand record exists; nothing renders it yet.
- **No price is authoritative.** Three price lists disagree (P-09). The first ERP plan is a staging trial at 0.

The catalogue is now data, not a document: the model `mumtaz.product` in `addons/mumtaz_control_plane`, seeded from `data/product_catalogue.xml`. Each record carries its status and the evidence for it. This file explains those records; if they disagree, the records in the control database are what the system acts on.

## 2. Status legend

| Tag | Meaning |
|---|---|
| **VERIFIED** | Read in code, or run on the local Odoo 19 + PostgreSQL 16 rig on 21 Nov 2026 |
| **REPORTED** | From a repository document or an earlier session note; not re-checked. This covers **everything about the live server**, including database names and whether a site is up |
| **PROPOSED** | Design. Not built |
| **UNKNOWN** | Needs server evidence or an owner answer |

Commercial status values (the `status` field of `mumtaz.product`, VERIFIED in `models/product.py`):

| Value | Meaning |
|---|---|
| Available | Sold, provisioned and supported in production |
| Pilot | Works end to end for selected customers or in staging |
| Planned | Not built, or not safe to expose yet |

A product can be opened to registration requests only if it is not Planned, is delivered as a customer database, and has both an install profile and an access feature. The model refuses otherwise (VERIFIED by test `test_planned_product_cannot_be_opened`).

Decision IDs: `P-xx`, `D-xx` and `ADR-xxx` are in [`docs/erp/project/DECISION_REGISTER.md`](../erp/project/DECISION_REGISTER.md); "audit D-xx" and finding IDs are in [`docs/infrastructure-audit/`](../infrastructure-audit/).

## 3. The catalogue

### 3.1 Products (in the control-plane catalogue)

Database names and "live" statements are REPORTED. Code locations and catalogue statuses are VERIFIED.

| Product (code) | What it is | Category | Domain | Code | Database (REPORTED) | Delivery mode | Status | Open to registration | Missing before it can be sold | Decision needed |
|---|---|---|---|---|---|---|---|---|---|---|
| **Mumtaz ERP** (`erp`) | General business ERP on Odoo 19 Community: contacts, CRM, sales, purchasing, inventory, accounting, financial reports | General ERP | erp.mumtaz.digital | Standard Odoo apps + `addons/mumtaz_financial_reports`; profile `bundle_mumtaz_erp` | `Mumtaz_ERP` (flagship); new tenants `stg_<code>` | Own Odoo database per customer | **Pilot** | Yes (staging trial only) | Production enablement; localisation by country; e-mail delivery of the sign-in link; billing; backups; a price | P-02, P-03, P-06, P-07, P-09, P-17 |
| **Jawhar** (`jawhar`) | Jewellery edition: pieces, gold rate, pricing, VIP clients, trays, kiosk, governed AI agents | Industry edition | jewel.mumtaz.digital | `addons/mumtaz_jewellery*` (15), `apps/jawhar-web`, `website/jewel` | `jewel_demo` | Own Odoo database per customer | **Pilot** | No | An install profile; the tenant agent; brand rendering; sign-on | P-05, P-06, P-14 |
| **Mumtaz Pharma** (`pharma`) | Pharmacy edition | Industry edition | pharma.mumtaz.digital | Branches `pharma-*`; **not on `main`** | `mumtaz_pharma` | Own Odoo database per customer | **Planned** | No | Code on `main` or in its own repository; platform review; everything Jawhar needs | P-15 (repository), then as Jawhar |
| **ZAKI** (`zaki`) | AI finance assistant: embedded in the ERP, standalone, or as part of an edition | AI | zaki.mumtaz.digital | `addons/mumtaz_zaki` (survivor); three other front/back ends | none of its own | Inside another product | **Planned** | No | A safe implementation; metering; entitlement that fails closed | P-11, D-03, D-10 |
| **Marketplace** (`marketplace`) | Supplier discovery, catalogues, requests for quotation | Marketplace | marketplace.mumtaz.digital | `addons/mumtaz_marketplace`, `addons/mumtaz_organization`, `sites/marketplace.mumtaz.digital/storefront` | via an API that was deleted | Shared service | **Planned** | No | A topology decision; cross-company write fix (ODOO-08); a working front end | P-12 |
| **Delivery OS** (`delivery_os`) | The agency delivery system: AI-run Odoo implementation pipeline | Operations service | delivery.mumtaz.digital | `c2p-delivery-system/` (FastAPI + single-file console) | SQLite files | Shared service | **Planned** | No | Customer accounts, tenant separation, billing, backups, fail-closed authentication | P-13 |

Why each status (the `evidence` field, VERIFIED in the seed file):

| Product | Basis for the status | Tag |
|---|---|---|
| Mumtaz ERP — Pilot | A staging tenant was provisioned end to end on a development rig on 21 Nov 2026 by `scripts/tenant_journey_ci.sh`: registration, approval, trial entitlement, an isolated database, administrator sign-in. Not yet run on the production server; billing is not connected | VERIFIED |
| Jawhar — Pilot | Runs as a staging/demo instance with its own test suite. The control plane has no install profile for it, so it cannot be provisioned from there | Tests VERIFIED in the repository; instance REPORTED |
| Pharma — Planned | Its modules are on a separate branch, not on `main`, and have not been reviewed for the platform. A staging tenant is REPORTED live, which is why it could be argued as Pilot; it stays Planned until the code is reviewable | REPORTED |
| ZAKI — Planned | Reviewed 21 Nov 2026: none of the existing implementations is safe to expose. One architecture is proposed, not built | VERIFIED — `MUMTAZ_AI_ARCHITECTURE.md` |
| Marketplace — Planned | The Odoo module assumes all tenants share one database, which the platform does not do | VERIFIED |
| Delivery OS — Planned | In internal use. It has no customer accounts, billing or tenant separation that would let an outside organization subscribe | Code VERIFIED; use REPORTED |

### 3.2 Not products (not in the control-plane catalogue)

| System | What it is | Category | Domain | Code | Database (REPORTED) | Why it is not a product | Rule |
|---|---|---|---|---|---|---|---|
| **C2P internal ERP** | The group's own CRM and ERP | Customer deployment (internal customer) | core2plus.com | `addons/c2p_*` + 25 CRM rules held only in the database | `Mumtaz_C2P` | It serves one organization: the group itself. Its modules name C2P staff, clients and methodology | A customer of the platform. Never merged with IG2. Its code stays out of reusable profiles |
| **IG2** | An external client's accounting system | Customer deployment (external client) | ig2.mumtaz.digital | A feature branch, not `main`; `mumtaz_financial_reports` from `main` | `Mumtaz_IG2` | It belongs to a client | No automatic change. Compatibility testing and client approval before anything is applied. No staging exists today |
| **Faizy** | Family-care services venture | Customer deployment (independent venture) | myfaizy.com | `faizy/` + its production branch | `faizy_prod` | A separate business with its own brand, data model and release branch | Not forced into the ERP architecture. Candidate to move to its own repository (D-12) |
| mumtaz.digital | Corporate website | Supporting website | mumtaz.digital | `addons/mumtaz_website_builder` (canonical) | none decided | It sells the products; it is not one | `MUMTAZ_WEBSITE_IMPLEMENTATION.md`; P-10 |
| WordPress sites | Unrelated content sites | Supporting website | odditytrend.com, youngcraze.com | `wordpress-sites/` | MariaDB | Unrelated to the platform | Audit D-12 |
| app.mumtaz.digital | Intended home of the control plane's customer-facing side | Shared platform | app.mumtaz.digital | Static portal in `sites/app.mumtaz.digital/portal`; its backend was deleted | SQLite (orphaned) | It is the platform, not a product | Not continued as built; see `MUMTAZ_SAAS_CONTROL_PLANE.md`; P-02 |

A staging or demo tenant of a product (`jewel_demo`, `mumtaz_pharma`, any `stg_*` database) is an environment of that product. It is neither a product nor a customer deployment.

## 4. Product by product

### 4.1 Mumtaz ERP

**Scope today (VERIFIED).** The install profile `mumtaz_erp` installs `base, mail, contacts, crm, sale_management, purchase, stock, account, mumtaz_financial_reports`; optional `hr, project, mrp, mumtaz_crm_starter, mumtaz_customer_portal`. All nine base modules exist in Odoo 19 Community or in `addons/` and install cleanly; the journey check confirms each is `installed` in the new database. The plan `erp_staging_trial` grants the ERP and its accounting, inventory and sales areas for 14 days and switches ZAKI and Marketplace off explicitly.

The profile deliberately leaves out: every control-plane module; `mumtaz_core`, `mumtaz_branding` and `mumtaz_theme` until they are reworked; `mumtaz_sso` until audit ODOO-01 is fixed.

**Gaps.**

| Gap | Tag |
|---|---|
| No chart of accounts or taxes: no localisation is installed, so accounting is not usable for real books until a country package is chosen | VERIFIED (ADR-006, backlog item 5) |
| What the flagship database `Mumtaz_ERP` actually has installed, and how it differs from this profile | UNKNOWN |
| The reference transactions (order-to-cash, purchase-to-pay) have no tests on a generic tenant | VERIFIED (ERP backlog items 8, 9) |
| `mumtaz_financial_reports` has 0 tests; `mumtaz_einvoicing` has 0 tests and is in no profile, while the website page says e-invoicing is installed for every tenant | VERIFIED |
| The sign-in link is stored for an operator to pass on; it is not e-mailed | VERIFIED |
| No payment step; the Stripe module is not connected to the journey | VERIFIED |
| Real provisioning is not enabled on any server | REPORTED / P-03 |

**Next step (PROPOSED).** Decide P-02 and P-03, run the journey check on a staging instance of the control plane, then add localisation by country (P-06).

### 4.2 Jawhar

**Scope today (VERIFIED).** Fifteen `mumtaz_jewellery*` modules with their own CI (`scripts/jewel_ci.sh`), a React web app (`apps/jawhar-web`) talking to Odoo through `/jawhar/v1`, a public site (`website/jewel`), and the only governed AI stack in the repository (`mumtaz_jewellery_ai`). No Jawhar manifest depends on a foundation or platform module, which keeps it clean but also means the platform cannot yet brand, entitle or meter it.

**Gaps.** No install profile in the control plane; no tenant agent; brand record not rendered; no sign-on path from the control plane; `mumtaz_jewellery_demo` and `mumtaz_jewellery_website` must be excluded from a customer profile (VERIFIED — `MUMTAZ_MODULE_REGISTRY_REVIEW.md` §5.7, §7.2).

**Next step (PROPOSED).** Add a `jawhar` profile matching the module order of `jewel_ci.sh`, then build the tenant agent. The stricter Jawhar rules in `docs/mumtaz-jewel/CLAUDE.md` stay in force.

### 4.3 Mumtaz Pharma

**Scope today (REPORTED).** `pharma_*` modules, a staging deploy kit and documentation on four unmerged branches; a neutralised staging tenant reported live since 18 Nov 2026. None of it is on `main`, so none of it was reviewed here.

**Gaps.** Everything listed for Jawhar, plus: the code must become reviewable first.

**Next step (PROPOSED).** Decide where the code lives, then review it against the platform rules before it enters the catalogue as Pilot.

### 4.4 ZAKI

**Scope today (VERIFIED).** Three applications for zaki.mumtaz.digital (a browser-only page, a Node app written for one named client, an unauthenticated FastAPI backend) and eight Odoo AI/CFO modules. `mumtaz_zaki` is the right home but has no model call, reports cash as zero and sums all companies under `sudo()`. Detail and file references: [`MUMTAZ_AI_ARCHITECTURE.md`](MUMTAZ_AI_ARCHITECTURE.md).

**Three modes (PROPOSED).** Embedded in the ERP; standalone thin client at zaki.mumtaz.digital that signs the user into their own tenant; optional per edition, where the edition registers extra tools. One implementation serves all three.

**Gaps.** No safe implementation; no metering; the entitlement lookup for AI fails open; model keys are stored in plain text in tenant databases.

**Next step (PROPOSED).** The first slice in the AI document: fix the connector, extract the governed core from Jawhar, add one read-only "ask" endpoint with a run log. Do not merge the implementations before that is verified (P-11).

### 4.5 Marketplace

**Scope today (VERIFIED).** `mumtaz_marketplace`: listings, categories, inquiries, a purchase-order-to-RFQ wizard, an entitlement check. `mumtaz_organization`: a public directory of partner organizations with join requests. The static storefront depends on an API that was deleted.

**MVP scope (PROPOSED, from the directive).** Opt-in only. Start with four things and nothing else: supplier discovery, supplier catalogues, requests for quotation, and an authorised integration that lets a tenant's ERP send an RFQ and receive the answer. No payments, no logistics, no ratings in the MVP.

**Gaps.** Listings must be visible across tenants, which a database-per-tenant model cannot do from inside a tenant. The module also hard-depends on both control-plane modules, and writes across companies (ODOO-08).

**Next step (PROPOSED).** Decide the topology (P-12): one shared marketplace database that tenants reach through an authorised API, opted into per tenant by entitlement. Only then cut the module's dependencies.

### 4.6 Delivery OS

**Scope today (VERIFIED).** A FastAPI application with a single-file console: presales, discovery, requirements, estimate, proposal, functional analysis, generated modules, configuration applied to a live Odoo over XML-RPC, all with a local fallback when no model provider is available. SQLite stores; an optional multi-tenant mode.

**Gaps.** Authentication is switched on by a setting and fails open if mistyped (audit C2P-01); stored credentials can be redirected (C2P-02, -03); no backup of the stores or the encryption key (C2P-14); no customer accounts or billing.

**Next step (PROPOSED).** Keep the FastAPI foundation. Evaluate it as a subscribable product before changing its architecture (P-13); the approved Consulting OS plan in `c2p-delivery-system/docs/06-consulting-os-plan.md` is the existing design for that.

## 5. White-label

White-label is a capability of the platform, sold as a way of delivering a product, not as a product.

| Part | State | Tag |
|---|---|---|
| Brand record `mumtaz.brand` (names, logo, colours, e-mail and report text) | Exists in `addons/mumtaz_branding`; no code renders it | VERIFIED |
| Tenant fields `brand_id` and `partner_id` (the white-label owner) | Exist on `mumtaz.tenant` | VERIFIED |
| Resolution path host → tenant → brand → tokens | Not built | PROPOSED — `MUMTAZ_DESIGN_SYSTEM.md`, `docs/jawhar/WHITE_LABEL_SPECIFICATION.md` |
| What a partner may change and what is fixed | Defined in the design document | PROPOSED (P-14) |
| A bundle named `enterprise_partner` | Exists; pulls control-plane modules into the tenant | VERIFIED; to be replaced |

White-label needs the tenant agent first (it carries the brand document to the tenant) and one signed-off token set.

## 6. Prices

No price is authoritative. Three lists exist, and they disagree.

| Source | Figures | Tag |
|---|---|---|
| Bundle records, `addons/mumtaz_tenant_manager/data/mumtaz_bundle_data.xml` | Starter 49, Growth 149, Finance 199, AI CFO 299 (monthly, USD); partner bundle 0; `mumtaz_erp` 0 pending the decision | VERIFIED |
| Website Builder page since PR #187, `addons/mumtaz_website_builder/views/snippets/mumtaz_blocks.xml` | Starter $49, Growth $199, add-ons $12–$35, organization plans $8 / $6 per SME | VERIFIED (page unpublished) |
| Older figures: the portal wizard's $149 / $399 / $999 and the old static site's AED 99 / 299 | See D-11 and `MUMTAZ_WEBSITE_IMPLEMENTATION.md` §4.2 | REPORTED |

Until P-09 (which supersedes the question in D-11) names one list and one source record:

- the only seeded plan is `erp_staging_trial` at 0 (VERIFIED);
- no page should publish a price;
- the single source should be `mumtaz.plan` in the control database, with the website reading from it rather than carrying its own copy (PROPOSED).

## 7. What must be true before a product is marked Available

PROPOSED acceptance list, the same for every product:

1. It has an install profile whose module closure contains no control-plane module, checked in CI.
2. The journey check passes for it on a staging control plane, not only on a development rig.
3. Its tenant databases are backed up and one restore has been rehearsed (P-17).
4. Entitlement is enforced inside the tenant and fails closed.
5. A price exists in `mumtaz.plan` and payment is connected.
6. Its public claims match what the code does.
7. A named person owns support for it.

The status field is changed by the owner in the control database, with the evidence written into the record.
