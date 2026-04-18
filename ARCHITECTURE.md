# Mumtaz Platform — Architecture

## 1. Domains / Subdomains

| Domain | Purpose |
|---|---|
| `mumtaz.digital` | Marketing website (static) |
| `app.mumtaz.digital` | Customer portal — signup, onboarding, billing |
| `erp.mumtaz.digital` | Odoo ERP (customer-facing) |
| `zaki.mumtaz.digital` | ZAKI AI CFO — frontend + API |
| `marketplace.mumtaz.digital` | B2B Marketplace — storefront + vendor portal |
| `admin.mumtaz.digital` | Odoo backend UI (internal) |

---

## 2. Portals / Apps

| App | File | Auth |
|---|---|---|
| Customer Portal | `apps/portal/index.html` | JWT via ZAKI server |
| ZAKI AI CFO | `apps/zaki-server/main.py` (API) | JWT |
| B2B Marketplace Storefront | `apps/marketplace/index.html` | None (public) |
| Vendor Portal | `apps/marketplace/vendor.html` | JWT via ZAKI server |
| Odoo ERP | Odoo (port 8069) | Odoo session |

**ZAKI Server** (`apps/zaki-server/main.py`) is the central auth API for all portals:
- `POST /api/v1/auth/signup` — register (also creates Odoo user + tenant)
- `POST /api/v1/auth/register` — alias for signup (ZAKI CFO compat)
- `POST /api/v1/auth/login` — login via Odoo first, SQLite fallback
- `GET  /api/v1/auth/me` — profile
- `POST /api/v1/ai/chat/stream` — Claude AI (SSE)
- `GET  /health`

Runs as systemd service on **port 8001**. nginx proxies `zaki.mumtaz.digital/api/` → `127.0.0.1:8001`.

---

## 3. Odoo Role

- **Database:** `Mumtaz_ERP` (PostgreSQL, user: `odoo`)
- **Admin:** `umer@mumtaz.digital`
- **Single source of truth for auth** — ZAKI server validates all logins via Odoo XML-RPC
- **Tenant registry** — `mumtaz.tenant` model stores one record per customer org (state: draft → active)
- **Custom addons:**

| Addon | Purpose |
|---|---|
| `mumtaz_tenant_manager` | Core `mumtaz.tenant` model, provisioning wizard |
| `mumtaz_control_plane` | Subscription health fields on tenant form/list |
| `mumtaz_sme_profile` | SME business profile per tenant |
| `mumtaz_cfo_workspace` | ZAKI CFO workspace linked to SME profile |
| `mumtaz_brand` | White-label brand config |

---

## 4. Completed

- [x] Customer portal (`app.mumtaz.digital`) — full SPA with real JWT auth
- [x] 5-step onboarding wizard (company → products → ERP modules → plan → review)
- [x] ZAKI server v2 — unified auth backed by Odoo XML-RPC (`odoo_live: true`)
- [x] Signup creates Odoo user + `mumtaz.tenant` record automatically
- [x] Same credentials work at `erp.mumtaz.digital` (Odoo login)
- [x] `/auth/register` alias added for ZAKI CFO frontend compatibility
- [x] Fixed `mumtaz_control_plane` xpath install error (changed to `//notebook` anchor)
- [x] nginx config updated — `app.mumtaz.digital` serves static SPA (not Odoo proxy)
- [x] Marketplace architecture defined (public storefront + vendor portal)

---

## 5. Pending

| Item | Notes |
|---|---|
| Marketplace HTML | `apps/marketplace/index.html` + `vendor.html` — in progress |
| Nginx redeploy on VPS | New config separates `app.` (static) from `erp.` (Odoo) — fixes blank page |
| Marketplace nginx block | Update to serve static files instead of proxying to Odoo |
| Install `mumtaz_control_plane` | VPS needs `git pull` then install from Odoo UI |
| SSL certificates | Run certbot after DNS is set for all domains |
| Odoo admin password rotation | Currently `Admin1234!` — change after testing |
