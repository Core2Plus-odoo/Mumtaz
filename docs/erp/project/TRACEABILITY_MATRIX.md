# Traceability matrix

Process → requirement → entity/field → service/API → UI → security → report →
test → release → sign-off. Seeded from `REQUIREMENTS_REGISTER.csv`; one row
per requirement as it enters a sprint. Jawhar's delivered slices are listed
first because their evidence exists today.

| Process | Requirement | Entity / field | API | UI | Security | Test | Release | Sign-off |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Jewellery L2C | Approved-rate price on every line | `sale.order.line.jewellery_rate_per_gram` | `/jawhar/v1/sales/*` | NewQuote, OrderDetail | sale groups + VIP rules | `mumtaz_jewellery_sale/tests` (5 files) | #157 | owner (chat) |
| Jewellery counter | One-transaction commit with AML gate | `sale.order.action_counter_commit` | `/counter/*` | Counter | `_counter_extra_checks` | `mumtaz_jewellery_aml/tests` | #162 | owner |
| Jewellery stock | Import by spreadsheet, idempotent | `jewellery.piece.import` | `/pieces/import` | Pieces | manager only | `test_piece_import` (5) + door (2) | #169 | owner |
| C2P CRM | CRM-REQ-001 versioned rules | `crm.lead` | — | Odoo CRM | Sales Manager | CRM-TEST-001 | W1 | |
| Tenant L2C | SLS-REQ-001 | `sale.order`… | standard | Odoo | standard groups | SLS-E2E-001 | W2 | |
| Tenant P2P | PUR-REQ-001 | `purchase.order`… | standard | Odoo | standard | PUR-E2E-001 | W2 | |
| R2R | FIN-REQ-001..003 | `account.move` | standard | Odoo | Controller | FIN-TEST/REC | W2 | finance |
