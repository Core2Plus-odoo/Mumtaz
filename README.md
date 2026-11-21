# Mumtaz

This repository holds several products and websites run by the Core 2 Plus group. They share one server but **not** one owner: some are the group's own systems, one is a client's, one is a separate product, and some are demos.

Start with **[`sites/`](sites/)** — one folder per website, each saying what the site is, where its code lives, which database it uses and how it is deployed.

## Websites

| Website | What it is | Status |
|---|---|---|
| [core2plus.com](sites/core2plus.com/) | Group CRM and internal ERP (Odoo 19) | Production |
| [erp.mumtaz.digital](sites/erp.mumtaz.digital/) | Mumtaz platform ERP (Odoo 19) | Production |
| [ig2.mumtaz.digital](sites/ig2.mumtaz.digital/) | Client accounting system (Odoo 19) | Production |
| [myfaizy.com](sites/myfaizy.com/) | Faizy, a separate product (Odoo 19) | Production |
| [delivery.mumtaz.digital](sites/delivery.mumtaz.digital/) | C2P Agency OS delivery console (FastAPI) | Production |
| [jewel.mumtaz.digital](sites/jewel.mumtaz.digital/) | Jawhar jewellery system (Odoo 19 + React) | Staging / demo |
| [pharma.mumtaz.digital](sites/pharma.mumtaz.digital/) | Pharma demo tenant (Odoo 19) | Staging / demo |
| [mumtaz.digital](sites/mumtaz.digital/) | Marketing site | Unverified |
| [app.mumtaz.digital](sites/app.mumtaz.digital/) | Customer portal | Orphaned |
| [marketplace.mumtaz.digital](sites/marketplace.mumtaz.digital/) | B2B marketplace | Orphaned |
| [zaki.mumtaz.digital](sites/zaki.mumtaz.digital/) | ZAKI AI CFO | Unknown |
| [odditytrend.com](sites/odditytrend.com/), [youngcraze.com](sites/youngcraze.com/) | WordPress content sites | Unknown |

"Status" for anything on the server is as last recorded in this repository, not re-verified.

## Layout

```
sites/                  one folder per website (index + code that is safe to hold there)
addons/                 Odoo 19 modules: platform (mumtaz_*), jewellery (mumtaz_jewellery*), C2P (c2p_*)
c2p-delivery-system/    C2P Agency OS — API, console, deploy scripts (production deploy path)
apps/jawhar-web/        Jawhar web app (React)
website/                single-page marketing site + Jawhar landing page (website/jewel/)
deploy/jewel-staging/   Jawhar staging stack: compose, deploy, backup, restore drill
faizy/                  Faizy product (the production branch is ahead of this copy)
wordpress-sites/        two WordPress themes and their installer
ops/                    nginx/Odoo config templates and older deploy scripts
scripts/                CI helpers and older deploy scripts
platform/               stalled "platform rebuild" (schema, ZAKI back end, installers)
tools/scrapers/         a lead scraper
docs/                   architecture notes, Jawhar docs, and the infrastructure audit
```

Three folders are deliberately **not** yet under `sites/`, because a running server depends on their exact path: `addons/`, `c2p-delivery-system/` and the Jawhar folders. [`sites/README.md`](sites/README.md) explains why and lists the next steps.

## Before you deploy anything

- Read [`docs/infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md`](docs/infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md). Several documented deploy paths in this repository describe a setup that was never built, and production is reported to track a feature branch rather than `main`.
- The root `Dockerfile` and `docker-compose*.yml` describe a Docker setup that production is **not** reported to use (the server runs Odoo as native services). Treat them as a local development stack.
- Scripts under `ops/deployment/` and `scripts/deploy-*.sh` predate the current server layout. Check each against the server before running it.
- Working deploy kits to copy from: [`deploy/jewel-staging/`](deploy/jewel-staging/) and [`c2p-delivery-system/deploy/`](c2p-delivery-system/deploy/).

## Working rules

- Agent and contributor rules: [`CLAUDE.md`](CLAUDE.md). Jawhar has its own, stricter rules in [`docs/mumtaz-jewel/CLAUDE.md`](docs/mumtaz-jewel/CLAUDE.md).
- Secrets never go in git. Only `*.example` templates are tracked.
- Client work is confidential: no client names, customer data or credentials in code, tests or docs.
