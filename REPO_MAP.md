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
| IG2 | Client | Own database on the Hostinger VPS. Nothing in this repository names IG2 |
| C2P | Client | Own database on the Hostinger VPS (`Mumtaz_C2P` per `docs/erp/00-AUDIT.md`) |

To verify on the server: which modules each database has installed, and from
which checkout. That mapping is the input for any consolidation.

## Top-level folders

| Folder | What it is | Belongs to |
| --- | --- | --- |
| `addons/` | 58 Odoo 19 modules | Mumtaz platform, Jawhar, C2P internal (see `registry.yaml`) |
| `apps/jawhar-web` | Jawhar React app | Jawhar |
| `apps/portal` | Static customer portal pages | Mumtaz platform |
| `apps/marketplace` | Static B2B storefront and vendor page | Mumtaz platform |
| `apps/website` | 16-page static marketing site | Mumtaz (see duplicates) |
| `apps/zaki`, `apps/zaki-ai` | Two ZAKI front ends | Mumtaz (see duplicates) |
| `apps/erp`, `apps/platform`, `apps/addons` | nginx configs and deploy scripts | Operations |
| `platform/` | A later platform generation: FastAPI ZAKI back end, marketing page, SQL schema, ops | Mumtaz (see duplicates) |
| `website/` | Landing page plus the Jawhar public site (`website/jewel`) | Mumtaz, Jawhar |
| `brand/` | CSS design tokens and components | Mumtaz |
| `deploy/jewel-staging` | Jawhar staging deployment | Jawhar |
| `ops/`, `scripts/`, `config/` | Deployment, CI and maintenance scripts | Operations |
| `docs/` | Programme documentation | All |
| `c2p-delivery-system/` | C2P Agency OS (FastAPI + console) | C2P, separate product |
| `tools/scrapers` | Lead scrapers | C2P business development |
| `faizy/` | Faizy family-care venture (2 Odoo modules) | Separate venture |
| `wordpress-sites/` | Two WordPress AdSense themes | Separate venture |

## Module layers

Generated detail is in `registry.yaml`. Summary at this commit:

| Layer | Modules | With a test file |
| --- | --- | --- |
| foundation | 4 | 0 |
| platform | 17 | 2 |
| product | 12 | 1 |
| edition (Jawhar) | 15 | 14 |
| internal | 10 | 3 |
| venture | 2 | 0 |

Findings:

- **Jawhar does not depend on the platform.** No `mumtaz_jewellery*` module
  depends on a foundation or platform module. It runs beside the SaaS shell,
  not on it. A bridge module is needed before a Jawhar tenant can be
  provisioned, branded and billed by the control plane.
- **One layering violation:** `mumtaz_portal_routing` (platform) depends on
  `mumtaz_cfo_base` (product). It is recorded as known debt; CI blocks new ones.
- **Tests:** the Jawhar edition is tested; 30 of the 33 foundation, platform
  and product modules have no test file.

## Duplicates awaiting a decision

Nothing here has been deleted or deprecated. Each row needs an owner decision,
then one pull request per row.

| Area | Copies | Evidence so far |
| --- | --- | --- |
| Marketing site | `apps/website` (16 pages), `website/index.html`, `platform/marketing/index.html` | On 21 Nov the live page title at mumtaz.digital matched `platform/marketing` |
| ZAKI application | `apps/zaki` (static), `apps/zaki-ai` (Node), `platform/zaki` (FastAPI + page) | Which one is served is not determinable from git |
| AI and CFO modules | `mumtaz_ai`, `mumtaz_voice`, `mumtaz_zaki`, `mumtaz_cfo_*`, plus the Jawhar provider layer | Decision D-03 in the decision register covers part of this |
| Foundation | `mumtaz_core`, `mumtaz_base` | `mumtaz_base` is 46 lines |
| Brand source | `mumtaz_branding`, `mumtaz_theme`, `brand/tokens.css` | — |
| Organisation model | `mumtaz_org_config`, `mumtaz_organization` | — |
| Portal shells | `mumtaz_portal` (12 lines), `mumtaz_customer_portal` (21 lines) | — |
| Deploy scripts and nginx | `ops/deployment`, `platform/ops`, `deploy/`, `scripts/`, `apps/*/deploy.sh` | 15 distinct `server_name` patterns, including `mumtaz.io` |
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
