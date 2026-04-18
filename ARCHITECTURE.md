# Mumtaz Platform — Architecture

## Addon Dependency Graph

```
mumtaz_tenant_manager          (base: mail, base)
    ├── mumtaz_control_plane   (extends mumtaz.tenant with subscription/commercial fields)
    ├── mumtaz_sme_profile     (mumtaz.sme.profile → links to mumtaz.tenant)
    │       └── mumtaz_cfo_workspace  (mumtaz.cfo.workspace → links to mumtaz.sme.profile)
    └── mumtaz_brand           (mumtaz.brand → referenced by mumtaz.tenant + mumtaz.sme.profile)

mumtaz_marketplace             (standalone, optional Odoo module)
```

## Data Flow Between Modules

```
Customer signs up at app.mumtaz.digital
    │
    ▼
ZAKI Server (FastAPI, port 8001)
    ├── XML-RPC → Odoo: create res.users (email, name, password)
    ├── XML-RPC → Odoo: create mumtaz.tenant (name, code, database_name, admin_email, state=draft)
    ├── SQLite:  cache user row (email, odoo_uid, tenant_id, plan)
    └── Return JWT

JWT contains: { sub, email, name, company, odoo_uid, tenant_id, plan, exp }
    │
    ├── Portal uses JWT for all /api/v1/* calls
    ├── ZAKI CFO uses same JWT (same ZAKI server)
    └── Odoo login uses same email+password (created in Odoo during signup)

Odoo Control Plane (admin.mumtaz.digital)
    └── mumtaz.tenant record
            ├── state: draft → provisioning → active → suspended → archived
            ├── bundle_id → mumtaz.module.bundle (which Odoo modules to install)
            ├── brand_id  → mumtaz.brand (white-label config)
            └── partner_id → res.partner (white-label owner/reseller)
```

## Multi-Tenant Provisioning Workflow

```
1. Signup (app.mumtaz.digital)
   └── ZAKI server creates mumtaz.tenant with state=draft

2. Admin Review (admin.mumtaz.digital → Odoo backend)
   └── Platform admin opens mumtaz.tenant record
       ├── Fills in: bundle_id, database_name, brand_id (if white-label)
       └── Clicks "Provision Tenant" → state=provisioning

3. Provisioning
   └── Triggers mumtaz.provision.wizard
       ├── Creates new PostgreSQL database
       ├── Installs Odoo + selected bundle modules
       ├── Creates admin user in tenant DB
       └── Sets state=active, records provisioned_on timestamp

4. Active Tenant
   └── Tenant accesses their Odoo at subdomain (e.g. acme.mumtaz.io)
       ├── ZAKI CFO connects via erp_api_key
       └── Marketplace profile linked to tenant
```

## Module: mumtaz_tenant_manager

**Model:** `mumtaz.tenant`

| Field | Type | Purpose |
|---|---|---|
| `name` | Char | Display name of org |
| `code` | Char | Slug: `[a-z0-9][a-z0-9_-]{1,28}[a-z0-9]` |
| `database_name` | Char | PostgreSQL DB name: `[a-z][a-z0-9_]{1,62}` |
| `subdomain` | Char | Subdomain prefix |
| `custom_domain` | Char | Fully-qualified custom domain |
| `state` | Selection | draft/provisioning/active/suspended/archived |
| `bundle_id` | Many2one | → mumtaz.module.bundle |
| `brand_id` | Many2one | → mumtaz.brand |
| `partner_id` | Many2one | → res.partner (reseller) |
| `admin_email` | Char | Initial admin user email |
| `subscription_start` | Date | |
| `subscription_end` | Date | |
| `provision_log` | Text | Append-only provisioning log |

**Actions:**
- `action_start_provisioning()` — draft → provisioning
- `action_mark_active()` — → active
- `action_suspend()` — → suspended
- `action_archive_tenant()` — → archived, active=False
- `action_open_provision_wizard()` — opens mumtaz.provision.wizard
- `action_create_sme_profile()` — creates mumtaz.sme.profile
- `action_create_cfo_workspace()` — creates mumtaz.cfo.workspace
- `action_run_smoke_tests()` — verifies SME profiles + workspaces exist

## Module: mumtaz_control_plane

Extends `mumtaz.tenant` with subscription health fields (computed, read-only on the form).

