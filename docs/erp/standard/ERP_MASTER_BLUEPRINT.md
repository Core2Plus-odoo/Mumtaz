# ENTERPRISE ERP DEVELOPMENT MASTER BLUEPRINT
## Architecture, Business Domain Model, Engineering Methodology, Controls, UX, AI and Delivery Standards

**Version:** 1.0  
**Prepared for:** C2P Group / reusable client ERP delivery  
**Primary execution environment:** Claude Code  
**Status:** Reference blueprint; adapt and approve project-specific scope before implementation  
**Date:** 20 November 2026  

> **Operating principle:** Build an ERP as a system of interdependent, auditable business transactions—not a collection of forms, dashboards, and isolated modules. Every feature must preserve data integrity, business flow, financial effects, permissions and downstream consequences.

## 0. How to use this blueprint

This document is a **master standard**, not a claim that every listed feature belongs in every project. Start every implementation with a signed project charter, industry profile, process fit-gap assessment and platform decision. Mark each capability **Standard / Configure / Extend / Integrate / Defer / Out of scope**, with an owner and acceptance criteria. The standard-first principle is mandatory.

Three intended deployment paths:

1. **Odoo-based ERP:** Prefer native Odoo capabilities, configuration and Studio where supportable; use custom add-ons only for approved gaps. Follow the exact installed Odoo version's ORM, security, views, assets, and testing conventions.
2. **Custom ERP platform:** Prefer a well-structured modular monolith with explicit domain boundaries; adopt a documented technology stack and architecture decision before coding. Avoid premature microservices.
3. **ERP-connected applications:** Preserve the ERP as system of record for financial and operational transactions, and integrate external portals, mobile apps, AI agents and industry tools via governed contracts.

**Never blend these paths silently.** A custom platform has different schema, security, transaction and migration requirements than Odoo. Claude Code must detect the repository and ask for a decision only when a material missing fact prevents a safe choice.

**Normative language:** MUST = non-negotiable; SHOULD = expected absent documented exception; MAY = optional.

---

## 1. Product mission and outcomes

Build a reliable, easy-to-use, secure and expandable business operating system that:

- Connects lead-to-cash, procure-to-pay, inventory, projects, service, HR, payroll and record-to-report where in scope.
- Supports multi-company, branches, departments, warehouses, cost centers, projects, users, currencies, tax jurisdictions and languages as required.
- Preserves traceable relationships between origin documents, operational fulfillment, accounting entries, settlements and reports.
- Enables role-based workflows, approvals, alerts, delegated access and immutable or tamper-evident audit evidence.
- Gives staff simple task-oriented screens and gives executives reliable drill-down dashboards rather than isolated KPIs.
- Is configurable by industry, localization and client without forking the entire codebase.
- Supports integration and a controlled AI layer, with humans retaining authorization for high-impact actions.

### 1.1 Business outcomes and measures

For each project define baseline, target, owner, data source and measurement frequency for: quote-to-order conversion, order fulfillment, invoice turnaround, DSO/aging, purchasing cycle time, stock accuracy, stockout rate, closing-cycle length, project margin, asset utilization, SLA compliance, user adoption, data completeness, and exception rate. **Do not invent baselines or report targets as achieved.**

### 1.2 Non-functional characteristics

Reliability, transactional correctness, confidentiality, tenant/company isolation, recoverability, performance, accessibility, maintainability, traceability, observability, scalability, upgradeability, and integrations must have testable acceptance criteria. Capacity and SLA targets must be explicitly agreed; do not promise a latency or uptime figure without an infrastructure design and load model.

---

## 2. Discovery and project qualification: no coding before these decisions

Create `docs/project/PROJECT_CHARTER.md` with: sponsor, legal entities, countries, business units, industry, operating model, process owners, key users, current systems, source data, volumes, user count, concurrency expectations, deployment/hosting, recovery objectives, licenses, timeline, budget, in-scope/excluded modules, migration history, external systems, risk tolerance and sign-off parties.

**Mandatory decision register:**

| ADR | Decision | Required evidence |
|---|---|---|
| ADR-001 | Odoo extension vs greenfield custom ERP vs integration | fit-gap, ownership, licensing, upgrade and total cost |
| ADR-002 | Tenant model | database per tenant or approved shared DB with enforceable isolation |
| ADR-003 | Company/branch/department/warehouse model | legal structure and ownership of records |
| ADR-004 | Financial source of truth | posting authority, ledgers, reconciliation and close |
| ADR-005 | Inventory valuation | costing policy, negative stock, returns and accounting treatment |
| ADR-006 | Localization | jurisdiction-specific taxes, invoice rules, currencies, payroll, e-invoicing |
| ADR-007 | Workflow/approval engine | approval thresholds, delegation and SoD |
| ADR-008 | Integration strategy | APIs, events, retries, idempotency, ownership of master data |
| ADR-009 | Security and identity | RBAC/ABAC, SSO, MFA, company isolation, audit and retention |
| ADR-010 | Deployment and disaster recovery | environments, backup, RPO/RTO, rollback and ownership |
| ADR-011 | Accounting close/correction policy | locks, reversals, adjustments, backdating controls |
| ADR-012 | Stack or Odoo version and supported dependencies | compatibility matrix and test evidence |

**Fit-gap classification:** Each requirement must have ID, business owner, priority, process reference, native capability, configuration approach, extension/integration decision, cost/risk, acceptance evidence and approval status. Unknown is not equivalent to approved.

---

## 3. Development methodology and governance

Adopt **architecture-led, domain-driven, iterative delivery** with early end-to-end vertical slices and strict stage gates. Do not try to generate the entire ERP in one undifferentiated coding task.

### 3.1 Lifecycle and deliverables

| Gate | Phase | Must produce | Gate to advance |
|---|---|---|---|
| G0 | Discovery & current-state audit | charter, AS-IS flows, inventories, stakeholders, constraints | signed scope and assumptions |
| G1 | Solution architecture & fit-gap | TO-BE flows, module map, ADRs, deployment and data ownership | architecture and scope approval |
| G2 | Foundation | repo conventions, identity, company model, master data, audit, CI | security and baseline smoke tests |
| G3 | Vertical slices | one process end-to-end with posting, permissions, reporting | live functional demo, integration tests |
| G4 | Wider module delivery | prioritized module increments and regression suites | product-owner acceptance per module |
| G5 | Data migration & integrations | mapping, dry runs, reconciliation, rollback plan | validated migrated totals and sign-off |
| G6 | UAT & hardening | process scripts, accessibility, load, security, training | signed UAT and cutover checklist |
| G7 | Controlled go-live | cutover, smoke test, monitoring, recovery ready | business go/no-go authorization |
| G8 | Hypercare & handover | issue register, support runbook, knowledge transfer | operational ownership acceptance |

### 3.2 Backlog and traceability

Every backlog item MUST link: **Business process -> requirement -> domain entity/field -> API/service -> UI -> workflow/permissions -> reports -> tests -> release -> sign-off**. Use unique IDs, e.g. `SLS-REQ-014`, `INV-ENTITY-003`, `FIN-TEST-051`; never rely on prose alone.

For each iteration: select the smallest working vertical slice, write acceptance tests, implement through domain logic and transaction boundaries, validate role and negative scenarios, demo with realistic *synthetic* fixtures, update docs, and only then mark complete. Separate discovery, implementation, review and release branches/steps where practical.

### 3.3 Definition of Ready (DoR)

A story is ready only with validated intent, owner, priority, role, prerequisites, data and field definitions, business rules, full journey, happy/exception paths, linkages, financial/tax consequences, permissions, notifications, reports and testable acceptance criteria.

### 3.4 Definition of Done (DoD)

