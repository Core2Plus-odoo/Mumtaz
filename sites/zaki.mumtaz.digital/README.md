# zaki.mumtaz.digital

ZAKI, the AI CFO assistant. Three rival implementations exist.

**Server check, 22 Nov 2026:** nginx serves this hostname from `/opt/mumtaz/zaki/frontend`, which is the front end of the third implementation (`platform/zaki/`), copied there by `platform/ops/install/05-cutover.sh`. Neither `static/` nor `node-app/` in this folder is what visitors see. The matching back end (`platform/zaki/backend`, port 8001) is the one the security review found to have no authentication and one Odoo administrator for every tenant (audit APP-01, APP-02); whether that service is running is the next check.

| | |
|---|---|
| **Status** | Unknown. Needs a product decision before any of these is exposed |
| **Code in this folder** | [`static/`](static/) — single-page app (moved from `apps/zaki/static/`); the copy `deploy-website.sh` publishes · [`node-app/`](node-app/) — Node/Express server on port 3000 with the same page plus chat (moved from `apps/zaki-ai/`) |
| **Third implementation** | [`platform/zaki/`](../../platform/zaki/) — FastAPI back end on port 8001 and its own front end |
| **Related Odoo modules** | [`addons/mumtaz_zaki/`](../../addons/mumtaz_zaki/), [`addons/mumtaz_voice/`](../../addons/mumtaz_voice/), [`addons/mumtaz_ai/`](../../addons/mumtaz_ai/) |
| **Database** | None of its own; reads finance data from Odoo |
| **Served by** | Three conflicting nginx definitions (upstream ports 3000, 8001, 8002) |
| **CI** | `npm audit` runs on `node-app/` |

> Server facts below are **reported** (from owner-run output recorded in this repo, Oct–Nov 2026) and have not been re-verified. See the [audit pack](../../docs/infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md).

## Open points

- `platform/zaki` has **no authentication**: any tenant's finances readable by number (APP-01, APP-02). Do not deploy it as written.
- `node-app` relies on the deleted `zaki-server` for login and accepts any Odoo URL from the user (APP-05).
- `static/` and `node-app/public/index.html` are near-identical 400 KB files.
