# Jawhar — tenancy and security

## 1. Tenant model (decided: ADR-002 in `docs/erp`)

One PostgreSQL database per tenant, one Odoo filestore per tenant, routed by
host. Multi-company inside a tenant only for legal entities under one owner
(a group with a Dubai and a Riyadh company). Stores are warehouses, not
companies. The control plane (tenant registry, plans, billing, branding)
lives in its own database and never reads tenant data.

What exists: `mumtaz.tenant` (database name, subdomain, custom domain,
state, brand, admin, bundle), provisioner steps (create DB → install → admin
→ settings), host→database resolution in `mumtaz_portal_routing`. VERIFIED
by install tests only; the real provisioner is NOT VERIFIED on a host.

What Jawhar adds (Phase 4): a `jawhar` module bundle; tenant settings for
currency, VAT rate holder, AML threshold holder, voice agent id, model key
(encrypted); brand tokens served to the app; per-tenant export and
offboarding.

## 2. Isolation guarantees

| Layer | Mechanism | Evidence |
| --- | --- | --- |
| Data | separate database and filestore per tenant | compose + provisioner |
| Request | host resolves to exactly one database; unknown host → 404 | routing tests |
| Within tenant | Odoo groups + record rules on every Jawhar model; restricted clients hidden (404 not 403) | negative tests per module |
| Company | `company_id` + rules on platform modules (this week) | `TwoCompanyCase` tests |
| Privilege | every `sudo()` labelled with a reason and listed by `scripts/check_sudo.py` in CI | 269 sites |
| Public doors | no session, no internal ids, per-contact caps, honeypot, nginx `limit_req` | kiosk, client, website tests |
| Secrets | environment variables; tokens encrypted at rest; never logged | `.env` ignored by git |

## 3. Roles

Jawhar groups: jewellery user, jewellery manager, VIP manager, AML officer,
plus standard sales/stock/account groups. Platform roles (to define in
Phase 4): tenant administrator, reseller operator, platform operator,
support (read-only, time-boxed, logged).

## 4. Data protection

- Personal data of clients stays in the tenant database; the control plane holds only the tenant's own contacts.
- Consent recorded with source and date (client) and verbatim text (website demo request).
- Restricted VIP data never enters a model request (enforced in the agent tool layer, tested).
- Retention periods are configuration for the named finance/compliance manager; nothing is defaulted in code.
- Export: Odoo standard export for staff; tenant-level export PLANNED.

## 5. Authentication

Odoo sessions for the app and API; one-time codes for the client app (3 per
hour); signed tokens with digests for tray links and agent drafts; HTTP basic
auth in front of staging. MFA (`auth_totp`) for managers is recommended and
not yet enforced (ADR-009).

## 6. Audit

API audit rows (who, what, when, duration, outcome); VIP access log (form,
list, export); agent run log with tool calls; rate approval chatter; demo
request chatter. Logs are per tenant; central log shipping PLANNED.

## 7. Open items

MFA enforcement; staging on a shared host (production needs its own);
restore drill not evidenced; penetration test not done; rate limiting at
nginx exists only for the website door; secret rotation procedure.