A feature is done only if code is reviewed, migrations are safe, unit/integration/E2E and role tests pass, transaction invariants hold, audit logging works, list/form/report views are usable, errors and empty states are handled, analytics reconcile, accessibility checks pass, documentation is updated and the business owner has accepted it. **A rendered screen, demo, green unit suite alone, or generated code is not completion.**

### 3.5 Engineering controls

Require issue-linked branches, code review, automated checks, dependency scanning, migration reviews, release tags, changelogs and production deployment approvals. Keep development, test/UAT and production environments separated. Do not store production secrets or unmasked personal data in the repository or AI prompts.

---

## 4. Product architecture and design principles

### 4.1 Logical layers

1. **Experience layer:** desktop/mobile responsive screens, field service/mobile workflows, portal, optional POS and e-commerce.
2. **Application layer:** commands, validations, workflows, orchestration, permissions and explicit use cases.
3. **Domain layer:** sales, procurement, stock, accounting, HR, projects, maintenance and industry-specific rules.
4. **Persistence layer:** canonical entities, revisions, transactions, event/outbox store, audit and attachments.
5. **Integration layer:** APIs, events, webhooks, ETL, import/export and external adapters.
6. **Intelligence layer:** dashboards, semantic KPI definitions, alerts, recommendations and restricted AI tools.
7. **Platform layer:** identity, policy, localization, notifications, logging, background jobs, health checks, backup and deployment.

A custom ERP SHOULD begin as a modular monolith with bounded contexts and an internal event bus/outbox where needed. Extract services only with measured justification. Each module owns its rules and data contracts; other modules reference documented interfaces and identifiers rather than directly changing foreign state.

### 4.2 Architectural invariants

- One authoritative owner per business fact: customer, price rule, stock quantity, valuation, receivable balance, posted ledger entry, employee record, etc.
- Every legal entity has explicit ownership and transaction context. **Never infer company from a display name** or mix two companies in a financial document.
- Financial documents and stock/ledger changes are generated by authorized business events and validated posting services, not direct UI database writes.
- Every link must declare cardinality, ownership, cascade/delete behavior, uniqueness, state constraints and cross-company restrictions.
- Monetary calculations use fixed-point decimal and documented currency rounding; no binary floating-point for financial totals.
- Save source rate, rate timestamp, transaction currency, company currency and conversion result when applicable.
- Dates/times are timezone-aware; store instants consistently and format according to user locale; distinguish dates from timestamps.
- Mutable drafts may be edited; approved/posted records follow controlled correction/reversal policies. Never erase fiscal history to make a report look correct.
- Background jobs and inbound integrations must be idempotent and retry-safe.
- Reports must derive from authoritative transactions with explicit time, company, currency and state filters.
- The database and API must enforce required constraints independently of browser validation.

### 4.3 Multi-tenancy / group structures

Clarify these distinct scopes: **tenant/customer organization**, **legal company**, **business unit/brand**, **branch**, **department**, **project**, **warehouse**, **location**, **cost center** and **analytic dimension**. They must not be interchangeable fields. For group shared-services models, implement service-owning cost centers and documented allocations/recharge policies; do not disguise cross-company postings as internal departmental moves.

Data scope policy:
- **Global platform reference:** ISO countries, languages, generic UoM definitions; non-sensitive standardized reference data.
- **Tenant scope:** identities, preferences, organization profile and subscription rights where SaaS.
- **Company scope:** chart of accounts, transactions, tax accounts, fiscal configuration, employees and statutory reports; sharing requires explicit rules.
- **Shared master:** partners/items may be shared across companies only if platform supports it safely and company-specific properties are separated.
- **Branch/project scope:** operational dimension under a company, not a legal company by default.

### 4.4 Domain communication

Use commands for requests (`ConfirmSalesOrder`) and domain events for observed outcomes (`SalesOrderConfirmed`). Use a transactional outbox when an event must not be lost across a database commit. Consumers must deduplicate with idempotency keys and support dead-letter/error inspection. Define contract versioning, retries with backoff, replays, monitoring and manual recovery.

---

## 5. Canonical module and dependency registry

**Classification:** `CORE` = normally required at foundation; `COMMON` = frequently required based on scope; `OPTIONAL` = only when the industry demands it. Dependency arrows indicate the primary domains required, not necessarily one technical module per row.

| ID | Capability | Classification | Core entities | Major dependencies and cross-links |
|---|---|---|---|---|
| PLT-01 | Tenant, company and organizational structure | CORE | Tenant, Company, Branch, Department, CostCenter | security, accounting, all transactions |
| PLT-02 | Identity, roles, approvals and delegation | CORE | User, Role, Policy, ApprovalRequest, Delegation | all state-changing modules |
| PLT-03 | Shared contacts and counterparties | CORE | Party, Organization, Person, Address, BankAccount | CRM, Sales, Purchase, Finance, HR |
| PLT-04 | Item/service catalog and configuration | CORE | Item, SKU, Variant, UoM, Category, Pricelist | Sales, Purchase, Inventory, MRP, POS |
| PLT-05 | Currency, tax, fiscal periods and localization | CORE | Currency, FXRate, TaxRule, FiscalPeriod | Sales, Purchase, Payroll, Accounting |
| PLT-06 | Documents, attachments, messaging and audit | CORE | Attachment, Activity, AuditEvent, Note | all modules |
| PLT-07 | Workflow, jobs, notification and integration | CORE | Workflow, Rule, Job, Webhook, Mapping | all transactional modules |
| PLT-08 | Data governance, import and reference codes | CORE | ImportBatch, ExternalIdentity, Sequence | migration, integration, all modules |
| CRM-01 | Leads, opportunities, activities, campaigns | COMMON | Lead, Opportunity, ContactActivity, Campaign | Party -> Quotation -> Order |
| SLS-01 | Quotation, pricing and sales orders | COMMON | Quote, SalesOrder, SalesOrderLine, Discount | Customer, Item, Tax, Credit, Inventory |
| SLS-02 | Contracts, recurring billing, subscriptions | OPTIONAL | Contract, Schedule, Renewal, Amendment | Sales, Service, AR, Projects |
| SLS-03 | Returns, rebates, customer service | COMMON | RMA, ReturnLine, CreditNoteRequest | Sales, Inventory, AR, Payment |
| PUR-01 | Requisition, RFQ, supplier quotes, PO | COMMON | PR, RFQ, Bid, PurchaseOrder, POLine | Vendor, Item, Budget, Approval |
| PUR-02 | Supplier invoices and settlement | COMMON | VendorBill, ThreeWayMatch, SupplierPayment | Receipt, AP, Tax, GL |
| INV-01 | Warehouses and inventory movements | COMMON | Warehouse, Location, StockMove, Picking | Item, Sales, Purchase, Accounting |
| INV-02 | Lot/serial, reservations, replenishment | OPTIONAL | Lot, Serial, Reservation, ReorderRule | Inventory, MRP, Service, Sales |
| INV-03 | Stock valuation and landed costs | COMMON for stock | ValuationLayer, CostLayer, LandedCost | StockMove, GL, SupplierBill |
| FIN-01 | General ledger and financial controls | CORE if financial ERP | Account, Journal, JournalEntry, EntryLine | Tax, AP, AR, Asset, Payroll, Inventory |
| FIN-02 | AR, collections, customer invoicing | COMMON | Invoice, InvoiceLine, Receivable, Receipt | Sales, Contract, GL, Bank |
| FIN-03 | AP, bank and reconciliations | COMMON | Payable, BankStatement, Payment, Match | Purchase, Expense, GL |
| FIN-04 | Budgets, cash forecast, assets, reporting | OPTIONAL | Budget, BudgetLine, Asset, Depreciation | GL, Projects, Procurement |
| FIN-05 | Intercompany, consolidation and allocations | OPTIONAL | IntercompanyTransfer, Allocation, Elimination | multi-company GL, CostCenter |
| PRJ-01 | Projects, tasks, timesheets and budgets | OPTIONAL | Project, Task, TimeEntry, ProjectBudget | Sales, HR, Purchase, GL |
| SRV-01 | Helpdesk, field service, SLA | OPTIONAL | Ticket, ServiceOrder, SLA, Visit | Customer, Contract, Item, Inventory |
| SRV-02 | Equipment, maintenance and rental | OPTIONAL | AssetEquipment, MaintenancePlan, WorkOrder, RentalContract | Service, Inventory, Purchase, Cost |
| MFG-01 | BOM, production, routing, quality | OPTIONAL | BOM, WorkCenter, MfgOrder, QualityCheck | Item, Inventory, Purchase, GL |
| HRM-01 | Employees, attendance, leave, expenses | OPTIONAL | Employee, Attendance, Leave, Expense | Organization, Projects, Approval, AP |
| HRM-02 | Payroll, advances and obligations | OPTIONAL | PayRun, Payslip, Loan, Deduction | Employees, Localization, GL, Bank |
| OMC-01 | POS, e-commerce, customer/partner portals | OPTIONAL | Cart, WebOrder, POSSession, PortalUser | Price, Inventory, Sales, Payments |
| BI-01 | Reporting, analytics and command centers | COMMON | MetricDefinition, Dashboard, Alert | validated domain data/read models |
| AI-01 | Recommendations and governed AI agents | OPTIONAL | AgentAction, Proposal, Evaluation, Approval | APIs, Roles, Audit, BI |
| VRT-01 | Industry extensions | OPTIONAL | sector-specific models | approved dependencies only |

