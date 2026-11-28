# Repository map

Written 21 Nov 2026 from a read-only review of `main` at `5c077df`. It
describes what is in git. It does not describe the servers: nothing on a
server or in a database was inspected. Statements marked **owner-stated** come
from Muhammad Umer and are not yet backed by repository evidence.

## Tenants and clients (owner-stated, 21 Nov 2026)

| Tenant | Kind | Notes |
| --- | --- | --- |
| Jewel (Jawhar) | Product tenant | Staging documented at `jewel.mumtaz.digital`, database `jewel_demo` (`docs/erp/00-AUDIT.md`) |
| Pharma | Product tenant | No pharma module exists in this repository |
| IG2 | Client | Own database on the Hostinger VPS. Two shared modules still carry IG2-specific values (see `docs/platform/MUMTAZ_MODULE_REGISTRY_REVIEW.md`) |
| C2P | Client | Own database on the Hostinger VPS (`Mumtaz_C2P` per `docs/erp/00-AUDIT.md`) |

To verify on the server: which modules each database has installed, and from
which checkout. That mapping is the input for any consolidation.

## Top-level folders

Every folder has a `README.md` that says what it is and whether it may be
moved (except `addons/`, where a stray file would be read as a module by the
CI scripts). Folders are grouped below by the four categories used in
`docs/platform/`. "Fixed" means a running service or a deploy script reads
that exact path: it moves only with a planned step on the server.

### Shared platform

| Folder | What it is | Path |
| --- | --- | --- |
| `addons/` | 62 Odoo 19 modules: the platform, the products, the Jawhar edition and C2P's internal modules. Classified in `registry.yaml` | Fixed |
| `registry/`, `registry.yaml` | Module classification (hand-kept) and the generated registry | Free |
| `scripts/` | Checks, test runs and older server scripts; grouped in `scripts/README.md` | Fixed (CI workflows call them by path) |
| `config/` | `odoo.conf` for the root `Dockerfile` and `docker-compose*.yml` | Fixed (compose mounts it) |
| `.github/` | CI workflows | Fixed |

### Commercial products

| Folder | What it is | Path |
| --- | --- | --- |
| `c2p-delivery-system/` | Delivery OS / C2P Agency OS: FastAPI back end and single-file console | **Fixed** — production pulls `main` at this path |
| `apps/jawhar-web/` | Jawhar web app (React) | Fixed (Jawhar deploy kit) |
| `website/jewel/` | Jawhar public site | Fixed (Jawhar deploy kit, CI link check) |
| `deploy/jewel-staging/` | Jawhar staging stack and runbook | Fixed |
| `sites/zaki.mumtaz.digital/`, `sites/marketplace.mumtaz.digital/`, `sites/erp.mumtaz.digital/`, `sites/app.mumtaz.digital/` | Per-website index plus the static code of each | Free |
| `platform/` | A stalled rebuild: FastAPI ZAKI back end, a marketing page, an SQL schema, install scripts. **Do not run its cut-over script** (`docs/platform/MUMTAZ_AI_ARCHITECTURE.md`) | Fixed until the server inventory shows nothing reads it |

Mumtaz ERP, the general ERP product, has no folder of its own: it is the
install profile `mumtaz_erp` over modules in `addons/`.

### Customer deployments and separate ventures

| Folder | What it is | Path |
| --- | --- | --- |
| `sites/core2plus.com/`, `sites/ig2.mumtaz.digital/` | Index pages for C2P's internal ERP and the IG2 client instance. Their code is in `addons/` (C2P) and on a separate branch (IG2) | Free |
| `faizy/` | Faizy, a separate venture: 4 Odoo modules, brand, docs. Production runs it from its own branch | Fixed; destination is its own repository (decision D-12) |
| `sites/myfaizy.com/` | Index page for Faizy | Free |

### Supporting websites and operations

| Folder | What it is | Path |
| --- | --- | --- |
| `sites/mumtaz.digital/` | Index plus the 14-page static marketing site | Free |
| `sites/delivery.mumtaz.digital/landing/` | A landing page for the delivery console (was `website/index.html` and `website/assets/`) | Free: the server check of 22 Nov 2026 showed no nginx root reads it |
| `wordpress-sites/`, `sites/odditytrend.com/`, `sites/youngcraze.com/` | Two WordPress themes and their index pages | Fixed; destination is their own repository (D-12) |
| `ops/` | nginx definitions, Odoo config samples and older deploy scripts. None confirmed live | Free, but referenced by scripts |
| `tools/scrapers/` | Internal lead scraper | Free (CI lints this path) |
| `docs/` | All documentation; index in `docs/README.md` | Free |

### What moved, and when

| Date | Move |
| --- | --- |
| 21 Nov 2026 | Eight `apps/*` folders to `sites/<domain>/` and `ops/` (table in `sites/README.md`) |
| 22 Nov 2026 | `brand/` → `docs/design/brand-tokens-v3/`; `docs/ARCHITECTURE.md`, `DEPLOYMENT.md`, `MONITORING.md`, `VPS_SETUP.md` → `docs/operations/`; `website/index.html` and `website/assets/` → `sites/delivery.mumtaz.digital/landing/` |

