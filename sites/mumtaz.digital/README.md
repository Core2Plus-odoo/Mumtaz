# mumtaz.digital

Marketing website for the Mumtaz platform. Static HTML, no database.

| | |
|---|---|
| **Status** | Live state not verified. Three copies of this site exist in the repo |
| **Code in this folder** | [`site/`](site/) — 14-page static site (moved from `apps/website/`). This is the copy the deploy scripts publish |
| **Other copies** | [`website/index.html`](../../website/index.html) — single page, checked by CI, links to the delivery console · [`platform/marketing/`](../../platform/marketing/) — from the stalled platform rebuild |
| **Database** | None |
| **Served by** | nginx, web root `/var/www/mumtaz.digital` |
| **Deploy** | `ops/deployment/deploy-website.sh` copies `site/` to the web root |

> Server facts below are **reported** (from owner-run output recorded in this repo, Oct–Nov 2026) and have not been re-verified. See the [audit pack](../../docs/infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md).

## Open points

- Decide which of the three copies is the real site and retire the other two.
- Six pages in `site/` link "Platform Login" to a raw server port instead of the HTTPS address (audit finding APP-12).
- The contact form shows a success message and discards the enquiry (APP-36).
