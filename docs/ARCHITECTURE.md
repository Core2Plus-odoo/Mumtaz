# Mumtaz Platform — Architecture & Operations

> Multi-tenant SaaS ERP for the UAE / GCC + Pakistan. Odoo Community is the
> engine; a thin services layer and a friendly portal make it easy to use.

---

## 1. Domains & what serves them

| Domain | Serves | Source | Web root / upstream |
|---|---|---|---|
| `mumtaz.digital` | Marketing website | `apps/website/` | `/var/www/mumtaz.digital` |
| `app.mumtaz.digital` | Portal hub (login, dashboard, app toggles) | `apps/portal/` | `/var/www/app.mumtaz.digital` |
| `marketplace.mumtaz.digital` | B2B marketplace + vendor portal | `apps/marketplace/` | `/var/www/marketplace.mumtaz.digital` |
| `erp.mumtaz.digital` | Odoo ERP (per-tenant) | Odoo Community + `addons/` | proxy → `127.0.0.1:8069` (web), `:8072` (longpoll) |
| `zaki.mumtaz.digital` | ZAKI AI landing | `apps/zaki/static/` | `/var/www/zaki.mumtaz.digital` |
| `admin.mumtaz.digital` | Control-plane (restricted) | Odoo backend | proxy → Odoo, customer routes blocked |

The static sites are plain HTML/CSS/JS. The **platform API** is `zaki-server`
(FastAPI, `127.0.0.1:8002`), reverse-proxied under `/api/` on the `app`,
`marketplace`, and `zaki` subdomains.

---

## 2. Multi-tenancy model

**One isolated Odoo database per tenant.** This is the strongest isolation
boundary — important for UAE/GCC + Pakistan data-residency and compliance.

- `zaki-server` holds the central **auth + tenant registry** (`users`,
  `tenants` tables). Each user row carries `tenant_db` (their Odoo DB name)
  and `odoo_uid`.
- Every Odoo call from the API is scoped to the user's `tenant_db` — there is
  no cross-tenant query path.
- New tenants should be provisioned by **cloning a template DB** that already
  has the curated module set installed (seconds), rather than installing
  modules fresh per signup (slow, fragile).

---

## 3. Components

### `zaki-server` (FastAPI, `:8002`) — the platform API
Single auth backend for all products. Responsibilities:
- JWT auth (`/api/v1/auth/*`), `require_auth` dependency.
- Tenant provisioning & status (`/api/v1/tenant/*`).
- Odoo XML-RPC bridge (`odoo_get_admin_uid`, `_odoo_object`, `execute_kw`).
- App enable/disable (control-plane feature toggles).
- ERP ↔ Marketplace endpoints (product import, listings).
- ZATCA e-invoicing, billing, mail, settings.

> **Deploy unit:** `/opt/zaki-server` (systemd `zaki-server`). Code changes
> require a service restart — static deploys do **not** pick them up.

### Odoo addons (`addons/`)
- `mumtaz_theme` — backend/login rebranding (favicon, login CSS, fonts).
- `mumtaz_tenant_manager` — `mumtaz.tenant` registry (one record per DB).
- `mumtaz_control_plane` — features, plans, subscriptions, usage, and the
  `mumtaz.feature.access.service` resolver. **The source of truth for which
  apps a tenant may use.**
- `mumtaz_marketplace` — `mumtaz.marketplace.listing` / `.category` /
  `.inquiry`, plus product/sale/purchase integration.
- `mumtaz_sme_profile` — SME onboarding profile.

---

## 4. App enable/disable (control plane)

**Rule: enable/disable is a feature flag, never an Odoo module
install/uninstall.** Uninstalling a module deletes its data and causes
downtime; flags are instant, reversible, and safe.

How it resolves (`mumtaz.feature.access.service`):
```
effective_enabled = plan grant (mumtaz.plan.feature)
                    then tenant override (mumtaz.tenant.feature):
                      force_on  → enabled
                      force_off → disabled
                      inherit   → plan default
```

Portal flow:
```
app.mumtaz.digital (toggle app card)
   │  PUT /api/v1/tenant/features { code, enabled }   (JWT)
   ▼
zaki-server ──XML-RPC──► tenant's Odoo DB
   │   upsert mumtaz.tenant.feature → force_on / force_off
   ▼
GET /api/v1/tenant/features reflects state (apps ON by default;
only an explicit force_off disables — fails open if unprovisioned)
```

