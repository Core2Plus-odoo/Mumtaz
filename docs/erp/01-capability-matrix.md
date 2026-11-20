# IG Square ERP — Capability & Fit-Gap Matrix (Gate G1)

Blueprint module registry (§5) mapped to IG Square (a **media/advertising agency** — so inventory/manufacturing are largely N/A). Disposition per blueprint §0: **Standard** (use native) · **Configure** · **Extend** (custom add-on) · **Integrate** · **Defer** · **Out**.
Status: **Have** (working) · **Partial** · **Gap** · 🔎 (confirm via audit script).

| Blueprint cap | Relevance to IG Square | Disposition | Status | Notes |
|---|---|---|---|---|
| PLT-01 Company/branch/cost-center | High (2 companies, cost centers, job codes) | Standard+Configure | **Have** | IG Square + Mesh Media; CC/Job-Code analytic plans built. Branch dimension not used. |
| PLT-02 Identity, roles, approvals, delegation | High | Standard+Extend | **Gap (High)** | No SoD/approval on vouchers; roles unmapped. **Top priority.** |
| PLT-03 Contacts / counterparties | High | Standard | **Have** | Customers + vendors present; WHT bound on partner. |
| PLT-04 Item/service catalog | Medium | Standard | **Partial** | Expense products seeded; sellable media services catalog 🔎. |
| PLT-05 Currency, tax, fiscal, localization | High (PKR, SRB/FBR WHT, 153) | Standard+Extend | **Have/Partial** | WHT (income+sales) at bill via native tax; receipt-side advance-tax wiring pending; fiscal lock 🔎. |
| PLT-06 Documents, audit, messaging | High | Standard | **Partial** | Chatter on challans; module-wide audit/retention policy not defined. |
| PLT-07 Workflow, jobs, notifications | High | Standard+Configure | **Gap** | No approval workflow; cron hygiene pending. |
| PLT-08 Data governance, sequences, import | Medium | Standard | **Partial** | Voucher numbering exists; import/migration controls not formalized. |
| CRM-01 Leads/opportunities | Medium (agency pitches) | Standard | 🔎 Gap? | `c2p_proposal`/`mumtaz_crm_starter` exist in repo; install on IG2 unconfirmed. |
| SLS-01 Quote/pricing/sales order | Medium–High | Standard | 🔎 | Is AR raised via SO→Invoice or direct invoices? Audit settles. |
| SLS-02 Contracts/recurring billing | High (retainers, media contracts) | Standard/Extend | **Gap** | Retainer/subscription billing not set up. |
| SLS-03 Returns/rebates/credit notes | High (BD/rebate pass-backs) | Standard+Configure | **Partial** | Rebate accounts exist; structured rebate workflow not modelled. |
| PUR-01 Requisition/RFQ/PO | Low–Medium | Standard | **Defer/🔎** | Media buys may be POs or direct bills; confirm. |
| PUR-02 Supplier invoices & settlement | High | Standard+Extend | **Have** | Bills + pay + dual WHT + knock-off done. |
| INV-01/02/03 Inventory/valuation | **N/A** (services) | Out | Out | No stock. |
| FIN-01 GL & controls | High | Standard | **Have** | Full CoA; journals; period controls 🔎. |
| FIN-02 AR / customer invoicing / receipts | High | Standard+Extend | **Partial** | Receipt voucher + customer WHT; advance-tax receivable wiring pending. |
| FIN-03 AP / bank / reconciliation | High | Standard+Extend | **Partial** | Payments/vouchers done; **bank-statement reconciliation** setup 🔎. |
| FIN-04 Budgets / cash forecast / assets | Medium | Standard (base_accounting_kit) | **Partial** | Assets via kit; depreciation register completeness 🔎; budgets not set. |
| FIN-05 Intercompany / consolidation | High (IG Square↔Mesh) | Extend | **Have/Partial** | Intercompany transfer + **mirror** built; **group consolidation/elimination** not. |
| PRJ-01 Projects/timesheets/costing | High (campaign costing) | Standard | **Gap/🔎** | Job codes exist as analytic; true campaign P&L via Projects not set. |
| SRV-01/02 Helpdesk/field/equipment | Low | Out/Defer | Out | Fleet exists as assets only. |
| MFG-01 Manufacturing | **N/A** | Out | Out | — |
| HRM-01/02 HR / payroll | Medium | Standard/Integrate | **Gap/🔎** | Payroll accounts exist (salaries, EOBI, PF); HR/payroll module 🔎. |
| OMC-01 POS / e-commerce / portals | Low | Defer | Defer | Repo has portals; not for IG Square finance. |
| BI-01 Dashboards/command center | High | Standard+Extend | **Gap** | No role dashboards; financial statements only. |
| AI-01 Governed AI agents | Later | Extend | Defer | `mumtaz_ai`/`mumtaz_voice` exist; out of current finance scope. |
| PLT-05/FBR e-invoicing | Statutory 🔎 | Integrate | 🔎 Gap | `mumtaz_einvoicing` in repo; FBR obligation + install unconfirmed. |

## Scope recommendation (💡 for sponsor sign-off)
A media agency's ERP spine is **Lead-to-cash + Procure-to-pay + Record-to-report + Campaign costing + Intercompany**, not inventory/manufacturing. Proposed **in-scope** for IG Square:
**CORE/COMMON:** PLT-01..08, FIN-01/02/03/05, PUR-02, SLS-01/02/03, CRM-01, PRJ-01 (campaign costing), BI-01, FIN-04 (assets+budget).
**DEFER:** PUR-01 (unless they run requisitions), HRM (payroll — confirm if in Odoo or external), FBR e-invoicing (pending obligation check), AI-01.
**OUT:** INV-*, MFG-*, SRV-*, POS.

This split is a **decision for approval** (ADR-001 scope) — see `02-decision-register.md`.
