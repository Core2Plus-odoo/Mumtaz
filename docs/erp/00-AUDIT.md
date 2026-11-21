# 1. Current-system technical and functional audit

Date: 20 Nov 2026. Scope: this repository (`Core2Plus-odoo/Mumtaz`, 252
commits, first commit 30 Jun 2026) and what its documents say about the live
servers. Nothing on a server was touched; server facts are quoted from
`README.md`, `docs/ARCHITECTURE.md`, `docs/mumtaz-jewel/*` and
`c2p-delivery-system/docs/07-mumtaz-c2p-crm-findings.md` and tagged as such.

## 1.1 Platform determination

**[VERIFIED] Path (A): Odoo-based ERP, Odoo 19 Community, with two ERP-connected
applications.** `Dockerfile` is `FROM odoo:19`; `config/odoo.conf` adds
`/mnt/extra-addons`; `.github/workflows/jewel-odoo-tests.yml` checks out the
Odoo 19 Community branch to run the suite; `docs/mumtaz-jewel/CLAUDE.md` forbids
Enterprise code. The connected applications are:

| Application | Stack | System of record | Evidence |
| --- | --- | --- | --- |
| Jawhar (jewellery retail OS) | React 18 + TypeScript + Vite, `apps/jawhar-web` (26 pages) | Odoo, through `mumtaz_jewellery_api` (`/jawhar/v1/*`, runs as the signed-in Odoo user) | `docs/mumtaz-jewel/JAWHAR_INTERFACE.md`, 242 Odoo tests |
| C2P Agency OS (delivery system) | FastAPI + single-file console, SQLite store | Odoo over XML-RPC (CRM lead → sale → project) | `c2p-delivery-system/delivery_api/store.py` (sqlite3), `docs/01-architecture.md` |
| Mumtaz platform API (`zaki-server`) | FastAPI, SQLite user cache, JWT | Odoo (auth, tenants, control plane) | `README.md`, `docs/ARCHITECTURE.md` (ports differ between the two documents: 8001 vs 8002) |

**[VERIFIED] Three distinct products share one `addons/` tree:**

1. **Mumtaz platform** (multi-tenant SaaS shell): 37 `mumtaz_*` modules: tenant manager, control plane (plans, features, subscriptions, usage), Stripe billing, API gateway, SSO, subdomain routing, portals, branding/theme, SME profile and onboarding, marketplace, media buying, CFO toolkit (ingestion of bank/transaction files), AI/voice services, ZAKI AI CFO bridge, e-invoicing (UAE QR, KSA ZATCA, Pakistan FBR), financial reports, lead scraper and nurture, CRM starter, website.
2. **C2P group internal**: `c2p_project_tracker` (portfolio ↔ delivery across two legal companies, RAID, change requests, milestone history; 57 test functions) and `c2p_command_center`.
3. **Jawhar jewellery edition**: 13 `mumtaz_jewellery*` modules plus demo (pricing engine, gold-rate maker-checker, serial-tracked pieces, VIP tiers and record rules, sales with frozen rate, counter, trays, AI agents with autonomy levels, kiosk and try-on, outreach with consent, AML/KYC, stores and gold reconciliation, channels, client app, stock import).

## 1.2 Repository and engineering state

