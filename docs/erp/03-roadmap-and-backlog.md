# IG Square ERP — Roadmap & Prioritized Backlog

Dependency-based (blueprint §19), not calendar promises. Each item is a vertical slice with acceptance criteria; built standard-first; every money-touching slice ships with a test and an approval/role check.

## Waves (gated)
- **Wave 0 — Audit & decisions (now).** This doc set + discovery script + sponsor sign-off on ADR-001/007/010. *Gate: signed scope + approval model + staging decision.*
- **Wave 1 — Controls & safety (highest value, lowest regret).** Approval/SoD on money-out; security/role matrix; staging DB; cron/log hygiene; finish the pending tax wiring. *Gate: controls tested as each role.*
- **Wave 2 — Complete the finance spine.** Receipt-side customer WHT → advance-tax receivables + challan reconciliation; bank-statement reconciliation; period-close/lock policy; fixed-asset register check. *Gate: AR/AP/bank reconcile; close rehearsed.*
- **Wave 3 — Commercial & costing.** Confirm/enable Lead→Quote→Invoice (CRM/Sales); campaign/job P&L via Projects or analytic; retainer/recurring billing; rebate/BD pass-back workflow. *Gate: one campaign traced end-to-end.*
- **Wave 4 — Visibility.** CFO/Owner dashboards (cash, AR/AP aging, WHT receivable vs challans, intercompany balance, budget vs actual) reading validated data. *Gate: every KPI drills to records.*
- **Wave 5 — Statutory & scale (if approved).** FBR e-invoicing; HR/payroll; group consolidation/eliminations; AI read-only briefings.

## Prioritized backlog (next up)
Acceptance = blueprint DoD §3.4 (reviewed, tested incl. negative role, reconciles, documented, owner-accepted).

| ID | Slice | Wave | Pre-req | Why | Acceptance (summary) |
|---|---|---|---|---|---|
| **FIN-SETUP-01** | Run `setup_taxes.py` (bill Sales-Tax-Input + income WHT; receipt advance-tax receivables + sale WHT codes) | 1 | — | Finishes agreed tax model; unblocks receipt WHT | `SETUP|` output shows accounts wired; a test bill carries the taxes; a receipt voucher posts WHT to the receivable without error |
| **SEC-01** | Role & record-rule matrix for IG Square (accountant / finance-controller / data-entry / auditor / cross-company) + review `sudo()`/`with_company()` for leakage | 1 | ADR-009 | Blueprint §10 High gap | Each role tested; no cross-company leak; auditor read-only |
| **CTRL-01** | Approval gate on money-out (voucher/direct/intercompany/interbank/payment) above threshold; requester≠approver≠poster; audit of approver | 1 | ADR-007 | Blueprint §8/§10 High gap | Below-threshold auto; above routes for approval; poster can't self-approve; logged |
| **ENV-01** | Stand up a **staging** copy of Mumtaz_IG2 (restore to a separate instance/DB) + document upgrade/rollback runbook | 1 | ADR-010 | No prod-safe change path today | Staging reachable; module upgrade rehearsed there before live |
| **OPS-01** | Pin `odoo3` to `db_name=Mumtaz_IG2` (stop cron-polling dead DBs); clean logs | 1 | — | Hygiene; removes `scratch_pre` noise | Log shows only Mumtaz_IG2 activity |
| **FIN-AR-01** | Customer receipt → net to bank + income/sales WHT to advance-tax receivables; reconcile challan register to the receivable (variance report) | 2 | FIN-SETUP-01 | Completes "customers withhold from us" | Receipt posts; advance-tax asset grows; challan links; variance report balances |
| **FIN-BANK-01** | Bank-statement import + reconciliation for the 5 bank accounts | 2 | — | Blueprint §9 reconcile | Statements reconcile to GL; exceptions listed |
| **FIN-CLOSE-01** | Period-close checklist + fiscal/tax lock policy + reversal-only corrections | 2 | ADR-011 | §9/§4.2 | Locked period blocks posting; correction via reversal only |
| **COST-01** | Campaign / client P&L (Projects or analytic rollup over Job Code) | 3 | audit (PRJ) | Agency margin visibility | One campaign shows revenue, media cost, rebate, margin, drill-down |
| **BI-01** | CFO dashboard: cash, AR/AP aging, WHT-receivable vs challans, intercompany balance, budget vs actual | 4 | FIN-AR-01 | §11.3 | Each tile drills to source; company filter; eliminations labelled |

## Immediate recommended next action
Per blueprint §21 "NEXT ACTION": **run the §6 discovery script** (fills the 🔎 gaps) and **answer ADR-001/007/010**. In parallel, **FIN-SETUP-01** and **OPS-01** are safe, additive and already prepared — they can run now without waiting on the big decisions.
