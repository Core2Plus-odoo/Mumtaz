# jewel.mumtaz.digital

Jawhar, the jewellery retail system: Odoo 19 modules, a React web app, and a public landing page. Demo/staging with synthetic data.

| | |
|---|---|
| **Status** | Staging / demo. Tested and CI-gated — the best-kept product in the repo |
| **Odoo modules** | [`addons/`](../../addons/) — the 14 `mumtaz_jewellery*` modules |
| **Web app** | [`apps/jawhar-web/`](../../apps/jawhar-web/) — React + TypeScript, served at `/app/` |
| **Landing page** | [`website/jewel/`](../../website/jewel/) |
| **Deploy kit** | [`deploy/jewel-staging/`](../../deploy/jewel-staging/) — compose stack, deploy, backup and restore-drill scripts |
| **Docs and rules** | [`docs/mumtaz-jewel/`](../../docs/mumtaz-jewel/) — read `CLAUDE.md` there before changing anything |
| **Database** | `jewel_demo`, in its own PostgreSQL 16 container |
| **Service** | Docker Compose project `mumtaz-jewel-staging`, ports 8072/8073 on loopback |
| **CI** | `jewel-odoo-tests.yml` (242 tests), `jawhar-web.yml` |

**Nothing was moved for this site.** Its folders are wired into the deploy kit, two CI workflows and a server checkout. Moving them is a later step that needs the deploy script updated and tested on the staging host.

> Server facts below are **reported** (from owner-run output recorded in this repo, Oct–Nov 2026) and have not been re-verified. See the [audit pack](../../docs/infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md).

## Open points

- Never install `mumtaz_jewellery_demo` on a database the client app can reach (ODOO-07).
- Kiosk privacy wording and consent for fit measurements (APP-22).