**Computed fields added to mumtaz.tenant:**
- `cp_subscription_health` — badge (healthy/warning/critical)
- `cp_subscription_status` — badge (active/grace/expired/trial)
- `cp_plan_name` — plan display name
- `cp_renewal_date` — next renewal date
- `cp_grace_days_remaining` — days left in grace period
- `cp_quota_usage_summary` — text summary of quota usage

**Buttons added to mumtaz.tenant form:**
- Open Subscription, Reactivate Sub, Extend Grace

**View inheritance:** Extends `mumtaz_tenant_manager.mumtaz_tenant_form_view` and `mumtaz_tenant_list_view`.

## Module Organization

```
addons/
├── mumtaz_tenant_manager/
│   ├── models/
│   │   ├── mumtaz_tenant.py          Main tenant model
│   │   ├── mumtaz_module_bundle.py   Bundle definition
│   │   └── mumtaz_provision_wizard.py Provisioning wizard
│   ├── views/
│   │   ├── mumtaz_tenant_views.xml
│   │   └── mumtaz_module_bundle_views.xml
│   ├── security/
│   │   ├── ir.model.access.csv
│   │   └── mumtaz_security.xml       Groups: platform_admin, tenant_manager
│   └── __manifest__.py
│
├── mumtaz_control_plane/
│   ├── models/
│   │   └── mumtaz_tenant_commercial.py  Computed subscription fields
│   ├── views/
│   │   └── tenant_commercial_views.xml  Form/list view extensions
│   └── __manifest__.py
│
├── mumtaz_sme_profile/
│   ├── models/mumtaz_sme_profile.py
│   └── __manifest__.py
│
├── mumtaz_cfo_workspace/
│   ├── models/mumtaz_cfo_workspace.py
│   └── __manifest__.py
│
└── mumtaz_brand/
    ├── models/mumtaz_brand.py
    └── __manifest__.py
```

## ZAKI Server API

Base URL: `https://zaki.mumtaz.digital/api/v1`

```
POST /auth/signup          Register + create Odoo user + mumtaz.tenant
POST /auth/register        Alias for /signup (ZAKI CFO frontend compat)
POST /auth/login           Validate via Odoo XML-RPC → JWT
GET  /auth/me              Profile from JWT + SQLite
GET  /tenant/me            mumtaz.tenant data from Odoo
POST /ai/chat/stream       SSE streaming chat via Claude (claude-sonnet-4-5)
GET  /health               { status, ai_ready, odoo_live, odoo_url, odoo_db }
```

JWT signed with `HS256`, 30-day expiry. Payload:
```json
{ "sub": "1", "email": "...", "name": "...", "company": "...",
  "odoo_uid": 5, "tenant_id": 3, "plan": "trial", "exp": 1234567890 }
```

## Infrastructure

```
VPS (Ubuntu)
├── nginx (port 80/443)
│   ├── mumtaz.digital         → /var/www/mumtaz.digital (static)
│   ├── app.mumtaz.digital     → /var/www/app.mumtaz.digital (static SPA)
│   ├── erp.mumtaz.digital     → proxy 127.0.0.1:8069 (Odoo)
│   ├── zaki.mumtaz.digital    → /var/www/zaki.mumtaz.digital (static)
│   │                             + /api/ → proxy 127.0.0.1:8001
│   ├── marketplace.mumtaz.digital → /var/www/marketplace.mumtaz.digital (static)
│   └── admin.mumtaz.digital   → proxy 127.0.0.1:8069 (Odoo backend)
│
├── Odoo (port 8069, user: odoo)
│   ├── Database: Mumtaz_ERP
│   ├── Longpolling: port 8072
│   └── Custom addons: /opt/custom_addons/Mumtaz/addons/
│
├── PostgreSQL (user: odoo)
│   └── Mumtaz_ERP database
│
├── ZAKI Server (port 8001, systemd: zaki-server)
│   ├── /opt/zaki-server/main.py
│   ├── /opt/zaki-server/.env
│   ├── /opt/zaki-server/users.db   (SQLite cache)
│   └── /opt/zaki-server/venv/
│
└── Git repo: /opt/custom_addons/Mumtaz (branch: claude/odoo-architecture-review-ujm0W)
```
