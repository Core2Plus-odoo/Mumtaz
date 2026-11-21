# Module Specification: [ID] [Name]

**Classification:** Core / Common / Optional  
**Module owner / process owner:**  
**Status:** Draft / Reviewed / Approved / Built / Verified / Accepted  
**Platform:** Odoo / Custom / Connected  
**Versions:**  
**Dependencies (inbound):**  
**Downstream modules impacted:**  
**Out of scope:**  

## 1. Business mission and measurable result

## 2. User roles and access
| Role | View | Create | Edit draft | Approve | Post/execute | Reverse | Export | Sensitive fields |
|---|---|---|---|---|---|---|---|---|

## 3. User stories and requirements
| Req ID | Role | User need | Priority | Acceptance criteria | Status |
|---|---|---|---|---|---|

## 4. End-to-end journey and source/target links
- Upstream records and source-of-truth:
- Actions, statuses, events and notifications:
- Downstream documents/stock/accounting/BI:
- Link cardinality (1:N / M:N) and data provenance:
- Cancellation, return, refund, reversal, partial and retry paths:

## 5. Entity relationship design
| Model/entity | Ownership scope | Fields and constraints | Parent/child | Audit policy | Migration implications |
|---|---|---|---|---|---|

## 6. Field dictionary
Complete `DATA_DICTIONARY_TEMPLATE.csv`, including precision, defaults, related/compute, company ownership and validation.

## 7. Transaction state machine
| Source state | Action | Authorized actor | Guard | Side effects | Target state | Audit |
|---|---|---|---|---|---|---|

## 8. Rules, calculations and accounting effects
- Currency/tax/precision/rounding:
- Reconciliation and GL effect:
- Stock movement/valuation effect:
- Project/analytic/cost-center effect:
- Fiscal and period-lock rules:

## 9. UI and enterprise UX
- Home/list/form/search/action views:
- Create/edit/mobile flows:
- Status, warning, approval and error states:
- Dashboard metrics with SQL/domain lineage:
- Localization and RTL/accessibility:

## 10. Interfaces and automations
| Interface/event | Direction | Trigger | Ownership | Schema | Authentication | Retry/idempotency | Monitoring |
|---|---|---|---|---|---|---|---|

## 11. Negative and edge scenarios
- Missing data / duplicate request:
- Unauthorized company/role:
- Partial quantities and concurrency:
- Closed periods / failed external API:
- Corrections and disputes:

## 12. Implementation design
- Existing native capabilities and fit-gap:
- Files/models/services/views to change:
- DB migrations/data backfill:
- Backward compatibility, rollback and feature flags:

## 13. Tests and acceptance
| Test ID | Requirement | Scenario | Expected | Evidence | Status | Owner |
|---|---|---|---|---|---|---|

## 14. Release and sign-off
- QA evidence:
- UAT owner / result:
- Finance/stock reconciliation:
- Security review:
- Docs and training:
- Known limitations and approved exceptions:
