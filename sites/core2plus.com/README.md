# core2plus.com

The group's own CRM and internal ERP (Odoo 19 Community). 41 users, about 41,000 leads.

| | |
|---|---|
| **Status** | **Production** (reported) |
| **Code on `main`** | [`addons/c2p_project_tracker/`](../../addons/c2p_project_tracker/), [`addons/c2p_command_center/`](../../addons/c2p_command_center/), and — brought in from the production branch and the server by PR #180, as found, with review item REVIEW-05 open — [`addons/c2p_appointment/`](../../addons/c2p_appointment/), [`addons/c2p_proposal/`](../../addons/c2p_proposal/), [`addons/c2p_master_agent/`](../../addons/c2p_master_agent/) |
| **Still not on `main`** | 25 business rules stored only in the CRM database · anything else installed on the server that PR #180 did not cover (confirm with the server check) |
| **Database** | `Mumtaz_C2P` (PostgreSQL) |
| **Service** | `odoo4` on port 8075 |
| **Connected tool** | The delivery console ([`delivery.mumtaz.digital`](../delivery.mumtaz.digital/)) holds a stored connection to this database |
| **Deploy** | By hand. Install guide: [`addons/c2p_project_tracker/scripts/backup_and_install.md`](../../addons/c2p_project_tracker/scripts/backup_and_install.md) |

> Server facts below are **reported** (from owner-run output recorded in this repo, Oct–Nov 2026) and have not been re-verified. See the [audit pack](../../docs/infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md).

## Open points

- No backup found. A restored copy will email real contacts unless neutralised first.
- A second Odoo service (port 8069) is also bound to this database (F-07).
- The server-only modules are now in git (PR #180); they still need review (REVIEW-05). The database-stored rules are not yet in git (backlog O-03).
