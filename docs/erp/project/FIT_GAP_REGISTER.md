# Fit-gap register

One row per requirement area; detailed rows live in
`REQUIREMENTS_REGISTER.csv`. Disposition vocabulary: Standard / Configure /
Integrate / Extend / Build / Defer / Exclude. "Unknown is not approved."

| Area | Native capability (Odoo 19 CE) | Gap found | Disposition | Justification | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- |
| CRM pipeline (C2P) | `crm` stages, automation rules | Logic in DB server actions, no tests | Build (versioned module `c2p_crm_rules`) | Risk R1 | | Proposed |
| Lead-to-cash (generic tenant) | `crm` → `sale` → `stock` → `account` | Never proven end to end outside jewellery | Configure + tests | Blueprint §6.1 | | Proposed |
| Procure-to-pay | `purchase` → `stock` → `account` 3-way match | Unproven; no approval thresholds set | Configure + tests | §6.2 | | Proposed |
| Localisation | `l10n_ae`, `l10n_sa(_edi)`, `l10n_pk`, `l10n_gcc_invoice` | Not installed by code | Configure per tenant | ADR-006 | finance | Decision |
| E-invoicing | `l10n_sa_edi` (ZATCA) native; UAE QR not native; FBR not native | Custom module exists, untested | Test and keep for UAE/PK; evaluate native ZATCA vs custom | avoid two ZATCA paths | | Decision |
| Financial statements | `account` reports (TB, P&L, BS, aged) | Custom report module untested | Evaluate standard + OCA `mis_builder` | D-02 | finance | Decision |
| Fixed assets | Enterprise | None | Integrate OCA `account_asset_management` | D-04 | | Decision |
| Budgets | Enterprise | None | Integrate OCA `mis_builder_budget` | D-04 | | Decision |
| Bank statements | manual entry native; CSV/OFX import OCA | CFO toolkit parses files but does not post | Integrate OCA import; CFO toolkit stays analysis | FIN-03 | | Proposed |
| Projects and costing | `project`, `hr_timesheet`, analytic | Tracker has commercials, no cost from timesheets | Configure timesheets + analytic; Extend tracker to read cost | PRJ-01 | | Proposed |
| Intercompany (C2P) | inter-company rules (CE: `account` multi-company), analytic | 60/40 split is operational only | Configure mirrored invoices; Build nothing | FIN-05 | finance | Decision |
| Approvals | `sale` discount/`purchase` double validation, `base_automation` | Three bespoke patterns | Keep; generic later | ADR-007 | | Accepted |
| Jewellery vertical | — | Built, 242 tests | Extend (existing) | VRT-01 | | Built |
| HR, payroll, MRP, service, rental | partly CE, partly Enterprise | none | Defer | not scoped | | Deferred |