Nothing was deleted. The remaining "Fixed" folders are listed with the server
step each one needs in `docs/platform/MUMTAZ_REPOSITORY_CONSOLIDATION.md`.

## Module layers

Generated detail is in `registry.yaml`. Summary on 25 Nov 2026 (66 modules):

| Layer | Modules | With a test file |
| --- | --- | --- |
| foundation | 4 | 0 |
| platform | 18 | 5 |
| product | 12 | 2 |
| edition (Jawhar) | 15 | 14 |
| internal | 13 | 10 |
| venture | 4 | 4 |

Findings:

- **Jawhar does not depend on the platform.** No `mumtaz_jewellery*` module
  depends on a foundation or platform module. It runs beside the SaaS shell,
  not on it. A bridge module is needed before a Jawhar tenant can be
  provisioned, branded and billed by the control plane.
- **One layering violation:** `mumtaz_portal_routing` (platform) depends on
  `mumtaz_cfo_base` (product). It is recorded as known debt; CI blocks new ones.
- **Tests:** the Jawhar edition is tested; 27 of the 34 foundation, platform
  and product modules have no test file.

## What is live (checked on the server, 21 Nov 2026)

From the nginx site files and file checksums on the production server. The
live front ends are folders inside the server checkout that are **not tracked
in git**; they were copied there by hand, most in June 2026.

| Site | Served from (server) | Matches in git |
| --- | --- | --- |
| mumtaz.digital | `/opt/mumtaz/marketing` | Identical to `platform/marketing/index.html` at the time of the check |
| zaki.mumtaz.digital | `/opt/mumtaz/zaki/frontend`, API on port 8001 | Identical to `platform/zaki/frontend/index.html` at the time of the check |
| app.mumtaz.digital | `/opt/mumtaz/platform/frontend`, API on port 8002 | No matching file on `main` (not `sites/app.mumtaz.digital/portal`) |
| jewel.mumtaz.digital | `/opt/mumtaz/jewel-landing` plus the Jawhar Odoo | Not compared |
| marketplace.mumtaz.digital | `/var/www/marketplace.mumtaz.digital` | Not compared |
| erp, pharma, ig2 subdomains | Odoo, by proxy | — |

So `platform/marketing` and `platform/zaki` are the canonical sources.
`sites/mumtaz.digital/site`, `website/index.html`, `sites/zaki.mumtaz.digital/static`
and `sites/zaki.mumtaz.digital/node-app` are not deployed. Publishing a change means copying the file into the served folder;
merging to `main` does not do it.

## Duplicates awaiting a decision

Nothing here has been deleted or deprecated. Each row needs an owner decision,
then one pull request per row.

| Area | Copies | Evidence so far |
| --- | --- | --- |
| Marketing site | `sites/mumtaz.digital/site` (14 pages), `sites/delivery.mumtaz.digital/landing/index.html`, `platform/marketing/index.html` | **Resolved:** `platform/marketing` is live (see above) |
| ZAKI application | `sites/zaki.mumtaz.digital/static` (static), `sites/zaki.mumtaz.digital/node-app` (Node), `platform/zaki` (FastAPI + page) | **Resolved:** `platform/zaki` is live (see above) |
| AI and CFO modules | `mumtaz_ai`, `mumtaz_voice`, `mumtaz_zaki`, `mumtaz_cfo_*`, plus the Jawhar provider layer | Decision D-03 in the decision register covers part of this |
| Foundation | `mumtaz_core`, `mumtaz_base` | `mumtaz_base` is 46 lines |
| Brand source | `mumtaz_branding`, `mumtaz_theme`, `docs/design/brand-tokens-v3/tokens.css` | — |
| Organisation model | `mumtaz_org_config`, `mumtaz_organization` | — |
| Portal shells | `mumtaz_portal` (12 lines), `mumtaz_customer_portal` (21 lines) | — |
| Deploy scripts and nginx | `ops/deployment`, `platform/ops`, `deploy/`, `scripts/`, `sites/*/*/deploy.sh` | 15 distinct `server_name` patterns, including `mumtaz.io` |
| API port | 8001 in the previous README, 8002 in configuration files | — |
| Price list | $49 / $199 on the live site (21 Nov); $149 / $399 / $999 in the previous README's description of the portal wizard | — |

## Proposed order of work

1. This map, the registry and the layering check (this change; no behaviour change).
2. Server inventory: database to module to checkout mapping for every tenant.
3. Decide each duplicate above; collapse one per pull request, tested on staging.
4. Move `faizy/`, `wordpress-sites/` and, if agreed, `c2p-delivery-system/` to their own repositories. Production pulls this repository, so this needs a deployment plan first.
5. Bridge Jawhar onto the tenant manager and control plane.
6. One automated end-to-end test: sign-up, tenant created, edition installed, first login, first invoice.

Dispositions in `registry/classification.json` (`merge-candidate`,
`relocate-candidate`, `review`) are proposals. Record approvals in
`docs/erp/project/DECISION_REGISTER.md`.
