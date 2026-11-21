# 2. ERP module and capability matrix, with standard-versus-custom disposition

Classification follows the blueprint §5 registry. **Status** is AS-IS in this
repository: Existing / Partial / Missing / Unknown / Out of scope.
**Disposition** is the TO-BE decision this programme proposes: Standard (ship
with Odoo 19 Community, configure) / Configure / Integrate / Extend (small
custom add-on) / Build (approved gap) / Defer / Exclude. Items marked
[DECISION] need an owner's approval in the decision register.

Availability of Odoo apps in Community is stated from the Odoo 19 Community
addons tree as known to this programme; **verify on the installed server
before relying on any row** [ASSUMPTION].

## Platform (PLT)

| ID | Capability | Status | Evidence | Disposition |
| --- | --- | --- | --- | --- |
| PLT-01 | Tenant, company, branch, department, cost centre | Partial | One DB per tenant (`docs/ARCHITECTURE.md`); `res.company` multi-company; C2P two companies; no branch model | Standard for company; **Configure** analytic plans for branch/cost centre; Extend only if a branch needs its own sequences [DECISION ADR-003] |
| PLT-02 | Identity, roles, approvals, delegation | Partial | Groups per module; Jawhar roles tested; SSO via HMAC from the control panel (`mumtaz_sso`); no delegation, no generic approval engine | Standard groups + record rules; **Build** a small approval model only after three products prove the same need (today each has its own) |
| PLT-03 | Shared contacts and counterparties | Existing | `res.partner` with jewellery, media and CRM extensions | Standard |
| PLT-04 | Item and service catalogue, UoM, pricelists | Existing | `product` with jewellery and marketplace extensions | Standard |
| PLT-05 | Currency, tax, fiscal periods, localisation | **Missing in code** | No `l10n_*` dependency; VAT left to the finance manager | **Configure** `l10n_ae` / `l10n_sa` / `l10n_pk` per tenant; `l10n_gcc_invoice` for bilingual invoices [DECISION ADR-006] |
| PLT-06 | Documents, attachments, messaging, audit | Partial | `mail.thread` on some models; Jawhar audit models | Standard chatter + tracking on every transactional model; Build nothing |
| PLT-07 | Workflow, jobs, notifications, integrations | Partial | `base_automation` not used by code; crons in Jawhar; Stripe webhooks; API gateway | Standard crons and automation rules; **Build** an integration register (document, not code) |
| PLT-08 | Data governance, import, external identities | Partial | Jawhar stock import (new); `base_import` standard; no `source_system/source_id` convention | Standard `base_import`; **Extend**: an `x_external_ref` convention on migrated records (see data model) |

## Commercial and operations

