# myfaizy.com

Faizy: a family-care service for Pakistanis abroad. A **separate product** on its own Odoo 19 instance.

| | |
|---|---|
| **Status** | **Production** (reported) |
| **Code on `main`** | [`faizy/`](../../faizy/) — `faizy_core`, `faizy_website`, docs, deploy scripts. **This copy is behind production** |
| **Code production runs** | Branch `claude/repo-audit-faizy-instance-fck6o3` (37 commits ahead; adds `faizy_ai`) |
| **Database** | `faizy_prod` (PostgreSQL, its own login) |
| **Service** | `faizy-odoo`, own OS user, loopback ports |
| **Deploy** | Documented one-line command in `faizy/CLAUDE.md` on the production branch |
| **CI** | `faizy-ci.yml` |

**Not moved.** Five open branches and three open pull requests edit `faizy/`; moving it now would conflict with all of them. Recommended home: its own private repository.

> Server facts below are **reported** (from owner-run output recorded in this repo, Oct–Nov 2026) and have not been re-verified. See the [audit pack](../../docs/infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md).

## Open points

- Any signed-in customer can read every family's identity documents (audit ODOO-06). One access rule fixes it.
- Backups not documented.