| Area | Finding | Tag |
| --- | --- | --- |
| Odoo version | 19.0 Community; manifests mostly `19.0.1.0.0`, 30 of 52 modules carry **no version string** | [VERIFIED] |
| Standard apps the custom code builds on | `stock` (4 modules), `account` (4), `sale_management` (3), `crm` (2), `purchase` (1), `project` (2), `mail`, `portal`, `website`. **No module depends on `hr`, `hr_payroll`, `mrp`, `repair`, `maintenance`, `point_of_sale`, `fleet`, `quality`, `helpdesk` or any `l10n_*`** | [VERIFIED] |
| Automated tests | Jawhar: 242 Odoo tests + 19 engine tests, green on a fresh database (run 20 Nov 2026, `scripts/jewel_ci.sh`). `c2p_project_tracker`: 57 tests, green since 21 Nov 2026 (they had never run on Odoo 19 and failed in 20 places on the Datetime deadline). **All 37 platform modules: 0 tests**, but since 21 Nov every one installs and upgrades on a fresh database in CI (`scripts/platform_ci.sh`) | [VERIFIED] |
| CI | `ci.yml`: manifest validation, flake8 + bugbear, bandit, XML validation, dependency audit. `test.yml`: compileall and "tests if present". `jewel-odoo-tests.yml`: the real Odoo suite for the jewellery modules. `jawhar-web.yml`: tsc, vitest, build | [VERIFIED] |
| Security hygiene | 14 modules ship no `ir.model.access.csv` (eight are theme/website/installer shells with no models; `mumtaz_api`, `mumtaz_sso`, `mumtaz_financial_reports`, `mumtaz_subdomain_routing`, `c2p_command_center`, `mumtaz_jewellery_outreach` need a look). Record rules exist in 20 modules. `sudo()` appears **298 times in 34 modules** (the first count of 56 covered five modules); since 21 Nov every call carries a reason and CI enforces it, with three open REVIEW items (portal dashboards, ZAKI snapshot, command centre). Raw SQL only in `mumtaz_subdomain_routing/patch.py` (2) | [VERIFIED] |
| Company scoping | Jawhar: every custom model carries `company_id` (finding 3 closed 20 Nov). Platform: of 22 model files in marketplace, media buying, CFO and lead modules, 12 mention `company_id`; control plane models reference it twice. The tenant model is **one Odoo database per tenant**, so cross-tenant leakage is prevented by the database boundary, not by rules | [VERIFIED] |
| Migrations | 2 modules declare hooks; no `migrations/` folders anywhere. Schema changes so far rely on `-u` upgrades of additive fields | [VERIFIED] |
| Audit trail | `mail.thread` tracking in 19 places across media buying, marketplace and control plane; Jawhar has its own audit models (`jewellery.api.audit`, `jewellery.vip.access.log`, `jewellery.ai.run`, AML events) | [VERIFIED] |
| Documentation | Jawhar: complete (roadmap, reconciliation per slice, gap analysis, interface, protocol). Platform: `docs/ARCHITECTURE.md`, `DEPLOYMENT.md`, `MONITORING.md`, `VPS_SETUP.md`. C2P delivery: eight numbered docs and a build log. **No project charter, decision register, data dictionary, posting catalogue, security matrix or traceability matrix existed before this audit** | [VERIFIED] |
| Business logic outside git | The live C2P CRM database carries 25 `ir.actions.server` records on `crm.lead` (qualification, scoring, assignment, archival), two addons untracked in the production working tree and one installed with no source on the addons path (inspection of 5 Oct 2026) | [VERIFIED, by document] |

## 1.3 Live environments (as documented; not inspected in this session)

| Environment | What | Source |
| --- | --- | --- |
| Hostinger VPS `187.77.128.199`, checkout `/opt/mumtaz` | Production: `erp.mumtaz.digital`, `app`, `zaki`, `marketplace`, `admin`, `delivery.mumtaz.digital` (C2P console) | root `CLAUDE.md`, `README.md` |
| Odoo database `Mumtaz_ERP` | Platform tenant registry and the company's own ERP | `README.md` |
| Odoo database `Mumtaz_C2P` | C2P CRM: 41,182 leads, 2 won, 29,484 archived without audit trail | `c2p-delivery-system/docs/07-…` |
| Jawhar staging `/opt/mumtaz-jewel-staging`, database `jewel_demo`, `jewel.mumtaz.digital` | Synthetic demo of the jewellery edition; **deployed up to the kiosk slice, eight later slices merged to `main` but not yet deployed** | this session |
| GitHub Actions | CI on every push; production deploy is a manual workflow | `.github/workflows` |

[ASSUMPTION] The production Odoo serves several tenant databases from one
instance behind `mumtaz_subdomain_routing`; the number of live tenants and
which modules each has installed are not in the repository.

## 1.4 Functional audit by domain (summary; detail in `01-CAPABILITY_MATRIX.md`)