**Avoid over-customization:** If the platform already includes a capable standard module, extend and configure that module rather than recreating it. Each optional module must be installable/disabled without corrupting the base ERP. Dependency cycles are prohibited.

---

## 6. Cross-module process map and document linkages

For every process draw BPMN/flow and define event, source document, line-level link, status change, posting, exception, owner, reconciliation and analytics. Mandatory examples:

### 6.1 Lead-to-cash (L2C)

`Lead -> Opportunity -> Quotation -> Approval -> Sales Order -> Reservation/Delivery or Service Execution -> Customer Invoice -> Payment/Receipt -> Bank Reconciliation -> GL -> Revenue/Margin Report`

Required variants: partial delivery; multiple deliveries; down payment; partial invoice; split invoice; credit hold; customer cancellation; backorder; substitution; free-of-charge item; discount approval; tax exemption; return; refund; multi-currency settlement; warranty. Document flows must be many-to-many when business reality requires them; **do not force a one-order-one-invoice relationship**.

### 6.2 Procure-to-pay (P2P)

`Requisition -> Budget Check -> RFQ -> Vendor Bid/Comparison -> Approved PO -> Goods Receipt/Service Confirmation -> 2/3-Way Match -> Vendor Bill -> Payment -> Bank Reconciliation -> GL`

Variants: partial receipt, prepayment, under/over delivery tolerance, supplier return, replacement, landed cost, quality hold, price variance, debit note, multi-currency bill, non-PO expense, blanket PO. Define who can approve exceptions.

### 6.3 Inventory-to-finance

`Source Demand -> Reservation -> Picking -> Stock Move -> Lot/Serial Trace -> Stock Balance -> Valuation Layer -> Accounting Entries -> Inventory/COGS/GRNI Reconciliation`

Every stock-affecting action must have a documented physical effect, valuation effect, location, item, UoM and ownership. Transfers within a company are not sales; stock movement is not automatically a financial posting in every costing configuration. Inventory counts produce controlled adjustment requests with approval and audit trail.

### 6.4 Record-to-report

`Subledgers + Journals -> GL -> Trial Balance -> Tax Reports -> Period Close -> Balance Sheet / P&L / Cash Flow -> Consolidation (where applicable)`

Keep subledgers reconciled to control accounts; enforce balanced entries, fiscal lock dates, permissions, reversal method, tax reporting, exchange gains/losses, rounding, audit evidence and retained versions. No module may create fictitious balancing lines to mask a mismatch.

### 6.5 Project/service-to-cash

`Signed Contract -> Project/Service Order -> Budget/Resource Plan -> Time/Material/Expense -> Approval -> Customer Billing -> Collection -> Project Profitability`

Variants: fixed-price, T&M, retention, milestones, variation orders, field expenses, material issue/return, subcontractors, WIP, preventive maintenance, equipment depreciation/allocation and SLA penalties where applicable.

### 6.6 HR-to-finance

`Employee Master -> Contract/Attendance/Leave/Advance -> Approved Payroll Inputs -> Payroll Calculation -> Review -> Posting/Payable -> Disbursement -> GL/Cost Allocation`

Country-localized payroll rules must be approved by qualified local experts; the engine must show calculation provenance and never silently overwrite finalized payslips.

### 6.7 Intercompany / shared services

`Service Request -> Shared Team Time/Expense -> Cost Pool -> Allocation Rule -> Approved Charge/Recharge -> Intercompany Mirror Entries -> Reconciliation -> Group Reporting`

Allocation bases (usage, headcount, revenue, fixed share) must be versioned, effective-dated and auditable. Intercompany entities must agree on currencies and matching references, and consolidation eliminations must be traceable.

---

## 7. Data architecture, attributes and relationships

### 7.1 Universal entity contract

Every persisted business entity SHOULD document the fields below; not every table must physically duplicate them if provided by framework conventions.

| Field / concept | Type / control | Purpose |
|---|---|---|
| `id` | stable opaque identifier | internal identity, never business name |
| `tenant_id` | scoped foreign key, only for shared-tenant architecture | hard tenant isolation |
| `company_id` | scoped FK | legal-entity ownership |
| `branch_id`, `department_id` | optional FKs | organizational routing |
| `code`, `sequence` | unique within defined scope | readable document number |
| `status`, `substatus` | controlled enum/state machine | workflow validity |
| `document_date`, `effective_date` | date | business/accounting timing |
| `created_at`, `updated_at` | UTC instants | provenance and lifecycle |
| `created_by`, `updated_by` | actor FKs | audit responsibility |
| `owner_id`, `assigned_to_id` | actor FKs | operational accountability |
| `version` | monotonic number / revision | concurrency and controlled changes |
| `currency_id`, `exchange_rate_id` | FK | monetary context where applicable |
| `source_system`, `source_record_id` | immutable external identity | migration and idempotent sync |
| `origin_ref`, `external_ref` | structured reference | document linkage |
| `approval_state`, `approved_by`, `approved_at` | workflow + audit | control evidence |
| `active`/`archived_at` | retention governed | logical archival, not fiscal deletion |
| `notes`, `tags`, `attachments` | scoped relations | collaboration and evidence |
| `analytic_distribution` | structured controlled dimensions | cost/project reporting where applicable |

Additional metadata: legal data classification (public/internal/confidential/restricted), data owner, retention schedule, allowable export roles, and change history requirements. A posted ledger must be treated differently from an editable customer contact.

### 7.2 Core entity dictionary: mandatory illustrative attributes

**Party / customer / vendor:** `party_id`, `party_type`, `legal_name`, `display_name`, `tax_registration`, `registration_country`, `contact_person_ids`, `billing_address_id`, `delivery_address_ids`, `phone`, `email`, `payment_terms_id`, `credit_limit`, `price_list_id`, `account_receivable_id`, `account_payable_id`, `bank_account_ids`, `fiscal_position_id`, `active`, `company_scope`, `risk_flag`, `consent_preferences`. Differentiate a legal party from individual contacts and multiple roles; a party may be customer *and* vendor.

**Item / SKU:** `item_id`, `sku`, `name`, `category`, `product_type` (stock/service/consumable/etc), `variant_attributes`, `base_uom_id`, `purchase_uom_id`, `uom_conversion`, `sales_price`, `purchase_cost`, `pricing_rule_id`, `tax_ids`, `barcode`, `tracking` (none/lot/serial), `valuation_method`, `costing_method`, `income_account_id`, `expense_account_id`, `inventory_account_id`, `reorder_rule_ids`, `lead_time`, `warranty`, `status`. Item global attributes and company-dependent accounts/pricing require separate ownership rules.

**Sales order header:** `sales_order_id`, `order_number`, `company_id`, `customer_id`, `invoice_partner_id`, `shipping_partner_id`, `opportunity_id`, `quotation_id`, `customer_po_ref`, `order_date`, `valid_until`, `currency_id`, `exchange_rate_context`, `price_list_id`, `payment_terms_id`, `delivery_terms`, `warehouse_id`, `salesperson_id`, `team_id`, `status`, `credit_check_status`, `approval_id`, `untaxed_amount`, `tax_amount`, `total_amount`, `invoiced_amount`, `delivered_amount`, `balance_amount`, `invoice_status`, `delivery_status`, `revision`, `origin_refs`.

**Sales order line:** `line_id`, `order_id`, `line_no`, `item_id`, `variant_id`, `description`, `uom_id`, `ordered_qty`, `reserved_qty`, `delivered_qty`, `invoiced_qty`, `returned_qty`, `unit_price`, `discount_type`, `discount_value`, `tax_ids`, `subtotal`, `tax_total`, `total`, `cost_snapshot`, `required_date`, `analytic_distribution`, `linked_delivery_line_ids`, `linked_invoice_line_ids`, `cancellation_reason`. Define quantity rounding, negative/zero conditions and discount stacking policy.

**Purchase order header/line:** header stores supplier, company, supplier reference, currency, date, expected delivery, Incoterm, payment terms, approval, warehouse, tax and totals. Lines store item/service, UoM, ordered/received/billed/returned quantities, price, discount, taxes, landed cost allocation, cost center/project, linked receipt and bill lines.

**Stock move / lot / reservation:** `move_id`, `company_id`, `item_id`, `source_location_id`, `destination_location_id`, `uom_id`, `requested_qty`, `done_qty`, `reserved_qty`, `lot_id/serial_id`, `owner_id` (consignment), `date`, `status`, `origin_document_line_id`, `picking_id`, `valuation_layer_ids`, `reason_code`, `created_by`, `posted_by`. Invariants must prevent negative reserved quantities, duplicate serial consumption and unsupported cross-company movements.

**Invoice header:** `invoice_id`, `invoice_number`, `company_id`, `customer_or_vendor_id`, `invoice_type`, `invoice_date`, `due_date`, `posting_date`, `currency_id`, `exchange_rate`, `journal_id`, `tax_profile_id`, `status`, `approval`, `untaxed_amount`, `tax_amount`, `total_amount`, `residual_amount`, `payment_state`, `source_order_ids`, `accounting_entry_id`, `fiscal_reference`, `correction_of_id`, `reversal_id`. A single invoice may contain lines from multiple approved orders when business policy permits; keep the line-level origins.

**Invoice line:** `line_id`, `invoice_id`, `source_order_line_id`, `item_or_service_id`, `description`, `quantity`, `uom_id`, `unit_price`, `discount`, `tax_ids`, `subtotal`, `total`, `account_id`, `analytic_distribution`, `revenue_recognition_context`. A source order line may feed multiple invoice lines, and one invoice line may require a link table when consolidation is allowed.

**Journal entry/line:** header stores company, journal, reference, accounting date, state, source document and posting actor. Lines store account, partner, description, debit, credit, currency, foreign amount, tax tags, analytic distribution, maturity date and reconciliation links. Invariant: per-posted-entry company-currency debits equal credits with approved rounding rules; never mutate posted history outside an authorized correction process.

**Payment / allocation:** `payment_id`, `company_id`, `party_id`, `payment_method`, `journal/bank_account`, `date`, `amount`, `currency`, `fx_rate`, `status`, `reference`, `settlement_id`, `allocation_lines`, `reconciliation_ids`. Many payments can settle many invoices through allocation lines; support partial and overpayments according to policy.

**Project and cost dimensions:** `project_id`, `contract_id`, `customer_id`, `company_id`, `project_manager_id`, `budget_version`, `start/end dates`, `task_ids`, `cost_center`, `billing_model`, `milestones`, `approved_variations`, `committed_cost`, `actual_cost`, `recognized_revenue`, `unbilled_amount`, `forecast_margin`.

**Equipment asset:** `equipment_id`, `asset_tag`, `model`, `serial_no`, `owner_company_id`, `current_location_id`, `assigned_operator_id`, `purchase_date`, `warranty_end`, `maintenance_policy`, `service_interval`, `last_service`, `next_due`, `service_documents`, `odometer/hours`, `cost_ledger`, `status`; support near-expiry alerts (e.g., configurable seven-day warning) and document attachments.

**Audit event:** `actor`, `tenant`, `company`, `object_type`, `object_id`, `action`, `timestamp`, `old/new state hashes or redacted diffs`, `reason`, `approval_ref`, `source`, `correlation_id`, `result`, `IP/session metadata as permitted`. Retention/immutability policy must be specified, with sensitive values redacted.

### 7.3 Relationship catalog: cardinality and integrity

| Parent -> child | Cardinality / rule | Invariant |
|---|---|---|
| Company -> Branch | 1:N | every branch belongs to exactly one legal company |
| Party -> Contact/Address | 1:N | address roles controlled; no accidental merges |
| Opportunity -> Quote | 1:N | versioned quote history |
| Quote -> Sales Order | 0..N according to policy | approval/conversion traced; never reuse number as identity |
| Sales Order -> Order Line | 1:N | no confirmed order with invalid lines |
| Order Line <-> Delivery Move | M:N via fulfillment allocations | shipped quantities traceable; returns separate |
| Order Line <-> Invoice Line | M:N via billing allocations | quantities billed correctly even with split/consolidation |
| Purchase Order Line <-> Receipt/Bill Line | M:N via allocation | match tolerances explicit |
| Stock Move -> Valuation Layer | 1:N | valuations reconcile to configured GL control accounts |
| Invoice <-> Payment | M:N via settlement allocations | residual and FX differences are accounted for |
| Journal Entry -> Journal Lines | 1:N | company balanced; posted records controlled |
| Equipment -> Work Order | 1:N | full lifecycle costs and service history |
| Project -> Task/TimeEntry/Expense | 1:N | resources and financial dimensions mapped |
| Integration source -> target | 1:1 or 1:N mapping explicitly defined | stable external IDs, idempotency, no duplicate import |

Enforce company consistency, foreign keys, reference uniqueness, document revision and allowed state transitions on the server. Model delete policy (restrict, archive, reverse or cascade) per relationship; **never cascade-delete posted fiscal or inventory history**.

### 7.4 Data dictionary specification

Every field in production must be recorded with: `domain`, `entity`, `technical_name`, `label`, `data_type`, `max_length/precision`, `required`, `default`, `unique_scope`, `reference_model`, `cardinality`, `compute_rule`, `validation`, `editable_states`, `security_class`, `role_visibility`, `company_scope`, `searchable`, `index_policy`, `external_mapping`, `audit_policy`, `source_of_truth`, `API_contract`, `UI_screen`, `report_usage`, `test_ID`. See the included CSV template.

---

## 8. Transactions, state machines, validations and exceptions

