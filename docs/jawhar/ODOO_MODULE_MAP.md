# Jawhar — Odoo module map

Standard first: configure Odoo Community, then native automation, then a
Jawhar module on top (inherit, never recreate). No Enterprise module.

| Capability | Standard Odoo 19 CE | OCA (candidates, pinned when adopted) | Jawhar module | Status |
| --- | --- | --- | --- | --- |
| Products, lots, serials, warehouses | `stock`, `product` | — | `mumtaz_jewellery` (piece fields on lot, categories, dims, import) | VERIFIED |
| Gold rate, pricing engine, old gold | — | — | `mumtaz_jewellery` (`jewellery.gold.rate`, `pricing.py`, `jewellery.old.gold`) | VERIFIED |
| Clients, tiers, restricted records | `contacts`, `mail` | — | `mumtaz_jewellery_vip` | VERIFIED |
| Owner cards | — | — | `mumtaz_jewellery_owner` | VERIFIED |
| Quotes, orders, invoices, payments | `sale_management`, `account` | — | `mumtaz_jewellery_sale` (frozen rate, discount limit, counter commit) | VERIFIED |
| Pipeline, tray, viewing, reservation | `crm` | — | `mumtaz_jewellery_crm` | VERIFIED |
| Outreach, consent, occasions | `mail`, `mail_activity` | — | `mumtaz_jewellery_outreach` | VERIFIED |
| AML / KYC | — | — | `mumtaz_jewellery_aml` | VERIFIED |
| Stores, transfers, reconciliation | `stock` (transit, multi-warehouse) | — | `mumtaz_jewellery_stores` | VERIFIED |
| Rate feed, web shelf | `website_sale` (shelf) | — | `mumtaz_jewellery_channels` | VERIFIED |
| Client app | — | — | `mumtaz_jewellery_client` | VERIFIED |
| Agents | — | — | `mumtaz_jewellery_ai` | VERIFIED |
| Kiosk (Noor) | — | — | `mumtaz_jewellery_kiosk` | VERIFIED (device pending) |
| API door | — | — | `mumtaz_jewellery_api` | VERIFIED |
| Website door (demo requests) | `crm` | — | `mumtaz_jewellery_website` (new) | VERIFIED |
| Demo data | — | — | `mumtaz_jewellery_demo` | VERIFIED |
| Accounting, VAT, localisation | `account`, `l10n_ae`, `l10n_sa`, `l10n_pk`, `l10n_gcc_invoice` | `account_financial_report`, `mis_builder` | — | PLANNED per tenant (ADR-006) |
| Purchase, consignment | `purchase`, `stock` (consignment owner) | `purchase_order_approved` | thin bridge if needed | PLANNED |
| Repairs, workshop | `repair`, `mrp` | — | gram-aware repair lines | PLANNED |
| E-commerce | `website_sale` | — | shelf already published | PLANNED |
| Automation | `base_automation`, scheduled actions, templates | — | `jewellery.event` bus | PLANNED (Phase 6) |
| Tenancy, branding, billing | — | — | `mumtaz_tenant_manager`, `mumtaz_branding`, `mumtaz_control_plane`, `mumtaz_portal_routing` (platform) | PARTIALLY (install-tested) |
| HR, payroll | `hr`, `hr_attendance` | `payroll` OCA | — | not in scope |

Dependency rule: every Jawhar module depends on `mumtaz_jewellery`; the API
depends on the business modules, never the reverse; the website module
depends on `crm` and `mumtaz_jewellery` only.
