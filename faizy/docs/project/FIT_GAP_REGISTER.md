# Faizy — Fit-Gap Register

Classifies every capability in the ERP Master Blueprint's canonical module registry (§5) against
what Faizy actually is: a narrow, single-vertical family-care service on Odoo Community, **not** a
general-purpose multi-module ERP. Per the blueprint's own §0: "This document is a master standard,
not a claim that every listed feature belongs in every project... Do not assume every project needs
every module." Most rows below are correctly **Out of scope** — that is the finding, not a gap to
apologize for.

Classification: `Standard` (native Odoo, unmodified) · `Configure` (native, settings-driven) ·
`Extend` (native model inherited/extended) · `Custom` (new Faizy-specific model) · `Integrate`
(external system) · `Defer` (explicitly postponed, decision recorded) · `Out of scope` (not needed
for this product).

| ID | Capability | Classification | Evidence / notes |
|---|---|---|---|
| PLT-01 | Tenant, company, org structure | Extend | Single `res.company`; no branch/dept model (ADR-003) |
| PLT-02 | Identity, roles, approvals, delegation | Extend + Custom | `res.groups` hierarchy (`faizy_core`) + bespoke `faizy.ai.draft` approval engine (`faizy_ai`), not generic Odoo `approval.request` |
| PLT-03 | Shared contacts/counterparties | Extend | `res.partner` extended for customers (`is_faizy_customer`, segment, care score) and vendors (`faizy_vendor_*`); no separate Party model |
| PLT-04 | Item/service catalog | Custom | `faizy.service`/`faizy.service.category`, not Odoo's generic `product.template` catalog (though `product` is a dependency, used for subscription/overage billing products on `faizy.plan`) |
| PLT-05 | Currency, tax, fiscal, localization | Standard + Configure | `l10n_pk`; multi-currency plan pricing via `faizy.plan.price` per currency; company country/currency itself unset (ADR-006, open) |
| PLT-06 | Documents, attachments, messaging, audit | Extend | `mail.thread`/`mail.activity.mixin` on most transactional models; `faizy.document` for family-member paperwork with expiry tracking |
| PLT-07 | Workflow, jobs, notifications, integration | Custom | Scheduled actions (`_cron_*`) + `faizy.whatsapp.message` queue, not a generic workflow engine |
| PLT-08 | Data governance, import, reference codes | Partial | `faizy.sample.data` for demo/seed data with clean removal; no formal import-batch/external-identity framework (not needed — no migration source, ADR per charter) |
| CRM-01 | Leads, opportunities, campaigns | **Out of scope** | No CRM model exists. Customer acquisition is via the public website signup (`/start`), not a sales pipeline |
| SLS-01 | Quotation, pricing, sales orders | **Out of scope (narrow Extend)** | `faizy.order` *is* effectively a one-line, non-negotiated service order — no quotation step, no multi-line order, no discount/pricelist engine beyond the plan price table |
| SLS-02 | Contracts, recurring billing, subscriptions | Custom | `faizy.subscription` — a hand-built recurring-billing model, because Odoo Community has no Subscriptions app (explicit, documented reason) |
| SLS-03 | Returns, rebates, customer service | **Out of scope** | No RMA/return/credit-note-request model. A cancelled order is just `state = cancelled`; no refund workflow modeled |
| PUR-01 | Requisition, RFQ, PO | **Out of scope** | No purchasing workflow — vendors are routed to via `faizy.order.vendor_id`, not a PO |
| PUR-02 | Supplier invoices, settlement | **Gap (flagged, not built)** | Vendor commission is computed and shown (`faizy_vendor_commission_total`) but **no vendor bill is ever created automatically** — see FIN-03 below and DECISION_REGISTER ADR-004 |
| INV-01/02/03 | Inventory, lots/serials, valuation | **Out of scope** | Faizy buys on the customer's behalf; it never holds stock. Confirmed by the absence of any `stock.*` dependency |
| FIN-01 | General ledger | Standard | Native `account.move`/`l10n_pk` chart of accounts |
| FIN-02 | AR, customer invoicing | Extend | `faizy.subscription._cron_recurring_invoice` creates real `account.move` invoices on schedule |
| FIN-03 | AP, bank reconciliation | **Gap** | No automated vendor-bill creation for the 10% commission model; a human must create a Vendor Bill by hand today. **This is the clearest concrete gap in the whole register** — the product's own vendor-commission revenue line is tracked but not booked |
| FIN-04 | Budgets, cash forecast, fixed assets | **Out of scope** | Not relevant at current scale; no budget/asset model exists or is implied |
| FIN-05 | Intercompany, consolidation | N/A | Single company — not applicable (ADR-002) |
| PRJ-01 | Projects, tasks, timesheets | **Out of scope** | Not a project business |
| SRV-01 | Helpdesk, field service, SLA | Extend (this *is* the product) | `faizy.order` + `faizy.worker` is a lightweight field-service model; no formal SLA tracking (no response/resolution-time fields) |
| SRV-02 | Equipment, maintenance, rental | **Out of scope** | No equipment/asset tracking — Faizy workers use their own means, not company equipment |
| MFG-01 | Manufacturing, BOM, quality | **Out of scope** | Not a manufacturing business |
| HRM-01 | Employees, attendance, leave, expenses | **Out of scope** | Workers are independent contractors (`faizy.worker`, via `faizy.application`), not `hr.employee` records; no attendance/leave model |
| HRM-02 | Payroll | **Out of scope** | No payroll — workers are presumably paid per job/commission outside this system (not evidenced either way; worth confirming with the product owner rather than assuming) |
| OMC-01 | POS, e-commerce, portals | Partial — portal only | `faizy_website` (portal under `/care`, no POS, no e-commerce cart) |
| BI-01 | Reporting, dashboards | Custom | `faizy.dashboard` (TransientModel) with hand-built KPI computation; not Odoo's generic BI/pivot layer |
| AI-01 | Governed AI agents | Custom, well-built | `faizy_ai` — draft/approve/execute with scoped ORM write guards, approval routing by kind, working-hours hold. Matches the blueprint's own §12 "Draft" and "Act with approval" tiers closely, by independent convergence, not because this pack was consulted when it was built |
| VRT-01 | Industry extension layer | N/A | Faizy itself is the vertical; there is no further industry-pack layer on top |

## The honest summary

Of the blueprint's ~30 canonical capabilities, Faizy genuinely needs roughly a third of them
(platform, parties, a narrow order/service model, AR invoicing, a WhatsApp integration, a governed
AI layer) and correctly has none of the rest (CRM pipeline, purchasing, inventory, manufacturing,
HR/payroll, POS/e-commerce, projects, fixed assets, intercompany). **Building any of the "out of
scope" rows without a real business reason would be over-engineering**, directly against the
blueprint's own standard-first and no-fake-completion principles.

The one row that is a genuine, concrete, worth-fixing gap rather than a correct exclusion is
**FIN-03 — vendor commission never becomes an AP bill.** That is the most defensible next backlog
item to come out of this audit, if the product owner wants it; it is not being proposed as code
here without approval (see PROJECT_CHARTER.md's stage-gate note).