Every transaction module MUST define:

1. **Trigger:** creation, import, API event, schedule, user action.
2. **Roles:** creator, editor, reviewer, approver, executor, auditor.
3. **States:** draft -> submitted -> approved -> confirmed/posted -> fulfilled/settled -> closed; include refused, canceled, reversed and exception where relevant.
4. **Transition guards:** required fields, stock, period locks, budget, credit, vendor compliance, duplicate detection, tax, SoD, permissions.
5. **Effects:** stock, reservation, GL, AR/AP, project costs, notifications, external events and KPIs.
6. **Compensation:** reversal, cancel, credit note, return, reassign, rollback or escalation as appropriate.
7. **Concurrency:** optimistic lock/version check or transactional serialization on state changes.
8. **Audit:** actor, time, reason, approver and before/after state.
9. **Idempotency:** safe retries and duplicate-submit protection.
10. **Tests:** positive, negative, boundary, concurrency and cross-company paths.

**Examples of mandatory invariants:**

- Posted journal entry totals balance by legal company and currency treatment.
- Invoice residual = original amount + approved adjustments - applied settlements, after controlled currency/rounding treatment.
- Delivered-to-date and invoiced-to-date never exceed allowable contract/order policy without documented over-tolerance approval.
- Stock on hand = validated opening + internal/receipt/inbound - issue/outbound +/- authorized adjustments at the chosen cut-off and location hierarchy.
- Available to promise = on-hand + permitted inbound - reservations - blocked/quality quantities, under a documented definition.
- All transactional references must belong to the authorized company unless a controlled intercompany process applies.
- A change in a draft does not silently alter an already approved or posted downstream document.

**Exception design is required, not optional:** duplicate vendor invoice, concurrent reservation, insufficient stock, tax mismatch, disconnected mobile client, integration timeout, supplier under-delivery, canceled order after delivery, exchange-rate variance, supplier credit note, missing employee contract, missing role permission, period closed, orphan documents.

---

## 9. Accounting and financial correctness standard

A financial ERP MUST explicitly document the chart of accounts, journals, posting rules, control accounts, tax rules, currency policies, fiscal calendar, analytic dimensions, bank rules, revenue/expense recognition policy, rounding and reconciliation rules. Where statutory accounting treatment is uncertain, require accountant approval instead of inventing logic.

**Controlled financial patterns:**

- Post from governed domain transactions with an auditable source document and stable linkage.
- Validate balancing, accounts, company, journal, reporting tags, taxes, periods and rights on the server.
- Reconcile AR to customer invoices/credits/payments, AP to bills/credits/payments, bank to statements, inventory value to stock valuation records and opening balances to signed migration controls.
- Support partial reconciliation, write-offs within approval thresholds, FX differences and reversal chains.
- Use locked periods, immutable document numbering where legally required, approval logs and tax evidence.
- Never create a fake invoice or order to compensate for missing migration records. Keep a difference register and resolve provenance before posting.

**CFO reporting:** trial balance, P&L, balance sheet, cash flow, AR/AP age, bank reconciliation exceptions, tax position, gross margin, inventory valuation, budget variance and intercompany mismatch. Every number must drill down to accountable records.

---

## 10. Permissions, security, privacy and control model

Baseline design against **OWASP ASVS 5.0.0** application control requirements and integrate the **NIST Secure Software Development Framework** into delivery. These are baselines, not guarantees of regulatory certification. Local legal review is required for data protection, payroll, tax and invoicing obligations.

### 10.1 Access rules

- Enforce server-side RBAC, company/tenant scope and optional attribute-based conditions; UI hiding alone is not security.
- Default deny for sensitive models and actions; least privilege; MFA for privileged operations where supported.
- Segregate requester, approver, payer, invoice poster, inventory adjuster and system administrator appropriately; no silent self-approval.
- Implement field-level restrictions for salary, bank account, cost, margin, confidential clients, credential references and other restricted data.
- Use scoped delegated access with start/end date, reason and audit.
- Every automation/agent acts under a named scoped service identity; do not use broad admin access by convenience.
- Protect import/export, mass update, attachment download, API tokens, file processing and report endpoints.
- Test horizontal/vertical privilege escalation and cross-tenant/cross-company leaks.

### 10.2 Security engineering

Threat-model sensitive flows, validate input at trust boundaries, use parameterized queries/framework ORM, secure session/CSRF controls, hardened upload/storage, secret management, encryption in transit/at rest as appropriate, dependency/SBOM and vulnerability checks, rate limiting, log redaction, recovery drills and incident response. Maintain backups with restore testing. Do not put credentials or private customer records in commits, fixtures, logs, demonstrations or AI chats.

### 10.3 Example access matrix

| Action | Sales rep | Sales mgr | Warehouse | Accountant | Finance controller | Auditor |
|---|---|---|---|---|---|---|
| Create quote | Own/team | Yes | No | No | No | Read |
| Approve excessive discount | No | Subject to threshold | No | No | Higher threshold | Read |
| Confirm shipping | No | Read | Authorized | No | No | Read |
| Post customer invoice | No | No | No | Authorized | Authorized | Read |
| Approve write-off | No | No | No | Within policy only | Higher threshold | Read |
| Adjust stock | Request only | No | Request/authorized | No | Independent approval as designed | Read |
| Change fiscal lock | No | No | No | No | Authorized + log | Read |
| Manage role grants | No | No | No | No | Separate security admin | Review |

This is a proposed model; adapt to organization size and signed authorization matrix. Verify that an admin/support role does not bypass cross-company boundaries inadvertently.

---

## 11. User experience and enterprise design system

Build a **clean, modern, high-trust enterprise experience**: visually engaging yet operationally calm. Accessibility, dense-data readability and fast task completion take priority over decorative animation. Adopt a consistent information architecture and design tokens.

### 11.1 Universal screen anatomy

- Global navigation: switch authorized company/branch, search, favorites, notifications, help and user context.
- Role home: urgent work, KPIs with definitions, approvals, exceptions, recent transactions, shortcuts.
- List view: server-side filters/search/sort, saved views, column personalization, bulk actions with role checks, clear status chips, export control, pagination and empty states.
- Form: identifying header, document state, approval route, primary action(s), grouped tabs, dependent information, source/target documents, activity timeline, attachment zone and audit trail.
- Financial detail: explainable totals, tax breakdown, amounts in original/base currency and posting status.
- Exception-first flows: user-friendly specific errors, recoverable drafts and guided resolution.
- Inline context: one-click drill-down from a KPI to records behind its value; avoid magic totals.

### 11.2 Usability controls

Design for desktop and tablet/mobile roles; keyboard navigation; screen readers and WCAG 2.2 AA as an intended accessibility benchmark; readable typography and tables; clear validation and loading indicators; Arabic/RTL and English where needed; locale-aware currency, dates and numeric formats; quick creation with progressively revealed advanced fields; undo only where business policy permits; helpful defaults, not hidden automatic postings.

### 11.3 Executive command center

Design role dashboards (Group Owner, CEO, CFO, Sales, Operations, Procurement, Project, Service and HR) using data with lineage. Include current period, company filter, cross-company view permissions, trend, actual vs target, drill-through and **exceptions needing action**. Candidate widgets: revenue and gross margin; cash/AR/AP; conversion and pipeline; procurement commitments; stockout/aging; project actual vs budget; equipment costs and upcoming maintenance; outstanding approvals; intercompany imbalances; system/data health. Group totals must state whether eliminations/conversions are applied.

---

## 12. AI agents, predictive capabilities and safe automations

AI is a **separate governed layer**, never the source of truth. Classify each action:

