# 02. ERP module and capability matrix

Rows follow the blueprint's canonical registry (§5). **Status** = what exists in the repository or tenant: `Existing`, `Partial`, `Missing`, `Unknown` (cannot be established without running or configuring a database), `Out of scope`. **Disposition** is the blueprint's fit-gap vocabulary: **Standard** (native Odoo, no work), **Configure**, **Extend** (small add-on), **Integrate**, **Defer**, **Exclude**; every disposition is `[P]` proposed until the charter is signed (decision D-002). "Class" is the blueprint's CORE / COMMON / OPTIONAL. Evidence is a path or a counted fact; behaviour not executed in this audit is marked.

| ID | Capability | Class | Status | Evidence (verified) | Proposed disposition and note |
| --- | --- | --- | --- | --- | --- |
| PLT-01 | Tenant, company, branch, department | CORE | **Partial** | Tenant = database; `mumtaz.tenant` registry. No branch/department model found; pharma has no `company_id` | Tenant: Existing. Company: **Standard** (`res.company`) + enforce scope in custom models `[D-003]`. Branch/department: Configure analytic or extend only if scoped |
| PLT-02 | Identity, roles, approvals, delegation | CORE | **Partial** | Odoo groups; pharma roles Operations / Finance Controller / Tax Approver / Admin; maker-checker on tax rules, exceptions; ZAKI JWT SSO; `mumtaz_sso` is a stub (0 models, 0 XML). No delegation, no Auditor role | Extend: Auditor role, SoD matrix, generic approval mixin `[D-007]`; **Integrate**: SSO |
| PLT-03 | Contacts and counterparties | CORE | **Existing (standard)** | `contacts`, `res.partner` used throughout; customer receivable account taken from partner property | **Standard**; add bank accounts and tax IDs as configuration |
| PLT-04 | Item and service catalog | CORE | **Existing (standard) + Partial** | `product.*`; jewellery piece identity (20 models); pharma SKU tax classification extension | **Standard** + Extend (done). Lot/expiry: see INV-02 |
| PLT-05 | Currency, tax, fiscal period, localization | CORE | **Partial** | Standard `account`; custom approved-only PK tax rules; **no `l10n_pk`**, generic COA on staging; no lock-date policy configured | **Configure** + decide localization `[D-006]`; the custom rule engine stays a *control* layer over `account.tax`, not a second source of rates |
| PLT-06 | Documents, messaging, audit | CORE | **Partial** | Chatter + `tracking=True` on key fields; immutable `pharma.raw.event` archive; chatter notes for overrides | **Standard** chatter; Extend with an audit-event view for sensitive actions `[P]` |
| PLT-07 | Workflow, jobs, notification, integration | CORE | **Partial** | New stage/next-step/owner computed flow + queues (NOT RUN); crons (neutralized on staging); `mumtaz_api_gateway` (3 models); no notification engine verified | Extend: notifications from queues `[P]`; **Integrate** via governed contracts `[D-008]` |
| PLT-08 | Data governance, import, reference codes | CORE | **Partial** | Idempotent raw-event ingestion with dedupe keys; statement import with row validation; sequences. `scripts/migrate.py` purpose **unknown** | Extend (done for COD); migration tooling `[P]` per `quality/` strategy |
| CRM-01 | Leads, opportunities, campaigns | COMMON | **Existing** | standard `crm`; `mumtaz_crm_starter`, `mumtaz_lead_scraper` (7 models), `mumtaz_lead_nurture` (11 models) | **Standard**; review lead tools for compliance `[D]` |
| SLS-01 | Quotation, pricing, sales orders | COMMON | **Existing (standard)** | `sale_management` on pharma and jewellery; pharma tax gate on confirm | **Standard** + pharma gate (done) |
| SLS-02 | Contracts, subscriptions, recurring billing | OPTIONAL | **Missing** | none; `sale_subscription` is Enterprise-only | **Defer** unless required `[D-002]` |
| SLS-03 | Returns, rebates, customer service | COMMON | **Partial** | parcel `returned` state, returned-COD exception; no RMA/credit-note flow | Configure standard returns; Extend COD refund and tax-event reversal `[P]` (backlog PHA-RET-001) |
| PUR-01 | Requisition, RFQ, POs | COMMON | **Existing (standard) / Missing** | `purchase` installed on pharma, used by marketplace; requisition not referenced | **Standard**; requisition **Defer** |
| PUR-02 | Supplier bills, 3-way match, payment | COMMON | **Unknown** | standard `account` + `purchase`; no custom evidence; kit adds payables tools | **Standard**; verify on a database `[P]` |
| INV-01 | Warehouses and movements | COMMON | **Existing (standard)** | `stock`; `pharma_partner_stock` derives roll-forward from done moves | **Standard** + Extend (done) |
| INV-02 | Lot/serial, reservation, replenishment, **expiry** | OPTIONAL (CORE for pharma) | **Missing for pharma** | jewellery has piece identity; no pharma lot/expiry/recall config; `product_expiry` not referenced | **Configure** standard lots + expiry (FEFO) + recall report; backlog PHA-INV-001 |
| INV-03 | Valuation and landed cost | COMMON | **Unknown** | `stock_account` not referenced; costing policy undecided | **Configure** after `[D-005]` |
| FIN-01 | General ledger and controls | CORE | **Existing (third-party) + Partial** | standard `account` + pinned third-party accounting kit (hardened); custom draft-only COD entries; no lock-date policy | **Standard**/**Integrate** kit; Extend (done); close policy `[D-011]` |
| FIN-02 | AR, collections, customer invoicing | COMMON | **Existing (standard)** | invoices gated by tax rule; collection credit to be reconciled to invoice (**not exercised**, gap G-4) | **Standard**; close G-4 |
| FIN-03 | AP, bank, reconciliations | COMMON | **Partial** | reconciliation hub (courier/gateway/bank vs ledger runs); **no bank-statement import** | Extend: statement import + matching (PHA-FIN-002) |
| FIN-04 | Budgets, cash forecast, assets, reporting | OPTIONAL | **Partial / Unknown** | `base_account_budget` installed with the kit; asset module not referenced; `mumtaz_financial_reports` (0 models) | **Configure**; verify kit reports `[P]` |
| FIN-05 | Intercompany, consolidation, allocations | OPTIONAL | **Missing** | none | **Defer** unless 2+ entities `[D-003]` |
| PRJ-01 | Projects, tasks, timesheets, budgets | OPTIONAL | **Partial** | `c2p_project_tracker` (ACL + rules + 57 tests); `hr_timesheet` not referenced | Review overlap with standard `project` `[P]` |
| SRV-01 | Helpdesk, field service, SLA | OPTIONAL | **Missing** | none | **Defer** |
| SRV-02 | Equipment, maintenance, rental | OPTIONAL | **Missing** | none (`maintenance`, `fleet` not referenced) | **Defer** |
| MFG-01 | BOM, production, quality | OPTIONAL | **Missing (installed, unconfigured)** | `mrp` on the pharma install list; no config or tests | **Configure** only if pharma manufactures `[D-002]` |
| HRM-01 | Employees, attendance, leave, expenses | OPTIONAL | **Missing** | no `hr*` referenced | **Defer** `[D-002]` |
| HRM-02 | Payroll, advances | OPTIONAL | **Missing** | none; payroll is localization-sensitive | **Defer**; local expert approval required |
| OMC-01 | POS, e-commerce, portals | OPTIONAL | **Partial** | pharma storefront (`website_sale`); `mumtaz_customer_portal`, `mumtaz_vendor_portal`, marketplace; **no POS** (jewellery POS audit in `docs/mumtaz-jewel/POS_NATIVE_AUDIT.md`) | **Standard** website_sale; POS per jewellery decision |
| BI-01 | Reporting, dashboards, command centres | COMMON | **Partial** | pivots (ageing, pipeline), `c2p_command_center`, `mumtaz_ceo_dashboard`, `mumtaz_financial_reports`; no metric lineage | Extend: role dashboards over **read models** (PLT/BI) |
| AI-01 | Governed AI agents | OPTIONAL | **Partial / Unknown** | `mumtaz_ai` (7 models), `mumtaz_voice`, `mumtaz_jewellery_ai`; governance (approval, kill switch, evaluation) **not established** | Audit against blueprint §12 before extending `[P]` |
| VRT-01 | Industry extensions | OPTIONAL | **Existing** | pharma (10), jewellery (14), marketplace | Keep each independently installable |

## Reading the matrix

- **Pharma tenant, honest summary:** strong on tax gating, reconciliation controls and COD; weak on lots/expiry/recall, localization, bank import, role dashboards, CI, and company scope.
- **Not everything is needed.** HRM, MFG, SRV, PRJ, FIN-05 and SLS-02 are marked Defer/Missing: the blueprint says not to assume every project needs every module. Scope is decided in the charter (D-002), not here.
- The `Unknown` rows need a configured test database to answer; they are listed so they are not silently treated as present.
