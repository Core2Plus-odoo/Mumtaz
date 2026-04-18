# Mumtaz Platform

SaaS platform for UAE/GCC businesses — ERP, AI CFO, B2B Marketplace, and white-label tools — all on a single multi-tenant Odoo backend with unified authentication.

---

## Live Domains

| Domain | What it serves |
|---|---|
| `mumtaz.digital` | Marketing website (static HTML) |
| `app.mumtaz.digital` | Customer portal — signup, onboarding, billing, modules |
| `erp.mumtaz.digital` | Odoo ERP (proxied from VPS port 8069) |
| `zaki.mumtaz.digital` | ZAKI AI CFO — static frontend + FastAPI backend (port 8001) |
| `marketplace.mumtaz.digital` | B2B Marketplace — public storefront + vendor portal |
| `admin.mumtaz.digital` | Odoo backend UI (restricted) |

---

## Architecture

```
Browser
  │
  ├── app.mumtaz.digital ──► nginx static /var/www/app.mumtaz.digital
  │                              (apps/portal/index.html — single-file SPA)
  │
  ├── zaki.mumtaz.digital ─► nginx static /var/www/zaki.mumtaz.digital
  │       └─ /api/ ──────────► FastAPI (127.0.0.1:8001)
  │                              apps/zaki-server/main.py
  │
  ├── erp.mumtaz.digital ──► nginx proxy → Odoo (127.0.0.1:8069)
  │
  ├── marketplace.mumtaz.digital ► nginx static /var/www/marketplace.mumtaz.digital
  │                                  (apps/marketplace/ — two-file SPA)
  │
  └── admin.mumtaz.digital ─► nginx proxy → Odoo (127.0.0.1:8069)

ZAKI Server (FastAPI, port 8001)
  ├── POST /api/v1/auth/signup      → creates Odoo user + mumtaz.tenant + SQLite cache + JWT
  ├── POST /api/v1/auth/register    → alias for /signup (ZAKI CFO frontend compat)
  ├── POST /api/v1/auth/login       → validates via Odoo XML-RPC first, falls back to SQLite
  ├── GET  /api/v1/auth/me          → returns profile from JWT + SQLite
  ├── GET  /api/v1/tenant/me        → reads mumtaz.tenant from Odoo
  ├── POST /api/v1/ai/chat/stream   → streams Claude (SSE) — requires ANTHROPIC_API_KEY
  └── GET  /health                  → { status, ai_ready, odoo_live, odoo_url, odoo_db }

Odoo (127.0.0.1:8069) — single source of truth for auth
  ├── Database: Mumtaz_ERP
  ├── Admin user: umer@mumtaz.digital
  └── Custom addons: /opt/custom_addons/Mumtaz/addons/
```

---

## Auth Flow (Unified SSO)

```
Signup (app.mumtaz.digital)
  1. POST /api/v1/auth/signup → ZAKI server
  2. ZAKI server calls Odoo XML-RPC → creates res.users record
  3. ZAKI server calls Odoo XML-RPC → creates mumtaz.tenant record (draft)
  4. ZAKI server caches user in SQLite (DB_PATH=/opt/zaki-server/users.db)
  5. Returns JWT (30-day, HS256) containing: sub, email, name, company, odoo_uid, tenant_id, plan

Login (any product)
  1. POST /api/v1/auth/login → ZAKI server
  2. ZAKI server authenticates against Odoo first (xmlrpc.client)
  3. Falls back to SQLite bcrypt check if Odoo unreachable
  4. Returns same JWT format

Same credentials work at erp.mumtaz.digital (Odoo login) because signup
creates a real Odoo user with the same email + password.
```

---

## Repository Structure

```
Mumtaz/
├── addons/                          Odoo custom modules
│   ├── mumtaz_tenant_manager/       Core tenant registry (mumtaz.tenant model)
│   ├── mumtaz_control_plane/        Subscription health, commercial visibility on tenant
│   ├── mumtaz_sme_profile/          SME business profile per tenant
│   ├── mumtaz_cfo_workspace/        ZAKI CFO workspace model
│   ├── mumtaz_brand/                White-label brand profiles
│   └── mumtaz_marketplace/          Marketplace Odoo module
│
├── apps/
│   ├── portal/index.html            Customer portal (single-file SPA)
│   │                                 — 5-step onboarding wizard
│   │                                 — Real JWT auth via ZAKI server
│   │                                 — Dashboard, modules, users, billing, white-label, settings
│   ├── zaki-server/
│   │   ├── main.py                  FastAPI auth + AI API (runs on VPS port 8001)
│   │   ├── requirements.txt
│   │   └── create_user.py           CLI tool to seed admin users
│   ├── marketplace/
│   │   ├── index.html               Public B2B storefront (no login)
│   │   └── vendor.html              Vendor/supplier portal (JWT auth)
│   ├── zaki/                        ZAKI AI CFO Next.js app + Python backend
│   └── website/                     Marketing website static pages
│
└── ops/
    └── deployment/
        ├── nginx-mumtaz-platform.conf   Unified nginx config (all domains)
        ├── zaki-server.service          systemd unit for ZAKI FastAPI server
        └── setup-zaki-server.sh         One-shot VPS setup script
```

---

## Odoo Modules (addons/)

### `mumtaz_tenant_manager`
Central model: `mumtaz.tenant` — one record per customer organisation.

Key fields: `name`, `code`, `database_name`, `subdomain`, `state` (draft/provisioning/active/suspended/archived), `bundle_id`, `admin_email`, `subscription_start`, `subscription_end`, `brand_id`, `partner_id`

