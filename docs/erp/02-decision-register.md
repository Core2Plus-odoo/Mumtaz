# IG Square ERP — Decision Register (ADRs)

Per blueprint §2. Each decision: **known answer** (✅ evidence) or **⚠️ needs sponsor approval**. No coding proceeds on a ⚠️ until decided (blueprint §2, §21.2).

| ADR | Decision | Current position | State |
|---|---|---|---|
| ADR-001 | Odoo-extend vs greenfield vs integrate; **module scope** | ✅ Odoo 19 extend. ⚠️ Confirm in-scope module list in `01-capability-matrix.md` (L2C + P2P + R2R + campaign costing + intercompany; defer HR/FBR; out of inventory/MFG). | ⚠️ needs approval |
| ADR-002 | Tenant model | ✅ Single DB `Mumtaz_IG2`, **multi-company** (IG Square + Mesh Media). No change proposed. | ✅ decided |
| ADR-003 | Company/branch/dept/cost-center model | ✅ 2 companies + Cost Center + Job Code analytic plans. ⚠️ Confirm whether "branch" (e.g. Karachi/Lahore) is needed as a dimension. | ⚠️ confirm |
| ADR-004 | Financial source of truth & close | ✅ Odoo `account` is SoT; `c2p_pk_vouchers` posts via it. ⚠️ Define period-close owner + lock policy (ADR-011). | ⚠️ partial |
| ADR-005 | Inventory valuation | ✅ **N/A** (services agency). | ✅ decided (Out) |
| ADR-006 | Localization (PK tax, invoice rules, currency, payroll, e-invoicing) | ✅ PKR; WHT 153 + SRB sales-tax modelled. ⚠️ FBR digital-invoicing obligation + payroll locality to confirm. | ⚠️ confirm |
| ADR-007 | Workflow / approval engine + SoD | ⚠️ **None today** — vouchers post immediately. Propose Odoo **Studio/`base` approval or `tier_validation`-style** gate on money-out above a threshold, requester≠approver≠poster. | ⚠️ needs approval (High) |
| ADR-008 | Integration strategy | ✅ Bank feeds, FBR, payroll external → integrate via governed contracts later. None live for IG2. | ✅ decided (later) |
| ADR-009 | Security & identity (RBAC, field-level, company isolation, audit) | ⚠️ Roles/record-rules **unmapped**; `sudo()` used in intercompany mirror (review for leakage); no field-level on salary/bank. | ⚠️ needs design (High) |
| ADR-010 | Deployment & DR (envs, backup, RPO/RTO, rollback) | ⚠️ **No staging/UAT** for IG2; upgrades go straight on live; backup/restore cadence unverified. | ⚠️ needs approval (High) |
| ADR-011 | Close/correction policy (locks, reversals, backdating) | ⚠️ Fiscal/tax lock dates 🔎; correction via reversal not formalized. | ⚠️ confirm |
| ADR-012 | Odoo version & dependencies | ✅ Odoo 19 (Community 🔎); `base_accounting_kit` 3rd-party dependency noted (two benign label warnings). | ✅ decided / 🔎 edition |

## Decisions I most need from you (to unblock the roadmap)
1. **ADR-001 scope** — approve the in-scope/deferred/out split (capability matrix).
2. **ADR-007 approvals** — do you want an approval gate on payments/vouchers (and at what rupee threshold, and who approves)? This is the single biggest control gap.
3. **ADR-010 environment** — may I set up a **staging copy of `Mumtaz_IG2`** (e.g. `odoo5`/separate DB) so changes and migrations are tested before the live DB? Blueprint forbids unproven changes on production financial data.
4. **ADR-006/011** — FBR e-invoicing in scope? Confirm fiscal-year and who may post/lock periods.

Nothing in the roadmap's "build" phases starts before #1–#3 are answered.
