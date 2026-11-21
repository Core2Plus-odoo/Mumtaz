# core2plus.com

The group's own CRM and internal ERP (Odoo 19 Community). 41 users, about 41,000 leads.

| | |
|---|---|
| **Status** | **Production** (reported) |
| **Code on `main`** | [`addons/c2p_project_tracker/`](../../addons/c2p_project_tracker/), [`addons/c2p_command_center/`](../../addons/c2p_command_center/) |
| **Code not on `main`** | `c2p_proposal`, `c2p_appointment`, `c2p_pk_vouchers` on branch `claude/resume-help-95ne9v` · `c2p_agents` in PR #131 · `c2p_master_agent` installed on the server with no source in git · 25 business rules stored only in the database |
| **Database** | `Mumtaz_C2P` (PostgreSQL) |
| **Service** | `odoo4` on port 8075 |
| **Connected tool** | The delivery console ([`delivery.mumtaz.digital`](../delivery.mumtaz.digital/)) holds a stored connection to this database |
| **Deploy** | By hand. Install guide: [`addons/c2p_project_tracker/scripts/backup_and_install.md`](../../addons/c2p_project_tracker/scripts/backup_and_install.md) |

> Server facts below are **reported** (from owner-run output recorded in this repo, Oct–Nov 2026) and have not been re-verified. See the [audit pack](../../docs/infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md).

## Open points

- No backup found. A restored copy will email real contacts unless neutralised first.
- A second Odoo service (port 8069) is also bound to this database (F-07).
- Bring every C2P module and the database-stored rules into git (backlog O-03, O-04).
