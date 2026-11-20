# ERP project charter (DRAFT, pharma tenant as the reference ERP)

Filled only from evidence. **To confirm** = a business fact this audit could not establish; nothing below is signed. Template: [`../templates/PROJECT_CHARTER_TEMPLATE.md`](../templates/PROJECT_CHARTER_TEMPLATE.md).

| Field | Value |
| --- | --- |
| Project ID | **To confirm** (working name: C2P ERP programme, reference tenant `pharma`) |
| Sponsor and sign-off authority | **To confirm** (the owner who gives named "go" approvals for VPS gates acts as the de facto approver; not a charter signatory) |
| Business process owners | **To confirm**; roles needed: Finance Controller, Accountant, Tax Approver, Operations lead |
| Platform path | **Odoo extension** (`[V]` evidence in the audit); ERP-connected apps for portal/AI only. ADR-001 Proposed |
| Target stack and versions | Odoo 19.0 Community (build 20260719 on staging), PostgreSQL on the VPS, Python from the distribution package; third-party accounting kit pinned at `fdeea97d` |
| Legal entities, countries, branches | **To confirm** (assumption: one entity, Pakistan; decision D-003) |
| Operating units / shared services | **To confirm** |
| Hosting and data residency | Hostinger VPS `187.77.128.199`; residency policy **To confirm** |
| Environments and access ownership | local/CI → throwaway test DB → staging `mumtaz_pharma` (`pharma.mumtaz.digital`) → production **does not exist for pharma**; access with the owner, credentials never in the repo |
| Existing systems and data sources | Courier delivery reports and remittance slips (files); storefront orders; no legacy ERP identified |
| Transaction volumes, concurrency, history | **To confirm**; no real volume exists (demo data only) |
| Target user roles and languages | Operations, Finance Controller, Tax Approver, Administrator, Accountant, Auditor (proposed); English; Arabic only for the jewellery product |
| Accounting policies and localization owner | **To confirm** (decision D-006, a local accountant must own it) |
| Security, SSO, MFA, retention, RPO/RTO, audit | **To confirm** (D-009, D-010); audit baseline in doc 08 |
| Integrations | Courier files (built), bank statements (missing), e-invoicing gateway (scope unknown), channels (raw-event ingestion built) |
| Milestones, commercial constraints, acceptance parties | See the roadmap; commercial constraints **To confirm** |

## Expected measurable outcomes (baselines not invented)

| Metric | Source / baseline | Target | Owner | Evidence |
| --- | --- | --- | --- | --- |
| COD outstanding by courier and ageing bucket | `pharma.courier.shipment` (demo data only) | **To confirm** | Finance Controller | Pipeline / Ageing |
| Days from delivery to remittance | not measured on real data | **To confirm** | Finance Controller | after go-live |
| Courier shortfall rate | not measured | **To confirm** | Finance Controller | after go-live |
| Exception rate and closure time | demo data only | **To confirm** | Finance Controller | Exception Queue |
| Close cycle length, stockout, DSO | no baseline | **To confirm** | Controller / Operations | after the corresponding slices |

No target is reported as achieved.

## Module scope (disposition proposed in [02_CAPABILITY_MATRIX.md](02_CAPABILITY_MATRIX.md); needs sign-off)

Standard/Configure: contacts, sales, purchase, inventory, accounting. Extend (built): tax control, reconciliation hub, courier COD and its accounting, partner stock. Configure next: lots/expiry, localization. **Defer** until the owner says otherwise: HR/payroll, manufacturing, projects/service, maintenance, subscriptions, intercompany, POS.

## Assumptions, dependencies and unresolved decisions

See [DECISION_REGISTER.md](DECISION_REGISTER.md) (ADR-001..012, D-001..D-012, DEC-01..08).

## Approvals

| Stage gate | Business approver | IT/technical approver | Financial approver | Date |
| --- | --- | --- | --- | --- |
| G0 Discovery and audit | | | | |
| G1 Architecture and fit-gap | | | | |
