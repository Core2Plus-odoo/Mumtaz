# erp.mumtaz.digital (and admin.mumtaz.digital)

The Mumtaz platform ERP: Odoo 19 Community with the platform modules.

| | |
|---|---|
| **Status** | Production (reported). Which Odoo service answers this hostname is **unverified** |
| **Code** | Platform modules in [`addons/`](../../addons/) — the 37 `mumtaz_*` modules that are not `mumtaz_jewellery*`. Not moved: the server's Odoo `addons_path` points at that folder |
| **Code in this folder** | [`legacy-spa/`](legacy-spa/) — an abandoned custom ERP page and deploy script for a back end that was deleted (moved from `apps/erp/`). Not Odoo; kept for reference only |
| **Database** | `Mumtaz_ERP` (PostgreSQL) |
| **Service** | `odoo2` on port 8070, or `odoo` on port 8069 — records conflict |
| **Routing configs** | [`ops/deployment/`](../../ops/deployment/), [`ops/platform-routing/`](../../ops/platform-routing/) |
| **Deploy** | By hand: `git pull`, then `odoo -u <modules>`. No tested pipeline |

> Server facts below are **reported** (from owner-run output recorded in this repo, Oct–Nov 2026) and have not been re-verified. See the [audit pack](../../docs/infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md).

## Open points

- The service on port 8069 is pinned to the **CRM** database, so this hostname may be opening the wrong database (audit F-07).
- Live-update traffic for this hostname is routed to the Jewel demo container.
- Cross-tenant sign-on flaw and finance data exposed to any logged-in user (ODOO-01, -04, -05).