State transitions: draft → provisioning → active → suspended → archived

### `mumtaz_control_plane`
Adds commercial/subscription visibility to the tenant form and list views.

Computed fields on `mumtaz.tenant`: `cp_subscription_health`, `cp_subscription_status`, `cp_plan_name`, `cp_renewal_date`, `cp_grace_days_remaining`, `cp_quota_usage_summary`

Buttons: Open Subscription, Reactivate Sub, Extend Grace

### `mumtaz_sme_profile`
Model: `mumtaz.sme.profile` — business profile attached to a tenant.

Fields: `tenant_id`, `company_id`, `legal_name`, `onboarding_stage`, `activation_status`, `brand_id`

### `mumtaz_cfo_workspace`
Model: `mumtaz.cfo.workspace` — ZAKI CFO workspace per SME.

### `mumtaz_brand`
Model: `mumtaz.brand` — white-label brand configuration (logo, colours, domain).

---

## ZAKI Server (`apps/zaki-server/main.py`)

FastAPI v2 — unified auth + AI API for all Mumtaz products.

**Config (read from `/opt/zaki-server/.env`):**
```
JWT_SECRET=<32-byte hex>
ANTHROPIC_API_KEY=<key>
DB_PATH=/opt/zaki-server/users.db
ODOO_URL=http://127.0.0.1:8069
ODOO_DB=Mumtaz_ERP
ODOO_ADMIN_USER=umer@mumtaz.digital
ODOO_ADMIN_PASS=<odoo admin password>
```

**SQLite schema (`users` table):**
`id, email, password_hash, name, company, odoo_uid, tenant_id, plan, active, created_at`

**JWT payload:** `{ sub, email, name, company, odoo_uid, tenant_id, plan, exp }`

---

## Portal (`apps/portal/index.html`)

Single-file SPA. No build step. State stored in `localStorage` key `mumtaz_portal_v2`. JWT stored under `mumtaz_token`.

**Onboarding wizard (5 steps, shown after signup):**
1. Company profile (name, industry, country, team size)
2. Product selection (ERP, ZAKI AI CFO, Marketplace)
3. ERP modules (8 core free + premium add-ons)
4. Plan selection (Starter $149 / Growth $399 / Enterprise $999)
5. Review & Launch

**App panels:** Dashboard, Modules, Users & Teams, Billing & Plans, White Label, Settings, Support

---

## Marketplace (`apps/marketplace/`)

### `index.html` — Public B2B Storefront
- No login required to browse
- Search suppliers by category
- Submit RFQ (Request for Quote) via modal
- Categories: Manufacturing, IT, Logistics, Raw Materials, Construction, Food & Beverage, Healthcare, Professional Services, and more
- Featured verified suppliers with ratings

### `vendor.html` — Vendor/Supplier Portal
- Auth: POST `/api/v1/auth/login` + `/auth/register` → ZAKI server JWT
- Dashboard: listings, RFQ inbox, analytics, company profile
- Manage product/service listings with status toggles
- Handle incoming RFQs from buyers

---

## Deployment (VPS)

**Server:** Ubuntu VPS, nginx, Odoo 16/17, PostgreSQL

### Deploy portal:
```bash
cd /opt/custom_addons/Mumtaz
git fetch origin claude/odoo-architecture-review-ujm0W
git checkout origin/claude/odoo-architecture-review-ujm0W -- apps/portal/index.html
mkdir -p /var/www/app.mumtaz.digital
cp apps/portal/index.html /var/www/app.mumtaz.digital/
```

### Deploy marketplace:
```bash
git checkout origin/claude/odoo-architecture-review-ujm0W -- apps/marketplace/
mkdir -p /var/www/marketplace.mumtaz.digital
cp apps/marketplace/index.html apps/marketplace/vendor.html /var/www/marketplace.mumtaz.digital/
```

### Deploy ZAKI server:
```bash
bash ops/deployment/setup-zaki-server.sh
# Then edit /opt/zaki-server/.env with real API keys
systemctl restart zaki-server
curl http://127.0.0.1:8001/health
```

### Deploy nginx config:
```bash
cp ops/deployment/nginx-mumtaz-platform.conf /etc/nginx/sites-available/mumtaz
ln -sf /etc/nginx/sites-available/mumtaz /etc/nginx/sites-enabled/mumtaz
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

### Update marketplace nginx block:
The current nginx config for `marketplace.mumtaz.digital` redirects to Odoo.
**Change it** to serve the static files instead:
```nginx
server {
    listen 80;
    server_name marketplace.mumtaz.digital;
    root /var/www/marketplace.mumtaz.digital;
    index index.html;
    location / { try_files $uri $uri/ /index.html; add_header Cache-Control "no-cache"; }
    location ~* \.(css|js|png|jpg|ico|woff2?)$ { expires 30d; }
}
```

---

## Known Issues / Pending

| Item | Status |
|---|---|
| `mumtaz_control_plane` xpath install error | Fixed — xpath changed from `//group[@name='subscription_group']` to `//notebook` |
| ZAKI server `odoo_live: false` | Fixed — correct DB `Mumtaz_ERP`, admin `umer@mumtaz.digital` |
| Portal blank page after signup | Old nginx config proxied all paths to Odoo; new nginx config fixes this — redeploy nginx on VPS |
| Marketplace nginx | Needs updating to serve static files (see above) |
| Odoo custom modules install | Run from Odoo web UI (Settings → Activate developer mode → Apps → Update list) |
| SSL certificates | Run certbot after DNS propagates for all domains |

---

## Development Branch

All active development: `claude/odoo-architecture-review-ujm0W`
