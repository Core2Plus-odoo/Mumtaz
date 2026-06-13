# Mumtaz Platform — Clean Rebuild (per Super Prompt)

Canonical rebuild of the Mumtaz Digital SaaS ERP platform, built in the repo and
provisioned on the VPS. Authored to the super-prompt **architecture**, with three
deliberate overrides agreed with the owner:

1. **Brand = Mumtaz ivory/gold/Inter** (not the spec's teal/navy/Cormorant).
   - `--paper #FAF8F4`, `--gold #B8862A` / `#D4A84C`, `--ink #1C1917`, font **Inter**, mark **م**.
2. **No hardcoded secrets.** Everything in `/opt/mumtaz/.env` (gitignored); `.env.example` only.
   - Installer auto-generates `JWT_SECRET`; super-admin password is read from `.env` and bcrypt-hashed at bootstrap.
3. **Dynamic, not hardcoded.** Products & pricing live in the `module_catalogue` DB table
   (editable via control panel), never in app code.

## Architecture
- `mumtaz.digital` — marketing site (static)
- `app.mumtaz.digital` — control panel; one codebase, two roles (super-admin / tenant-admin)
- `erp.mumtaz.digital` — Odoo 19 CE, **one DB per tenant**, `db_filter=^%d$` isolation
- `zaki.mumtaz.digital` — ZAKI AI CFO (FastAPI + 8-panel UI + ElevenLabs voice)

Tenant types: **business** (`corp_{slug}`), **org** (white-label reseller, `org_{slug}`),
**org_sme** (SME inside an org's Odoo DB, multi-company).

## Repo layout
```
platform/
  db/        schema.sql, seed_catalogue.sql        ← Phase 0 ✅
  ops/       .env.example, install/, nginx/, systemd/, scripts/
  marketing/         mumtaz.digital               ← Phase 1
  odoo/addons/       custom Odoo 19 modules        ← Phase 2
  zaki/{backend,frontend}                          ← Phase 3
  control-panel/{backend,frontend}                 ← Phase 4
```

## Build phases (each committed; VPS verifies)
- **Phase 0 — Foundation** ✅ schema, dynamic module catalogue, `.env` model, `00-foundation.sh`
- **Phase 1 — Marketing** `mumtaz.digital` (ivory/gold/Inter)
- **Phase 2 — Odoo** install + custom addons (branding, einvoicing, crm_starter, marketplace, zaki connector), `db_filter` isolation
- **Phase 3 — ZAKI** FastAPI backend (snapshot, briefing/chat stream, voice, health, KB) + 8-panel UI
- **Phase 4 — Control panel** FastAPI (auth/JWT, admin/* + tenant/* routes, dynamic catalogue, provisioning, billing, impersonation) + frontend
- **Phase 5 — Cutover** nginx + systemd + activation (backups first; deliberate switch from the current stack)
- **Phase 6 — Ops** backup, healthcheck, cron, cert renew

## Run Phase 0 (VPS, as root)
```bash
cd /opt/custom_addons/Mumtaz && git pull origin main      # or wherever the repo is cloned
cp platform/ops/.env.example /opt/mumtaz/.env             # then edit: set DB_PASS, SUPER_ADMIN_PASSWORD, ODOO_* , API keys
bash platform/ops/install/00-foundation.sh
```

> **Cutover safety:** Phases 0–4 are additive and do **not** disturb the currently-live
> services or nginx. Phase 5 is the only destructive step and runs only after full backups.