- **Read only:** answer questions, retrieve a report, summarize a client history.
- **Recommend:** product suggestions, expected delay, customer follow-up or anomaly flags with reason and supporting records.
- **Draft:** prepare quotation, email, purchase request or journal proposal for human validation.
- **Act with approval:** create/modify transactions only after explicit role/threshold authorization, with full provenance.
- **Prohibited by default:** unapproved payments, posted financial adjustments, destructive migration, changing permissions, mass confidential exports or publishing confidential data.

Agent design must specify: permitted tools/data, identity, user delegation, prompt-injection controls, grounding, confidence/uncertainty, sources, tenant/company boundary, approval workflow, action dry-run, audit logging, rate and spend limits, retries, evaluation corpus, failure mode, rollback and kill switch. AI outputs are untrusted until checked against deterministic business rules. Never allow an LLM to bypass posting constraints.

Suggested safe examples: CRM next-best-action, invoice anomaly queue, accounts-receivable collector drafts, stock replenishment recommendations, maintenance reminders, project variance narrative, owner daily briefing, product affinity with consent controls, and approval routing suggestions.

---

## 13. Integration/API/messaging standard

Register every integration with **owner, source of truth, objects/fields, direction, schedule/trigger, authentication, mapping, identifiers, pagination, upsert policy, idempotency, transformations, constraints, rate limits, retries, failure queue, monitoring, test harness and recovery procedure**.

Core integration categories: e-commerce, POS, bank statements/payment providers, government invoicing/tax gateways, HR attendance, logistics/shipping, mobile/field apps, CRM/communications, document storage/identity, BI and third-party accounting/legacy systems. Local government interfaces depend on current country requirements and must be verified at implementation time.

**API style:** explicit resource ownership; versioned endpoints/contracts; tenant/company authorization on every request; request/correlation IDs; safe pagination, filters, validation, rate limiting and stable error codes. Public consumers should not access internal database tables. Define real-time vs batch consistency expectations.

**Integration guarantees:** do not claim exactly-once end-to-end delivery without qualifying infrastructure; implement at-least-once-safe handling with idempotent consumers or other explicitly tested guarantees. Monitor lag, retries, duplicates, poison messages and unreconciled documents.

---

## 14. Migration, source-to-destination mapping and reconciliation

For existing ERP or Odoo-to-Odoo migrations, perform **source audit -> target model map -> extract -> transform -> stage -> validate -> load -> reconcile -> approve -> cutover**. The job is not complete merely because source counts match target counts.

### 14.1 Mandatory migration controls

1. Inventory all source tables/models and field semantics, including custom modules and inactive/canceled records.
2. Agree history window, cutover date, open balances, open quantities, fully/partially fulfilled order scope and statutory record retention.
3. Assign source-of-truth per object and stable external identities (`source_instance`, `model`, `source_id`) to avoid duplicates.
4. Build explicit partner, product, tax, account, unit, warehouse, journal, payment term, user, invoice, SO and stock-location mappings. **Do not match by number or name alone** where collisions are possible.
5. Preserve document lineage: order lines to deliveries and invoice lines; bills to receipts; payments to invoice allocations; journals to entries.
6. Import in dependency order; use idempotent upserts, transaction batching, checkpoints and restartability.
7. Validate uniqueness, required fields, legal company, currency, tax and accounting-period constraints.
8. Reconcile by company, currency, period, status and document type; compare counts **and** values, tax, balances, open/residual amounts, delivered/invoiced quantities, stock and valuations.
9. Produce difference register with source ID, target ID, field, expected, actual, root cause, disposition and approver.
10. Dry-run in non-production with full rollback/cutover rehearsal, backups and formal go/no-go authority.

### 14.2 Example reconciliation matrix

| Object | Required comparisons |
|---|---|
| Customers/vendors | unique mapped parties, duplicate/merged contacts, tax IDs, payable/receivable settings |
| Sales orders | source/destination IDs, status, order/line counts, qty, delivered, billed, untaxed/tax/total, company, links |
| Customer invoices | invoice/credit note status, fiscal number, currency, taxes, balance, SO-line mapping, posting references |
| Vendor bills | supplier, PO/receipt link, currency, taxes, balance and payment allocation |
| Inventory | quantity per company/product/location/lot at cut-off; unit costs and total valuation |
| Accounting | opening TB, journal totals, AR/AP subledger, bank balances and retained fiscal references |
| Payments | receipt/payment count, amount, partner, related invoice allocations, reconciliation state |
| Attachments | document owner, checksum where possible, access scopes and retention |

**Prohibit silent destructive “cleanup”** of target records. Identify pre-existing partial migration; map and reconcile before creating missing records. For already-posted records, plan authorized corrections and ledger reconciliation instead of direct edits.

---

## 15. Test strategy and verification matrix

Tests are not optional deliverables. Use realistic synthetic fixtures for each role, company, country, currency, item class and business cycle.

### 15.1 Test layers

| Layer | Focus |
|---|---|
| Static/type/lint/security scanning | style, correctness, dependencies, secrets, vulnerable patterns |
| Unit | prices, tax, calculations, validation, states, quantities, permissions helpers |
| Contract | APIs, events, schemas, integration mapping, version compatibility |
| Integration | real database, cross-module effects, outbox, posting, concurrent actions |
| End-to-end process | CRM -> SO -> ship -> invoice -> payment -> GL; P2P; stock; payroll/project as scoped |
| Role/security | tenant/company isolation, unauthorized actions, private fields, exports, cross-role escalation |
| Reconciliation/property | mathematical invariants, subledgers, trial balance, unit conversions, valuation |
| Migration | repeatable import, mapping, restart, counts/totals, partial-history handling |
| Performance/reliability | agreed transaction volumes, imports, background lag, backup restore and fault injection |
| UAT | business-user scripts, evidence, owner sign-off, regressions |

### 15.2 Minimum process scenarios

- Sales: new/return customer, quotation revision, approval, partial delivery, partial invoice, down payment, cancellation, return, refund and payment allocation.
- Purchase: RFQ, quote compare, PO approval, partial receipt, price variance, 3-way match, supplier credit and settlement.
- Inventory: positive/negative adjustments within policy, cycle count, serialized movements, backorders, transfers and landed costs.
- Finance: period lock, balanced journals, FX, tax, credit note, bank reconciliation, AR/AP aging and cash vs accrual context.
- Security: two users of different companies request the same record ID; unauthorized approval/posting/export is rejected by the server.
- Integrations: duplicate webhook, timeout after commit, retry, replay, malformed payload and dead-letter recovery.
- UX: keyboard/RTL, mobile, empty/error states, inline validation and inaccessible actions.

### 15.3 QA evidence

For every release save test command/results, screenshots or recordings for critical process journeys, migration report, security findings, unresolved defects, known limitations, scope deviations and signed UAT. Do not report a test as passed unless it was actually executed. Never confuse mocked integration success with external-system completion.

---

## 16. DevOps, environments, performance, business continuity

Standard environments: **local/dev -> isolated CI -> staging/UAT -> production**. Separate secrets, data, storage, integration endpoints and user roles. Use infrastructure as code where suitable, repeatable deployment artifacts and a rollback strategy reviewed for both code and database schema changes.

- CI: format/lint, type/static checks, unit/integration tests, migration smoke, secrets/dependency scanning, build artifact.
- CD: promoted versioned artifacts, approvals for production, pre-deploy backup, schema compatibility, smoke tests, monitoring and rollback plan.
- Observability: structured logs, correlation IDs, metrics, traces, job queue health, business exception dashboard, audit access.
- Backups: full/incremental design, encryption and offsite policy, documented RPO/RTO, regular verified restores, attachment and database consistency.
- Reliability: timeouts, retry backoff, concurrency protection, fail-safe approvals, disaster recovery, operational escalation.
- Performance: load-test with realistic master/transaction volumes, actual roles and reports; index proven queries; avoid unbounded list pulls, N+1 reads, blocking UI waits and simultaneous expensive dashboard queries.
- Data retention: jurisdiction-appropriate archival, export and deletion handling that never corrupts mandatory financial evidence.

