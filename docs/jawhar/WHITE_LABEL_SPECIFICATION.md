# Jawhar — white-label specification

## 1. Brandable surface

| Surface | Elements | Today | Target |
| --- | --- | --- | --- |
| Jawhar app shell | product name, logo, favicon, primary/accent colours, login background, footer line | not branded | brand tokens served at login (`/auth/me` carries `brand`) and applied as CSS variables |
| Kiosk | name of the assistant, avatar, colours, greeting, languages | config parameter for the agent id only | per-tenant kiosk brand record |
| Client app and tray link | logo, colours, sender name | fixed | from the same brand record |
| Documents | invoice/receipt header and footer, logo | Odoo company + `mumtaz.brand` report header/footer | add receipt template tokens |
| E-mail (when any) | sender name/address | `mumtaz.brand` | unchanged |
| Domain | `tenant.<platform>` or custom domain | `mumtaz.tenant.custom_domain` field; SSL manual | automated certificate per domain (Phase 4b) |
| Public site | reseller landing | none | optional reseller page template |

## 2. Data model

Reuse `mumtaz.brand` (product name, logo, favicon, primary/secondary colour, email, report header/footer, portal welcome). Add `jawhar.brand.extension` fields: accent colour, kiosk assistant name and avatar, Arabic product name, login tagline, receipt footer, typography choice (two curated pairs). Validation: contrast of primary on white ≥ 4.5:1 or the save is refused with the computed ratio.

## 3. Resolution

Host → tenant → brand → tokens JSON (cached per tenant, invalidated on write). The app loads tokens before first paint; a missing brand falls back to Jawhar defaults from the design system.

## 4. Roles

Platform operator: create brands, assign to tenants, set domains. Reseller operator: edit own brand(s) and see own tenants only (record rule on `mumtaz.brand` by reseller partner: PLANNED). Tenant administrator: edit logo and colours within the reseller's constraints (which fields are open: a flag per field).

## 5. What is never white-labelled

The pricing engine, the autonomy policy, the audit trail, the readiness vocabulary, the consent sentences (translation allowed, meaning fixed).

## 6. Acceptance

A second tenant provisioned with bundle `jawhar` and brand "Dar Al Noor" shows its name, logo and colours on login, in the shell, on the kiosk and on a receipt; the first tenant is unchanged; a user of one cannot reach the other by host or by id.
