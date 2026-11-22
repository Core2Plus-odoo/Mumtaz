# app.mumtaz.digital

Customer portal: signup, onboarding, billing, admin pages. Static HTML that calls a back-end API.

| | |
|---|---|
| **Status** | **Orphaned.** The API these pages call (`zaki-server`) was deleted from the repo in July 2026 (commit `48a2cf9`). Whether it still runs on the server is unknown |
| **Code in this folder** | [`portal/`](portal/) — 12 static pages, nginx config, deploy script (moved from `apps/portal/`) |
| **Database** | SQLite `users.db` on the server (accounts and tenant list), reached through the deleted API |
| **Served by** | nginx, web root `/var/www/app.mumtaz.digital`; `/api/` proxied to port 8002 |
| **Deploy** | `portal/deploy.sh` or `ops/deployment/deploy-website.sh` |

> Server facts below are **reported** (from owner-run output recorded in this repo, Oct–Nov 2026) and have not been re-verified. See the [audit pack](../../docs/infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md).

## What the server check of 22 Nov 2026 showed

nginx does **not** serve this hostname from `/var/www/app.mumtaz.digital`. Its root is `/opt/mumtaz/platform/frontend`: the control-panel front end of the `platform/` rebuild, copied there by `platform/ops/install/05-cutover.sh`. The source of that control panel (`platform/control-panel/`) is on the production branch `claude/resume-help-95ne9v` and was deleted from `main`. A second check the same day showed its back end on port 8002 **is running** and its database holds 2 tenants. The 12 static pages in `portal/` are therefore not what visitors see.

## The control plane is not this folder

The SaaS control plane (tenants, products, plans, subscriptions, entitlements,
provisioning, registration requests) is Odoo code in
`addons/mumtaz_tenant_manager` and `addons/mumtaz_control_plane`. Since
21 Nov 2026 it carries a tested journey from registration to an isolated
staging ERP database (`scripts/tenant_journey_ci.sh`). It has not been run on
any server, and which Odoo instance should host it is undecided (decision
P-02). See [`docs/platform/MUMTAZ_SAAS_CONTROL_PLANE.md`](../../docs/platform/MUMTAZ_SAAS_CONTROL_PLANE.md).

## Open points

- Product decision needed: rebuild the back end or retire the portal (audit decision D-08).
- Stored-XSS risk in the admin console and tokens kept in browser storage (APP-06).
- Five different nginx definitions for this hostname exist across the repo.