---

## 17. Odoo-specific implementation path (only if Odoo chosen)

**Standard-first priority:** standard module -> configuration -> supported integration -> small composable custom add-on -> broader customization only after a signed gap justification. Do not fork Odoo core or duplicate existing business workflows for visual preference.

### 17.1 Odoo framework discipline

- Inspect actual server version, edition, installed modules, dependencies, localization, customization and database before coding.
- Use `__manifest__.py` with correct `depends`, `data`, `demo`, license and version metadata; compose optional integration modules rather than hard coupling unrelated apps.
- Extend native models via supported `_inherit` or new models only when needed; preserve upgrade compatibility and access APIs through ORM.
- Use Odoo `res.groups`, `ir.model.access`, record rules and field groups; test as each intended role and company. Don't assume hiding a menu prevents model access.
- Respect company-dependent values and multi-company consistency checks; audit usage of `sudo()` and `with_company()` for accidental data leaks.
- Define business constraints and computed field dependencies using documented ORM mechanisms; do not use direct SQL to circumvent validation or security.
- Prefer native list/form/search actions, OWL for justified UI extensions, QWeb for suitable reports and supported assets APIs.
- Preserve native invoice, stock valuation, payment and ledger mechanisms. Custom dashboards should read from approved models/read models, not change accounting semantics.
- Automated tests: Python module tests, JavaScript/UI tests and Odoo tours where appropriate, plus installed-module and upgrade tests using a test database.
- Maintain independent custom add-ons with declared dependencies, sample data, access controls and update scripts. Test installation, upgrade and uninstall/disable impacts where relevant.

### 17.2 Odoo-specific blockers

Do not proceed when: Odoo major version is unknown; an add-on conflicts with an installed standard module; the source/destination model map lacks IDs; record rules leak company data; posting logic would bypass native accounting; migration attempts to write to posted fiscal documents outside supported behavior; required company/localization rules are unverified.

Official framework references should be checked against the target installation:
- Odoo 19 module manifests: https://www.odoo.com/documentation/19.0/developer/reference/backend/module.html
- Odoo 19 ORM: https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html
- Odoo 19 security: https://www.odoo.com/documentation/19.0/developer/reference/backend/security.html
- Odoo 19 multi-company: https://www.odoo.com/documentation/19.0/developer/howtos/company.html
- Odoo 19 testing: https://www.odoo.com/documentation/19.0/developer/reference/backend/testing.html

---

## 18. Industry solution packs: enable only after sector fit-gap

| Segment | Additional processes and models | Critical cross-links |
|---|---|---|
| Retail / omnichannel | POS, e-commerce, returns, loyalty, promotions, stock sync | sales, payment, inventory, tax, CRM |
| Wholesale / trading | customer pricing, purchase commitments, trade terms, credit, freight | sales, purchase, landed cost, multi-currency, AR/AP |
| Automotive spare parts | fitment catalog, OEM/cross-reference, alternate SKUs, VIN compatibility | item variants, inventory, purchase, sales, returns |
| Construction / EPC / fit-out | BOQ, estimate, WBS, subcontract, variation, retention, progress claims, WIP | project, purchase, inventory, timesheet, GL, AR/AP |
| Equipment rental / maintenance | fleet, dispatch, operator, usage meter, preventive alerts, breakdown cost ledger | equipment, HR, purchase, inventory, customer invoice |
| Property / real estate | units, owners, tenants, leases, billing, service charges, collections | contract, AR, asset, maintenance, reporting |
| Manufacturing | BOM, routing, shop floor, quality, scrap, traceability, MRP | inventory, purchasing, costing, finance |
| Jewellery | metal rate approvals, purity/karat/weights, stone attributes, old-gold exchange, VIP client tier | item, pricing, approvals, POS, CRM, valuation |
| Professional services | proposals, project staffing, timesheets, retainer, milestones, expenses | CRM, contracts, project, HR, billing |
| HR-intensive operations | sponsored/contract staff, advances, allowances, food/accommodation, labor costing | payroll, time, project, cash, accounting |

Industry configurations must define their **own field dictionary, roles, accounting implications, operational events, approval controls and UAT scenarios**. A vertical extension must not rewrite shared core logic unless required through a documented contract.

---

## 19. Suggested rollout sequence (dependency-based, not calendar promises)

**Wave 0 — Audit and design:** repository assessment, current data, desired state, fit-gap, charter, architecture, authorization matrix, migration inventory.

**Wave 1 — Platform and master data:** tenant/company, roles, party/item, UoM, currency/tax, audit, attachments, approvals, integrations, UI shell, observability, baseline CI.

**Wave 2 — End-to-end financial and commercial spine:** chart of accounts and close controls, quote/order, purchasing, inventory or service delivery, invoicing, receipts/payments, subledgers, reconciliations. Choose a reference transaction to prove entire flow.

**Wave 3 — Operations and industry:** projects, field service, rental, manufacturing, HR, e-commerce, specialty vertical packs, company allocations as genuinely required.

**Wave 4 — Analytics and intelligence:** validated executive dashboards, metric lineage, approval cards, alerts, AI read-only and proposal agents, then gradually governed action agents.

**Wave 5 — Migration, training and go-live:** production data dry runs, reconciliation sign-offs, business UAT, cutover, parallel run if appropriate, monitored launch, hypercare and handover.

Every wave must include regression testing of all earlier cycles, role tests, migration implications and a go/no-go decision. Avoid arbitrary percentage-complete claims. Track demonstrable transactions and signed acceptance.

---

## 20. Technical delivery file system and documentation contract

Recommended project structure (adapt to the chosen stack):

```text
project-root/
  CLAUDE.md                       # short always-on rules for Claude Code
  .claude/                        # optional path-scoped rules, skills, agents and hooks
  docs/
    ERP_MASTER_BLUEPRINT.md       # this source of architecture standards
    project/
      PROJECT_CHARTER.md
      REQUIREMENTS_REGISTER.md
      FIT_GAP_REGISTER.md
      DECISION_REGISTER.md
      TRACEABILITY_MATRIX.md
    architecture/
      CONTEXT_DIAGRAM.md
      MODULE_DEPENDENCY_MAP.md
      DATA_DICTIONARY.csv
      ENTITY_RELATIONSHIPS.md
      INTEGRATION_REGISTER.md
      SECURITY_MATRIX.md
      ACCOUNTING_POSTING_RULES.md
      BPMN_OR_PROCESS_FLOWS.md
    modules/
      MODULE_SPEC_<ID>.md
    quality/
      TEST_MATRIX.md
      MIGRATION_RECONCILIATION.md
      UAT_SIGNOFF.md
    operations/
      DEPLOYMENT_RUNBOOK.md
      RECOVERY_AND_BACKUP.md
      RELEASE_CHANGELOG.md
  src/ or addons/                  # depends on custom ERP or Odoo architecture
  tests/
  scripts/
```

Keep `CLAUDE.md` concise (ideally well under 200 lines); move bulky business specifications into versioned docs and path-scoped rules/skills. Claude must inspect the relevant files at the beginning of each task rather than trust conversational memory.

### 20.1 Required document templates

