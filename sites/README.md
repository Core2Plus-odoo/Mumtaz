# Sites

Companion to [`REPO_MAP.md`](../REPO_MAP.md): that file describes the repository folder by folder; this one describes it website by website.

One folder per website. Each has a `README.md` saying what the site is, where its code lives, which database it uses, how it is deployed, and what is open.

> Server facts are **reported**, not re-verified: they come from owner-run output recorded in this repo between Oct and Nov 2026. The full picture is in [`docs/infrastructure-audit/`](../docs/infrastructure-audit/).

| Website | What it is | Code | Database | Status |
|---|---|---|---|---|
| [core2plus.com](core2plus.com/) | Group CRM / internal ERP | `addons/c2p_*` + rules stored in the database | `Mumtaz_C2P` | Production |
| [erp.mumtaz.digital](erp.mumtaz.digital/) | Platform ERP (also `admin.`) | `addons/mumtaz_*` | `Mumtaz_ERP` | Production |
| [ig2.mumtaz.digital](ig2.mumtaz.digital/) | **Client** accounting | branch `claude/resume-help-95ne9v` | `Mumtaz_IG2` | Production, no staging |
| [myfaizy.com](myfaizy.com/) | Faizy (separate product) | `faizy/` + production branch | `faizy_prod` | Production |
| [delivery.mumtaz.digital](delivery.mumtaz.digital/) | C2P Agency OS console | `c2p-delivery-system/` | SQLite files | Production |
| [jewel.mumtaz.digital](jewel.mumtaz.digital/) | Jawhar jewellery demo | `addons/mumtaz_jewellery*`, `apps/jawhar-web/`, `website/jewel/` | `jewel_demo` | Staging |
| [pharma.mumtaz.digital](pharma.mumtaz.digital/) | Pharma demo tenant | branches `pharma-*` | `mumtaz_pharma` | Staging |
| [mumtaz.digital](mumtaz.digital/) | Marketing site | `sites/mumtaz.digital/site/` | none | Unverified |
| [app.mumtaz.digital](app.mumtaz.digital/) | Customer portal | `sites/app.mumtaz.digital/portal/` | SQLite `users.db` | Orphaned |
| [marketplace.mumtaz.digital](marketplace.mumtaz.digital/) | B2B marketplace | `sites/marketplace.mumtaz.digital/storefront/` | via API | Orphaned |
| [zaki.mumtaz.digital](zaki.mumtaz.digital/) | ZAKI AI CFO | `sites/zaki.mumtaz.digital/` + `platform/zaki/` | none | Unknown |
| [odditytrend.com](odditytrend.com/) | WordPress site | `wordpress-sites/odditytrend-theme/` | MariaDB | Unknown |
| [youngcraze.com](youngcraze.com/) | WordPress site | `wordpress-sites/youngcraze-theme/` | MariaDB | Unknown |

## What moved, and what did not

Step 1 of the reorganization moved only code that is **not** wired into a running deploy. History is preserved (`git log --follow` works on every moved file), and every script and CI job that referenced an old path was updated in the same commit.

| Old path | New path |
|---|---|
| `apps/website/` | `sites/mumtaz.digital/site/` |
| `apps/portal/` | `sites/app.mumtaz.digital/portal/` |
| `apps/marketplace/` | `sites/marketplace.mumtaz.digital/storefront/` |
| `apps/zaki/static/` | `sites/zaki.mumtaz.digital/static/` |
| `apps/zaki-ai/` | `sites/zaki.mumtaz.digital/node-app/` |
| `apps/erp/` | `sites/erp.mumtaz.digital/legacy-spa/` |
| `apps/platform/` | `ops/platform-routing/` |
| `apps/addons/` | `ops/addons-deploy/` |

On 22 Nov 2026 the remaining loose folders were tidied (nothing a server reads):

| Old path | New path |
|---|---|
| `brand/` | `docs/design/brand-tokens-v3/` |
| `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT.md`, `docs/MONITORING.md`, `docs/VPS_SETUP.md` | `docs/operations/` |
| `docs/05-build-log.md` (a stray fragment) | appended to `c2p-delivery-system/docs/05-build-log.md` |
| `website/index.html`, `website/assets/` | `sites/delivery.mumtaz.digital/landing/` |

Every top-level folder now has a `README.md`; the full folder table, grouped by category, is in [`REPO_MAP.md`](../REPO_MAP.md).

Paths in `docs/infrastructure-audit/` describe the repository as it was on 21 Nov 2026, before these moves; use the tables above to translate.

Left in place on purpose, and indexed from the site folders instead:

| Path | Why it stays for now |
|---|---|
| `addons/` | Every Odoo service's `addons_path` points here; moving it without a server-side change stops Odoo loading its modules. 23 unmerged branches also edit it |
| `c2p-delivery-system/` | Production deploys from this exact path, and untracked `.env` and database files sit inside it |
| `apps/jawhar-web/`, `website/jewel/`, `deploy/jewel-staging/`, `docs/mumtaz-jewel/` | Wired into the Jewel deploy kit and two CI workflows |
| `faizy/`, `wordpress-sites/` | Open branches and pull requests edit them; both belong in their own repositories |
| `ops/deployment/`, `scripts/`, `platform/`, root Docker files | Referenced by workflows or by the production branch; to be consolidated after the server check |

## Step 2 (needs a short server-side step per site, and approval)

1. `c2p-delivery-system/` → `sites/delivery.mumtaz.digital/` — stop service, move `.env` and stores, update unit and nginx paths, start.
2. Jewel folders → `sites/jewel.mumtaz.digital/` — update `deploy.sh`, compose mounts, CI paths; rehearse on staging.
3. `addons/` split by product — after the production branch is reconciled into `main`; each Odoo config gets the new `addons_path`.
4. Faizy, Pharma, IG2 client code and WordPress → their own private repositories.
