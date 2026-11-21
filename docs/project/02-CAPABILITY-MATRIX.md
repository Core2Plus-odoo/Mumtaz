# Deliverable 2 — ERP module and capability matrix

Blueprint §5's canonical registry, scored against this repository. Scoring is
**source-code evidence only** — see the audit's stated limitation: nothing here
asserts what is *installed*.

## Scoring key

| Score | Meaning |
|---|---|
| **Standard** | Odoo's own module covers it; a `depends` entry exists; nothing custom needed |
| **Existing** | Custom code implements it and the implementation looks complete in source |
| **Partial** | Custom code starts it; obvious gaps (no tests, no rules, no posting map) |
| **Missing** | No code addresses it |
| **Unknown** | Cannot be determined without the live instance (DEC-001) |
| **Out of scope** | Deliberately excluded — needs owner confirmation |

---

## Platform layer (blueprint PLT-01 … PLT-08)

| ID | Capability | Score | Evidence / gap |
|---|---|---|---|
| PLT-01 | Tenant, company, org structure | **Partial** | `mumtaz_tenant_manager` (4 models), `mumtaz_organization` (4), `mumtaz_org_config` (2), `mumtaz_control_plane` (16). **Three parallel tenancy mechanisms** (DEC-002); branch/department/cost-centre scopes not modelled at all |
| PLT-02 | Identity, roles, approvals, delegation | **Partial** | `mumtaz_sso` (112 lines), 25 `res.groups` across modules, 222 ACL rows. **No approval-request model anywhere**; no delegation; no segregation-of-duties enforcement. Blueprint §10.1 "no silent self-approval" is unimplemented |
| PLT-03 | Shared contacts and counterparties | **Standard** | `contacts` + `base` depended on; `res.partner` used natively. Correct — nothing custom needed |
| PLT-04 | Item / service catalog | **Standard** | `sale`, `purchase`, `stock` depended on; no custom product model. Correct |
| PLT-05 | Currency, tax, fiscal periods, localization | **Standard + Partial** | `account` depended on (7 modules). Custom layer: `mumtaz_einvoicing` for UAE Peppol / KSA ZATCA / PK FBR. GCC localization packs themselves **Unknown** (DEC-001) |
| PLT-06 | Documents, attachments, messaging, audit | **Partial** | `mail` depended on by 15 modules; **139 fields carry `tracking=True`** so chatter audit exists. No `AuditEvent` model, no retention policy, no redaction policy (blueprint §7.2 audit-event contract) |
| PLT-07 | Workflow, jobs, notification, integration | **Partial** | `ir.cron` jobs exist; `mumtaz_api_gateway` (3 models, API keys + usage log). **No outbox, no idempotency keys, no dead-letter queue** — blueprint §4.4 and §13 unmet |
| PLT-08 | Data governance, import, reference codes | **Missing** | No `ImportBatch`, no `ExternalIdentity`, no `source_system`/`source_record_id` pattern anywhere in 978 fields. This blocks any migration (blueprint §14.1 item 3) |

## Commercial spine (CRM / SLS / PUR)

| ID | Capability | Score | Evidence / gap |
|---|---|---|---|
| CRM-01 | Leads, opportunities, activities, campaigns | **Standard + Existing** | `crm` depended on by 4. Heavy custom growth layer: `mumtaz_lead_scraper` (2,626 lines, 6 models), `mumtaz_lead_nurture` (1,451 lines, 7 models, **0 record rules**), `mumtaz_crm_starter`. **[FACT, prior session]** the live CRM shows 41,182 leads of which 29,484 archived by bulk action, and a server action hardcoding `user_id = 42` as assignment policy — documented in `c2p-delivery-system/docs/07-mumtaz-c2p-crm-findings.md`, **not yet applied** |
| SLS-01 | Quotation, pricing, sales orders | **Standard, unproven** | `sale` + `sale_management` depended on by 2 modules. **No module implements or tests a quote→order flow.** Blueprint §19 Wave 2 cannot be signed off |
| SLS-02 | Contracts, recurring billing, subscriptions | **Existing (SaaS only)** | `mumtaz_control_plane` + `mumtaz_billing_stripe` (799 lines) implement **platform** subscription billing. This is C2P's own revenue, **not** a client-facing subscription product. Do not confuse the two |
| SLS-03 | Returns, rebates, customer service | **Missing** | No RMA, no credit-note request, no helpdesk |
| PUR-01 | Requisition, RFQ, supplier quotes, PO | **Standard, unproven** | `purchase` depended on by 3 (`mumtaz_marketplace`, `mumtaz_media_buying`, `mumtaz_vendor_portal`). No requisition, no budget check, no RFQ comparison |
| PUR-02 | Supplier invoices and settlement | **Standard, unproven** | `mumtaz_vendor_portal` has 7 posting references and **0 models, 0 ACL, 9 `sudo()`** — a pure controller module. No 3-way match anywhere |

## Inventory and finance

