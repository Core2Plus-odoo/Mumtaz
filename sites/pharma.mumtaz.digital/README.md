# pharma.mumtaz.digital

Pharma ERP staging tenant: Odoo 19 Community with `pharma_*` modules and fictional demo data.

| | |
|---|---|
| **Status** | Staging, neutralised (no outgoing mail, jobs off) — reported live since 18 Nov 2026 |
| **Code** | **Not on `main`.** Branches `pharma-erp-v0.1`, `pharma-reversal`, `pharma-functionality`, `pharma-hide-cybrosys`: `addons/pharma_*`, `deploy/pharma-staging/`, `docs/pharma/` |
| **Database** | `mumtaz_pharma` (PostgreSQL) |
| **Service** | `odoo-pharma` on ports 8076/8077 (loopback) |
| **Deploy** | `deploy/pharma-staging/stage.sh` on its branch: backup first, gated steps, printed rollback. Full record in `docs/pharma/DEPLOY_LOG.md` on that branch |

> Server facts below are **reported** (from owner-run output recorded in this repo, Oct–Nov 2026) and have not been re-verified. See the [audit pack](../../docs/infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md).

## Open points

- Four unmerged branches and no pull request. Recommended home: its own private repository.
- Shares the database login used by production systems (audit F-06).