| Domain | State | Evidence |
| --- | --- | --- |
| Organisation, companies, branches | **Partial.** Standard `res.company` multi-company; `mumtaz_org_config` binds an SME organisation to a company and subdomain; C2P's two-company structure modelled in the project tracker. No branch or cost-centre model beyond standard analytic accounts | manifests, `c2p_project_tracker/README.md` |
| Users, roles, security | **Partial.** Standard groups; Jawhar has a five-role model with record rules and tests; platform roles are per module and untested | security folders |
| CRM | **Existing (two flavours).** Standard `crm` + `mumtaz_crm_starter` (7-stage GCC/PK pipeline), lead scraper and nurture (WhatsApp provider model), Jawhar pipeline and trays. Logic in the live CRM is partly database-stored | modules, findings doc |
| Sales, quotations, orders | **Existing.** Standard `sale_management`; Jawhar adds approved-rate pricing frozen on the line, counter commit in one transaction, discount limits | `mumtaz_jewellery_sale` (5 test files) |
| Procurement, suppliers | **Minimal.** Standard `purchase` used by marketplace (RFQ wizard) and media buying; vendor portal module exists without tests | `mumtaz_marketplace`, `mumtaz_vendor_portal` |
| Warehouse and inventory | **Existing for jewellery.** Serial-tracked pieces, on-approval location, transfers via transit location, per-store reconciliation in fine grams, stock import. Generic warehousing is standard `stock`, unconfigured | `mumtaz_jewellery_stores` (9 tests) |
| Finance, accounting, tax | **Partial.** Standard `account`; invoices carry the rate snapshot (Jawhar); e-invoicing for three jurisdictions exists **without tests**; financial reports module (P&L, BS, TB, aged) exists **without tests**; no localisation (`l10n_*`) installed by any module; VAT and AML thresholds deliberately left to a named finance manager | modules, Jawhar CLAUDE.md |
| Treasury, bank reconciliation | **Missing beyond standard.** CFO toolkit ingests transaction files for review, but does not post to the ledger | `mumtaz_cfo_*` |
| Fixed assets, depreciation | **Missing.** `account_asset` is not in Community; nothing in the repository | manifests |
| HR, attendance, payroll | **Missing.** No module depends on `hr`; payroll is Enterprise or OCA | manifests |
| Projects, costing, timesheets | **Existing for C2P.** Portfolio/delivery link, milestones, RAID, change requests, 60/40 split, margin; standard `project`; no timesheet costing module | `c2p_project_tracker` |
| Manufacturing, quality | **Missing.** Jewellery workshop deferred to standard `mrp`/`repair` configuration (plan Slice 10) | Jawhar gap analysis |
| Maintenance, fleet | **Missing** | manifests |
| Service, helpdesk | **Missing** (Enterprise `helpdesk`; OCA alternative) | manifests |
| POS, e-commerce | **Partial.** Jawhar counter is a custom online-only till on `sale`; marketplace is a B2B listing/inquiry layer on `sale`/`purchase`; no `point_of_sale` or `website_sale` dependency | modules |
| Documents, approvals | **Partial.** Standard attachments and activities; approvals are built per product (gold-rate maker-checker, AI drafts with digest-bound approval, change requests). No generic approval engine | code |
| Budgeting, analytics, dashboards | **Partial.** Owner cards (Jawhar), CEO dashboard (media agency), control-plane dashboard, C2P command centre, ZAKI board pack. No budgets | modules |
| Notifications, automations, integrations | **Partial.** Stripe billing (webhook events model), API gateway with keys and usage log, rate feed adapter (Jawhar), e-invoicing gateways; no integration register | modules |
| AI agents, BI | **Existing (governed) in Jawhar**: autonomy levels A–E, drafts, approvals inbox, audit, restricted data never sent. Platform AI (`mumtaz_ai`, `mumtaz_voice`, ZAKI) exists **without tests or a documented policy** | `mumtaz_jewellery_ai` |
| Industry vertical | **Existing: jewellery** (deep). Media buying (agency) and consulting (C2P) are the other two verticals present | modules |

## 1.5 Critical risks found

| # | Risk | Severity | Where |
| --- | --- | --- | --- |
| R1 | Business logic of the live C2P CRM lives in database server actions with no version control, tests or rollback | High | `Mumtaz_C2P` |
| R2 | 37 platform modules, including e-invoicing and financial reports (both touch statutory output), have no automated tests; the fresh-database install check exists since 21 Nov 2026, and four modules could not install before it | High | `addons/mumtaz_*` |
| R3 | 298 `sudo()` calls, now labelled and CI-checked; 53 sites in three places serve data with `sudo()` to any signed-in user, portal users included (REVIEW-01/03/04); cross-company tests exist only for Jawhar | High | control plane, marketplace, vendor portal, e-invoicing |
| R4 | No localisation installed by code: tax, chart of accounts and invoice layout depend on what each tenant's database happens to have | High | finance |
| R5 | Three application stacks (Odoo, two FastAPI services with SQLite) each hold user or engagement state; the SQLite stores are not backed up by the documented Odoo backup | Medium | `zaki-server`, C2P delivery |
| R6 | No `migrations/` discipline; every schema change so far has been additive, which will not hold for finance work | Medium | repository |
| R7 | Documentation names different ports for the same service and the production checkout contains untracked addons | Medium | docs, VPS |
| R8 | Jawhar staging lags `main` by eight merged slices; the demo shown to prospects is not what is on `main` | Low | staging |

## 1.6 What must be preserved (do not rebuild)

- Odoo native `account`, `stock`, `sale`, `purchase`, `crm`, `project`: every custom module extends them; nothing replaces them.
- The Jawhar door (`/jawhar/v1`), its record-rule re-proof tests and its autonomy model: the reference pattern for every future API and agent.
- The gold-rate maker-checker, pricing engine and frozen-rate line: the one place prices come from.
- `c2p_project_tracker`'s adoption of the two-company structure rather than a new project concept.
- The deploy scripts' refusal paths (`deploy.sh` refusing `main` on staging, the admin-password guard).
