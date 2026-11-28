# mumtaz.digital

Marketing website for the Mumtaz platform. Static HTML, no database.

| | |
|---|---|
| **Status** | Three copies of this site exist in the repo. On 21 Nov 2026 the live page title matched the `platform/marketing` copy (recorded in `REPO_MAP.md`) |
| **Code in this folder** | [`site/`](site/) — 14-page static site (moved from `apps/website/`). This is the copy the scripts in `ops/deployment/` publish, which suggests those scripts are no longer what deploys the live site |
| **Other copies** | [`sites/delivery.mumtaz.digital/landing/index.html`](../delivery.mumtaz.digital/landing/index.html) — single page, checked by CI, links to the delivery console · [`platform/marketing/`](../../platform/marketing/) — from the stalled platform rebuild |
| **Database** | None |
| **Served by** | nginx, web root `/var/www/mumtaz.digital` |
| **Deploy** | `ops/deployment/deploy-website.sh` copies `site/` to the web root |

> Server facts below are **reported** (from owner-run output recorded in this repo, Oct–Nov 2026) and have not been re-verified. See the [audit pack](../../docs/infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md).

## Open points

- Decide which of the three copies is the real site (decision D-09 in `docs/erp/project/DECISION_REGISTER.md`) and retire the other two.
- Six pages in `site/` link "Platform Login" to a raw server port instead of the HTTPS address (audit finding APP-12).
- The contact form shows a success message and discards the enquiry (APP-36).