Baseline app features are seeded in
`addons/mumtaz_control_plane/data/feature_baseline.xml`:
`erp_access`, `zaki_access`, `marketplace_access`.

> **TODO (server-side enforcement):** hiding a menu is cosmetic. A disabled
> app must also revoke the relevant Odoo security group / add an `ir.rule`
> so it's unreachable via direct URL/API. Reuse the
> `_ensure_marketplace_access` pattern (raise if disabled) on each gated app.

---

## 5. ERP ↔ Marketplace integration

Vendors turn their Odoo catalogue into marketplace listings:

- `GET /api/v1/erp/products` — sellable products (`sale_ok=True`) from the
  tenant's Odoo DB. Gated on ERP enablement; fails open as `erp_enabled:false`.
- `POST /api/v1/erp/listings/import` `{ product_ids, moq, lead_days }` —
  creates `mumtaz.marketplace.listing` records (state `draft`). Re-reads
  product data server-side (never trusts client prices), find-or-creates a
  default category, and **dedupes by product template** so re-import is safe.
- `GET /api/v1/erp/listings` — the tenant's real listings for the vendor
  portal's "My Listings" table.

All three are tenant-scoped and catch every exception with a generic message.

---

## 6. API reference (platform endpoints added/used here)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/tenant/features` | App enable/disable state for the tenant |
| PUT | `/api/v1/tenant/features` | Toggle an app (`{code, enabled}`) |
| GET | `/api/v1/erp/products` | Sellable Odoo products (for import) |
| GET | `/api/v1/erp/listings` | Tenant's marketplace listings |
| POST | `/api/v1/erp/listings/import` | Create listings from products |

All require `Authorization: Bearer <JWT>` and resolve the tenant from the
authenticated user.

---

## 7. nginx vhost model

- HTTP-only server blocks live in `ops/deployment/nginx-mumtaz-platform.conf`;
  **certbot adds the `listen 443 ssl` blocks live, per domain.**
- A subdomain only works over HTTPS once it has **both** a server block named
  for it **and** a cert. If either is missing, the request falls back to the
  default 443 vhost (you'll see the wrong site, e.g. the app login).
- `marketplace.mumtaz.digital` uses a **standalone** vhost
  (`ops/deployment/nginx-marketplace.conf`) that references its own cert, so it
  doesn't disturb certbot's blocks for `app`/`erp`/`zaki`.

---

## 8. Deploy runbook

Run on the VPS as root. Repo lives at `/opt/custom_addons/Mumtaz`.

**Static sites only** (website, portal, marketplace, zaki landing):
```bash
bash /opt/custom_addons/Mumtaz/ops/deployment/deploy-website.sh
```

**Platform API** (after any `apps/zaki-server/` change — required for the
feature-toggle and ERP/marketplace endpoints):
```bash
bash /opt/custom_addons/Mumtaz/ops/deployment/setup-zaki-server.sh
# restarts the zaki-server systemd unit
```

**Odoo addons** (after any `addons/` change — required to load new models or
seed data such as `feature_baseline.xml`):
```bash
bash /opt/custom_addons/Mumtaz/ops/deployment/deploy.sh
# upgrades mumtaz_theme, mumtaz_sme_profile, mumtaz_control_plane, mumtaz_marketplace
```
> In production each **tenant DB** must receive the addon upgrade. The single
> `deploy.sh` upgrades one DB (`Mumtaz_ERP`); for many tenants, iterate the
> `-u ...` upgrade across every `tenant_db`.

**New subdomain HTTPS:** ensure DNS → VPS, a server block exists, then
`certbot --nginx -d <sub>.mumtaz.digital` (or reference an existing cert via a
standalone vhost, as marketplace does).

---

## 9. Security invariants (do not regress)

- Secrets via env only (`JWT_SECRET`, `ANTHROPIC_API_KEY`, `ODOO_ADMIN_PASS`,
  `DATABASE_URL`). Never commit `.env`; startup crashes on default `JWT_SECRET`.
- PostgreSQL in production (`DATABASE_URL`); SQLite only for local dev.
- Every tenant-data query scoped to the tenant; no `SELECT *` without a filter.
- Catch all exceptions at API boundaries; return generic messages externally.
- Odoo: never modify core models directly — always `_inherit`, `mumtaz.` prefix.
- ZATCA changes cross-checked against Phase 2 spec; never stub production calls.
- CORS from an explicit `CORS_ORIGINS` allowlist — never `*`.
- ANSI upsert (`ON CONFLICT`); never SQLite-only `INSERT OR REPLACE/IGNORE`.
