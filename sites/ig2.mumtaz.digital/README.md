# ig2.mumtaz.digital

**Client system.** Accounting for a client media agency and its sister company (two legal entities in one Odoo 19 database). Treat as client-confidential.

| | |
|---|---|
| **Status** | **Production client data, no staging copy** (reported) |
| **Code** | Not on `main` (PR #180 deliberately left the IG2 modules out). Branch `claude/resume-help-95ne9v`: `c2p_pk_vouchers` and the IG2 financial reports, plus the third-party `base_accounting_kit` installed on the server |
| **Database** | `Mumtaz_IG2` (PostgreSQL) |
| **Service** | `odoo3` on port 8071 |
| **Deploy** | By hand: `git pull`, then `-u` on the live database |

> Server facts below are **reported** (from owner-run output recorded in this repo, Oct–Nov 2026) and have not been re-verified. See the [audit pack](../../docs/infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md).

## Open points — the most urgent in the repo

- Used over an **unencrypted connection on a raw port**, bypassing nginx (audit F-01). Put it behind HTTPS on this hostname, then close the port.
- No backup found (F-02).
- The third-party accounting kit has not had the hardening that was written for the Pharma tenant (F-15).
- This client's code should live in its own private repository.