| ID | Capability | Status | Evidence | Disposition |
| --- | --- | --- | --- | --- |
| CRM-01 | Leads, opportunities, activities, campaigns | Existing | `crm`, `mumtaz_crm_starter`, lead scraper/nurture, Jawhar pipeline | Standard; **Build**: move the 25 database server actions of the C2P CRM into a versioned module (R1) |
| SLS-01 | Quotation, pricing, orders | Existing | `sale_management`; Jawhar pricing on the line (tests) | Standard; jewellery pricing stays Extend |
| SLS-02 | Contracts, recurring billing | Partial | Control plane subscriptions + Stripe (platform's own billing) | Standard `sale_subscription` is Enterprise; keep the control plane for SaaS billing; **Defer** for tenants |
| SLS-03 | Returns, credit notes, customer service | Partial | Standard credit notes; Jawhar old-gold exchange | Standard |
| PUR-01 | Requisition, RFQ, PO | Partial | `purchase` via marketplace RFQ wizard, media buying | Standard; Configure approval thresholds |
| PUR-02 | Vendor bills, 3-way match, payment | Partial | Standard `account` + `purchase`; untested | Standard; Configure `bill_control` policy |
| INV-01 | Warehouses and moves | Existing | `stock`; Jawhar stores on warehouses | Standard |
| INV-02 | Lot/serial, reservations, replenishment | Existing (jewellery) | serial pieces, memos, transfers | Standard tracking; jewellery rules Extend |
| INV-03 | Valuation and landed costs | Unknown | No module sets valuation; Jawhar records cost basis per piece | **Configure** `stock_account` automated valuation, FIFO or specific-identification per tenant [DECISION ADR-005]; `stock_landed_costs` standard |
| FIN-01 | General ledger and controls | Partial | `account`; no lock-date policy in code; invoice rate snapshot (Jawhar) | Standard; **Configure** lock dates, journals, posting rules (posting catalogue) |
| FIN-02 | AR, invoicing, collections | Partial | Standard; e-invoicing module exists untested; financial reports module untested | Standard; **Test then keep** `mumtaz_einvoicing`; **Evaluate** replacing `mumtaz_financial_reports` with standard reports + OCA `mis_builder` [DECISION] |
| FIN-03 | AP, bank, reconciliation | Partial | Standard reconciliation; CFO toolkit ingests files for review only | Standard `account` reconciliation; OCA `account_statement_import_*` for files; CFO toolkit stays an analysis tool, never posts |
| FIN-04 | Budgets, cash forecast, assets, reporting | Missing | nothing | Budgets and assets are Enterprise in 19: **Integrate** OCA `account_asset_management`, `mis_builder_budget` [DECISION]; cash forecast Defer |
| FIN-05 | Intercompany, consolidation, allocations | Partial | C2P 60/40 split and margin in the tracker (operational, not accounting) | **Configure** standard inter-company rules where both companies are on one DB; consolidation Defer |
| PRJ-01 | Projects, tasks, timesheets, budgets | Existing (C2P) | `c2p_project_tracker`, 57 tests | Standard `project` + `hr_timesheet`; tracker stays Extend |
| SRV-01 | Helpdesk, field service, SLA | Missing | — | Enterprise apps; **Integrate** OCA `helpdesk_mgmt` only when a tenant asks; Defer |
| SRV-02 | Equipment, maintenance, rental | Missing | — | Standard `maintenance` (Community) when needed; rental Defer |
| MFG-01 | BOM, production, quality | Missing | Jewellery workshop deferred | Standard `mrp`, `repair`; quality is Enterprise → OCA `quality_control_oca` [DECISION]; Defer until a workshop tenant exists |
| HRM-01 | Employees, attendance, leave, expenses | Missing | — | Standard `hr`, `hr_attendance`, `hr_holidays`, `hr_expense`; Defer until scoped |
| HRM-02 | Payroll | Missing | — | Enterprise; OCA `payroll` for UAE/PK needs localisation by a qualified expert; **Defer**, never hard-code rules |
| OMC-01 | POS, e-commerce, portals | Partial | Jawhar counter (custom, online-only); marketplace; customer and vendor portals (untested) | Jawhar counter stays Extend (decision recorded in gap analysis); standard `point_of_sale` for non-jewellery tenants; `website_sale` Configure |
| BI-01 | Reporting, analytics, command centres | Partial | Owner cards, CEO dashboard, command centre, ZAKI board pack | Standard pivot/graph + spreadsheet; **Extend** only with metric lineage (UX doc) |
| AI-01 | Governed agents | Existing (Jawhar), Partial (platform) | levels A–E with tests; `mumtaz_ai` untested | **Extend** the Jawhar agent policy to the platform; retire duplicate provider layers [DECISION] |
| VRT-01 | Industry packs | Existing: jewellery, media buying, consulting | 13 + 1 + 2 modules | Keep; each gets a module spec under the standard |

## Platform SaaS layer (not in the blueprint registry; C2P-specific)

| Capability | Status | Disposition |
| --- | --- | --- |
| Tenant provisioning, bundles, feature flags, plans, usage | Existing, untested | Keep; add install tests and a provisioning dry-run; server-side enforcement of a disabled app is a documented TODO (`docs/ARCHITECTURE.md` §4) → Build |
| Stripe billing of tenants | Existing, untested | Keep; add webhook idempotency tests |
| API gateway (keys, usage, async jobs) | Existing, untested | Keep; audit `sudo()` |
| Subdomain routing (db per host) | Existing, raw SQL patch | Keep; review patch |
| SME signup, onboarding, branding | Existing, untested | Keep |

## Standard-versus-custom summary

| Count | Items |
| --- | --- |
| Standard or Configure | PLT-01/03/04/05/06/07/08, CRM, SLS-01/03, PUR-01/02, INV-01/02/03, FIN-01/02/03/05, PRJ, SRV-02, MFG, HRM-01, OMC (non-jewellery), BI base |
| Integrate (OCA) | assets, budgets, statement import, helpdesk, quality, payroll (all [DECISION]) |
| Extend (small add-on, justified) | jewellery pricing/pieces/VIP/counter/agents, C2P tracker, media buying, external-ref convention, approval model (later) |
| Build (approved gap) | versioned C2P CRM logic (R1), integration register, feature-flag server enforcement |
| Defer | subscriptions for tenants, consolidation, cash forecast, field service, rental, payroll |
| Exclude | Enterprise-only modules; any second pricing engine; a second user store |