| ID | Capability | Score | Evidence / gap |
|---|---|---|---|
| INV-01 | Warehouses and movements | **Standard, unproven** | `stock` depended on by 2 (`mumtaz_customer_portal`, `mumtaz_vendor_portal`) |
| INV-02 | Lot/serial, reservations, replenishment | **Out of scope?** | No code. Needs owner confirmation — a consulting/services business may genuinely not need it (DEC-005) |
| INV-03 | Stock valuation and landed costs | **Out of scope?** | As above |
| FIN-01 | General ledger and controls | **Standard + Unknown** | `account` native, correctly extended. **No posting catalogue** (blueprint §20.1 item 5). Fiscal lock dates, journals, CoA: Unknown |
| FIN-02 | AR, collections, customer invoicing | **Standard + Partial** | `mumtaz_einvoicing` extends `account.move` correctly via `_inherit` + `super().action_post()`. No collections, no dunning, no AR ageing |
| FIN-03 | AP, bank and reconciliations | **Partial** | `mumtaz_cfo_ingestion` (3 models) ingests statements; `mumtaz_cfo_transactions` (3 models). **Role unclear — subledger or parallel ledger? (DEC-004)** |
| FIN-04 | Budgets, cash forecast, assets, reporting | **Partial** | `mumtaz_financial_reports` (375 lines, 1 OWL asset) renders reports with **no documented lineage**. No budget model, no asset/depreciation |
| FIN-05 | Intercompany, consolidation, allocations | **Missing in Odoo** | Notably, C2P's own 60/40 commercial split **is** implemented — in `c2p_project_tracker` (configurable per project, `groups=`-protected) and in the `c2p-intercompany-reserve-close` skill. Nothing generic exists for clients |

## Operations

| ID | Capability | Score | Evidence / gap |
|---|---|---|---|
| PRJ-01 | Projects, tasks, timesheets, budgets | **Existing, unproven** | `c2p_project_tracker`: 3 concrete models + 1 abstract, 89 fields, 2 OWL dashboards, 2 QWeb PDFs, 12 `groups=`-protected commercial fields, 5 constraints, **57 tests — all NOT RUN**, never installed. The best-engineered module in the repository and the only one with no runtime evidence at all |
| SRV-01 | Helpdesk, field service, SLA | **Missing** | — |
| SRV-02 | Equipment, maintenance, rental | **Missing** | — |
| MFG-01 | BOM, production, routing, quality | **Missing** | — |
| HRM-01 | Employees, attendance, leave, expenses | **Missing** | No `hr` dependency anywhere |
| HRM-02 | Payroll, advances, obligations | **Missing** | — |
| OMC-01 | POS, e-commerce, portals | **Partial** | Portals built heavily: `mumtaz_customer_portal`, `mumtaz_vendor_portal`, `mumtaz_app_portal` (604 lines, 23 `sudo()`), `mumtaz_portal_routing` (793 lines, 23 `sudo()`), `mumtaz_marketplace` (7 models). No POS, no e-commerce checkout |

## Intelligence and AI

| ID | Capability | Score | Evidence / gap |
|---|---|---|---|
| BI-01 | Reporting, analytics, command centres | **Partial** | `mumtaz_ceo_dashboard` (47 lines, 1 OWL asset — a shell), `mumtaz_financial_reports`, `c2p_project_tracker`'s two OWL dashboards. **No `MetricDefinition` model, so no semantic KPI layer and no lineage** — blueprint §11.3 requires group totals to state whether eliminations are applied; nothing does |
| AI-01 | Recommendations and governed AI agents | **Existing, ungoverned** | `mumtaz_ai` (7 models, provider abstraction for Anthropic + OpenAI), `mumtaz_voice` (5 models, 672 lines), `mumtaz_zaki` (5 models). Separately `c2p-delivery-system` is a full LLM pipeline with local fallback. **Blueprint §12 governance is absent**: no action classification (read/recommend/draft/act-with-approval), no named service identity per agent, no dry-run, no spend limit, no kill switch, no evaluation corpus. `mumtaz_ai` touches `account` (2 posting references) — an AI module reaching the ledger with no approval gate is the single riskiest design in the repository |
| VRT-01 | Industry extensions | **Existing (as knowledge, not modules)** | 11 verticals in `c2p-delivery-system/delivery_api/data/industry_playbooks.json` with a five-role composition layer. Knowledge assets, not Odoo modules — which is the right call |

---

## Aggregate

| Score | Count of 31 registry rows |
|---|---|
| Standard (native, nothing custom needed) | 4 |
| Existing | 4 |
| Partial | 12 |
| Missing | 8 |
| Out of scope (needs confirmation) | 2 |
| Unknown | 1 |

**Read this way:** the platform and growth layers are where the 21,772 lines went.
The transactional spine that makes an ERP an ERP — quote-to-cash, procure-to-pay,
record-to-report — is `depends` entries and nothing more. Twelve "Partial" scores
share one cause: code written without tests, record rules, or a posting map.

That is the roadmap's whole shape: **finish the twelve Partials to a provable
standard before starting any of the eight Missings.**