1. **Module specification:** mission, owner, scope, dependencies, process, user stories, entities/attributes, screens, states, validations, permissions, accounting effects, integrations, alerts, reports, exceptions, test matrix and acceptance.
2. **Data dictionary:** field-level type, source, scope, requiredness, validation, permissions, integration and tests.
3. **Process / integration contracts:** endpoints/events, schemas, source of truth, retry, idempotency and recovery.
4. **Security matrix:** roles x operations x company x sensitive fields.
5. **Posting catalog:** source event -> debit/credit accounts -> tax -> cash/AR/AP/stock/project effect -> reversal.
6. **Reconciliation register:** source ID, target ID, expected/actual/count/value, variance, root cause, sign-off.
7. **Test/UAT matrix:** requirement, actor, setup, steps, expected, observed, evidence, status and approver.
8. **ADR / decision log:** choice, alternatives, cost, assumptions, rationale and impact.

---

## 21. Claude Code execution protocol

Claude Code MUST adopt these instructions for every task:

**Step A — Inspect.** Read `CLAUDE.md`, project charter, ADRs, matching module spec, current code, migrations, tests and configuration. Determine target platform/version, dependencies, ownership and already-built features. Never create a parallel duplicate without checking the current implementation.

**Step B — Map the impact.** List affected entities, existing transactions, source/target document links, state transitions, accounts, stock, permissions, integrations, reports and regression tests. Highlight destructive or irreversible risks.

**Step C — Plan the vertical slice.** Propose file-by-file change, DB/data migration, UI workflow, API/events, controls, test scenarios and rollback. Reuse existing patterns and standard modules. If requirements conflict, record a decision or explicitly block that part; do not invent policy.

**Step D — Implement safely.** Change the minimum coherent surface. Put rules server-side. Keep separate domain/application/UI layers. Protect tenant/company boundaries and idempotency. Generate fixtures with fake data; preserve backward compatibility unless migration approved.

**Step E — Validate.** Run feasible automated checks and targeted tests, including negative roles and end-to-end linkage. Capture exact commands and outputs. If a test cannot run, say **NOT RUN** and why; never state pass by assumption.

**Step F — Update evidence.** Update schema/data dictionary, requirements traceability, module documentation, changelog, tests and known limitations. Provide evidence of changed screens/routes/modules; distinguish simulated from real integrations.

**Step G — Report and request human gates.** Output: completed changes, files, key decisions, commands/tests + actual result, risk/remaining work, exact next slice, and any action needing owner approval. Never deploy to production, alter production financial records, purge data or reveal secrets without explicit authorization.

### 21.1 Mandatory Claude Code response format

```text
TASK: <ID and one-sentence outcome>
REPOSITORY STATUS: <existing capability found / gaps>
PROCESS IMPACT: <upstream / downstream / finance / inventory / security>
PLAN: <minimal vertical slice, files, migration, tests>
IMPLEMENTED: <actual changes, filenames and commit if any>
VERIFIED: <commands run and observed results; NOT RUN when applicable>
RECONCILIATION: <source-to-destination or ledger checks, if relevant>
DECISIONS/BLOCKERS: <approved, assumptions, pending>
NEXT ACTION: <one concrete action or approval>
```

### 21.2 Prohibited shortcuts

- Do not declare completion because a screen looks good or source code was generated.
- Do not remove working features to pass tests or hide errors.
- Do not fabricate sample audit evidence, test output, performance numbers, database counts or execution logs.
- Do not merge cross-company data, elevate privileges casually or use a global superuser to avoid rules.
- Do not write to posted accounting or history to make migration reconcile.
- Do not hard-code regional tax/payroll regulations without local validation.
- Do not turn an AI suggestion directly into an irreversible action without deterministic controls and required approval.
- Do not bury unknown assumptions: maintain a live risk/decision register.
- Do not change production credentials, backup retention, configuration or live customer data without authority.

---

## 22. Worked example: one requirement traced end-to-end

**`SLS-REQ-014` — Partial delivery followed by staggered invoicing**

**Business intent:** A confirmed customer order for 10 units can deliver 6 now and 4 later; issue invoices according to agreed invoicing policy without duplicating deliveries or exceeding authorized billed quantity.

- **Actors:** sales rep, warehouse operator, accountant, customer.
- **Prerequisites:** approved customer and item, allowed credit status, legal company, tax and UoM.
- **Objects:** `SalesOrder`, `SalesOrderLine`, `Reservation`, `StockMove`, `Invoice`, `InvoiceLine`, `BillingAllocation`, `JournalEntry`.
- **Linkages:** SO line -> multiple move/dispatch lines; SO line -> multiple invoice lines by billing allocation; invoice -> many payments via reconciliation links.
- **States:** confirmed order -> partially delivered -> partially invoiced -> fully delivered -> fully invoiced -> settled; state pairs may progress independently.
- **Quantities:** ordered=10, first shipped=6, remaining-to-ship=4; if policy is delivered-quantity invoicing, initial billable=6 minus previously invoiced delivered qty. Return later adjusts deliverable/billable or creates credit per defined policy.
- **Accounting:** invoice creates controlled AR/revenue/tax entries; stock movement creates valuation/COGS only per configured valuation/recognition policy. Both retain source references.
- **Security:** warehouse cannot post customer invoice, sales cannot bypass a locked accounting period, accountant cannot invent stock shipment.
- **Failure cases:** duplicate shipment call, retry after timeout, concurrent reservation, closed fiscal period, invalid company, invoice quantity above allowed threshold.
- **Tests:** ship 6 then 4, invoice partial then remainder, assert links/totals, reject duplicate call, verify role isolation and ledger/stock reconciliation, test reversal/return.
- **Acceptance:** user can open the order and drill down to both deliveries, all invoices, settlements, stock moves and related journal entries; totals agree with confirmed policy.

---

## 23. Master acceptance scorecard (per module)

Rate each as **Not started / In progress / Evidence provided / Accepted / Exception approved**:

- Functional fit and prioritized requirements.
- Entity/field dictionary complete and constraints enforced.
- Upstream/downstream relationships correct and drill-down available.
- Happy and exception workflows demonstrable.
- Accurate monetary, tax, stock and company effects; finance approved where relevant.
- Role matrix and company isolation tested.
- Notifications, scheduled jobs, integrations and retries tested.
- Dashboards reconcile with source records.
- Responsive, accessible, multi-language UX where required.
- Automated tests and UAT evidence attached.
- Migration scripts/checks and rollback approved.
- Documentation, training, deployment and support ownership complete.

An acceptance committee may sign off a clearly bounded exception. **Do not label the entire ERP complete while critical cross-module reconciliations remain unverified.**

---

## 24. Reference standards and version policy

Refer to current official documentation at implementation time; record exact framework, package and standard versions in the project ADRs. Useful baseline sources:

- Claude Code project guidance, context files and rules: https://code.claude.com/docs/en/memory
- Claude Code project configuration and agent tooling: https://code.claude.com/docs/en/settings
- OWASP ASVS 5.0.0: https://asvs.owasp.org/
- NIST SP 800-218 SSDF v1.1 (final) / monitor newer final revisions: https://csrc.nist.gov/pubs/sp/800/218/final
- Odoo 19 developer docs: https://www.odoo.com/documentation/19.0/developer.html
- WCAG 2.2: https://www.w3.org/TR/WCAG22/

**Regulatory caveat:** Financial accounting, e-invoicing, tax, employment and data protection rules vary by jurisdiction and evolve. This blueprint deliberately requires localization review rather than treating any unverified legal rule as universally applicable.

---

## 25. Final directive for the engineering team

**Build vertical business truth first; render useful screens second; automate only proven transactions third.** Every field must have a purpose and owner; every link must be explicit; every state change must be authorized; every monetary/stock figure must reconcile; every AI action must have limits; and every release must be demonstrably safe. Keep modules optional and loosely coupled, but never allow a module to be isolated from its mandatory business and accounting consequences.
