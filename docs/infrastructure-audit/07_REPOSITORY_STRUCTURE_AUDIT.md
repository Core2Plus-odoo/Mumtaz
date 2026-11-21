# 07 — Repository Structure Audit

All findings here are **V-repo** (verified in the repository this session) unless marked.

## 1. Shape of the repository today

```
Mumtaz/                               public GitHub repo, 1,201 tracked files on main
├── addons/                 53 Odoo modules: 37 platform + 14 jewellery + 2 c2p
├── apps/
│   ├── jawhar-web/         ACTIVE   React SPA for Jewel (31 MB of it is ML model binaries)
│   ├── zaki-ai/            ORPHAN   Node server; its auth backend was deleted
│   ├── zaki/               DUPLICATE one HTML file, 44 lines different from zaki-ai's
│   ├── portal/             ORPHAN   static pages; backend deleted
│   ├── marketplace/        ORPHAN   static pages; backend deleted
│   ├── website/            SUPERSEDED marketing site #1
│   ├── erp/                ABANDONED static SPA + deploy for a deleted server
│   ├── platform/           ABANDONED nginx + setup for deleted services
│   └── addons/deploy.sh    STALE
├── platform/               "clean rebuild": schema, ZAKI backend #2, marketing site #2, ops
├── website/                marketing site #3 (index.html) + ACTIVE jewel landing
├── c2p-delivery-system/    ACTIVE   C2P Agency OS (FastAPI + console)
├── faizy/                  separate product (main copy is 37 commits behind its branch)
├── wordpress-sites/        unrelated content sites
├── tools/scrapers/         one scraper
├── deploy/jewel-staging/   ACTIVE   the one coherent deploy kit
├── ops/deployment/         14 legacy deploy scripts + nginx/odoo configs
├── scripts/                13 scripts: legacy Docker deploy, CI helpers, VPS setup
├── config/odoo.conf        legacy Docker config
├── docker-compose*.yml ×3  legacy
├── brand/                  design tokens, referenced only in comments
└── docs/                   5 short root docs + docs/mumtaz-jewel/
```

Plus, **only on unmerged branches**: `addons/pharma_*` (9 modules), `deploy/pharma-staging/`, `docs/pharma/`, `addons/c2p_pk_vouchers`, `addons/c2p_proposal`, `addons/c2p_appointment`, `c2p/odoo/`, `faizy/odoo/addons/faizy_ai`, `docs/erp/`, `docs/project/`, `docs/architecture/`, `wordpress-sites/oddcraze-amazon-shortcode/`, `pay-order.html`.

## 2. Findings

### 2.1 Unrelated projects mixed together — Confirmed

Fourteen projects with at least four different data owners (see `01_ENVIRONMENT_INVENTORY.md` §3). The mixing has concrete costs:

- **Conflicting rules in one tree.** Root `CLAUDE.md` says "commit to `main`, deploys go to `main`". `docs/mumtaz-jewel/CLAUDE.md` says "never commit or push to `main`: `main` auto-deploys to the production VPS". `faizy/CLAUDE.md` (branch) says the root file governs "a separate, unrelated product".
- **One `git pull` moves several products.** `/opt/mumtaz` feeds the C2P Agency OS, the Jewel landing copy and the legacy scripts.
- **CI runs every workflow on every push.** A Faizy commit triggers Mumtaz CI; a WordPress commit triggers Odoo manifest checks.
- **Client work is visible to anyone**, because the shared repository is public.

### 2.2 Duplicate and competing codebases — Confirmed

| What | Copies | Notes |
|---|---|---|
| Marketing site for `mumtaz.digital` | `apps/website/`, `platform/marketing/`, `website/index.html` | Only `website/` is CI-checked and newest |
| ZAKI front end | `apps/zaki-ai/public/index.html` (414 KB), `apps/zaki/static/index.html` (413 KB), `platform/zaki/frontend/` | First two differ by 44 lines |
| ZAKI back end | `apps/zaki-ai/server.js` (Node :3000), `platform/zaki/backend/main.py` (FastAPI :8001), deleted `zaki-server` (:8002) | Three ports, one hostname |
| nginx definition for `app.mumtaz.digital` | 5 files | Upstreams 8002 and 8069 |
| nginx definition for `zaki.mumtaz.digital` | 4 files | Upstreams 3000, 8001, 8002 |
| nginx definition for `erp.mumtaz.digital` | 4 files | Odoo vs a custom SPA |
| Odoo server config | `config/odoo.conf`, `ops/deployment/odoo_master.conf`, `odoo_tenant_worker.conf`, `apps/platform/odoo-multitenant.conf`, `deploy/jewel-staging/odoo.conf.tmpl` | Four different `dbfilter` conventions |
| Deploy scripts | `scripts/deploy-production.sh`, `ops/deployment/deploy.sh`, `deploy-mumtaz.sh`, `deploy-phase-a.sh`, `deploy-website.sh`, `scripts/deploy-architecture-review.sh`, `apps/*/deploy.sh` ×4, `platform/ops/install/*` | Most pin the stale branch `claude/odoo-architecture-review-ujm0W` |
| Build log | `docs/05-build-log.md`, `c2p-delivery-system/docs/05-build-log.md` | Same filename, different content |
| Portal-family Odoo modules | `mumtaz_portal`, `mumtaz_app_portal`, `mumtaz_customer_portal`, `mumtaz_portal_routing`, `mumtaz_vendor_portal` | See `06_ODOO_INSTANCES_AUDIT.md` |
| WordPress themes | `odditytrend-theme`, `youngcraze-theme` | Same tree; candidates for a parent/child theme |
| Deploy prompt | `c2p-delivery-system/CLAUDE-CODE-PROMPT.md`, `c2p-delivery-system/docs/prompts/claude-code-deploy-prompt.md` | Byte-identical |

### 2.3 References to code that no longer exists — Confirmed

Commit `48a2cf9` (PR #124, 2026-07-06) deleted `apps/zaki-server/`, `apps/erp-server/` and `platform/control-panel/`. Still pointing at them: `README.md`, `docs/ARCHITECTURE.md`, `scripts/setup-vps.sh`, `scripts/deploy-architecture-review.sh`, `ops/deployment/deploy.sh`, `deploy-website.sh`, `setup-ssl.sh`, `apps/erp/deploy.sh`, `platform/ops/install/05-cutover.sh`, `platform/ops/systemd/mumtaz-platform.service`, and every nginx file that proxies to :8002.

Running `platform/ops/install/05-cutover.sh` today would delete and re-sync the marketing web root, then abort (APP-26).

### 2.4 Branch and pull-request sprawl — Confirmed

- 51 remote branches. 28 are fully merged and can be deleted after owner confirmation. 23 carry unmerged work.
- Production runs from one of the unmerged ones (R-doc): `claude/resume-help-95ne9v`, 57 commits ahead of and 224 behind `main`.
- Faizy production code lives on `claude/repo-audit-faizy-instance-fck6o3` (+37 / −165), with four more Faizy branches stacked on it.
- Pharma lives on four `pharma-*` branches with no PR.
- 12 open PRs; five are older than two months. Two contain security fixes that never merged: `security/h1-h2-zaki-server-side-and-einvoice-csrf` (e-invoice CSRF, 2026-11-01) and PR #126 "ZAKI auth hardening" (2026-07-11).
- No tags, no releases — there is no way to say "what was deployed on date X".

### 2.5 Artifacts, binaries and oversized files — Confirmed

| Item | Size | Verdict |
|---|---|---|
| `apps/jawhar-web/public/mediapipe/` (wasm + three `.task` models) | 31 MB | Legitimate (on-device vision), but should be Git LFS or fetched at build |
| `addons/mumtaz_jewellery_demo/static/img/*` | ~5 MB | Demo images; acceptable |
| Single-file HTML applications ≥ 250 KB | `zaki-ai` 414 KB, `zaki` 413 KB, C2P console 261 KB, `erp` 147 KB | Maintainability risk rather than a size problem |
| `docs/mumtaz-jewel/plans/*.pdf`, `website/jewel/site/audio/owner-brief.mp3` | < 1 MB each | Fine |

No build output, virtualenvs, `node_modules`, database files or archives are tracked.

### 2.6 Credentials and environment files — Confirmed clean, with caveats

- No `.env`, key, certificate, dump or `.htpasswd` file is tracked on `main`.
- A pattern scan of all 1,089 commits on all branches for provider keys (Anthropic, OpenAI, Stripe, GitHub, AWS, Google, Slack, SendGrid, Telegram), private-key blocks, JWTs and credential-bearing URLs found **no live-looking secret**. Three hits were all placeholders or local defaults.
- Caveat: pattern scans miss low-entropy passwords. Two scripts on `main` carry literal fallback credentials (APP-11) and one demo script documents a default role password (C2P-24). `.env.example` ships `admin` / `odoo` defaults.
- `.gitignore` is sound for secrets. It lacks `*.csv` under `tools/scrapers/` (scraped contact data would be committable) and `*.db` at the root level (covered only inside `c2p-delivery-system/`).

### 2.7 Sensitive information that is not a credential — Confirmed

Because the repository is public, the following is world-readable today (locations in `04_SECURITY_AUDIT.md`, F-03):

- the production IP address, the per-tenant port map, service and config file names, on-disk paths;
- eight production and staging database names, the Odoo build, user/lead/module counts;
- a client's legal name, its sister company, its customer list and the names of its finance staff;
- staff names, a role mailbox, the bot user's name and privilege level;
- a statement that a reachable instance is protected by a default-strength administrator credential;
- 239 lines describing how the CRM's automation qualifies, scores and archives leads.

### 2.8 Documentation — Confirmed

| Document | State |
|---|---|
| `README.md` | Stale since April: Odoo 16/17, deleted `apps/zaki-server`, wrong paths, names a feature branch as "all active development" |
| `docs/DEPLOYMENT.md`, `VPS_SETUP.md`, `MONITORING.md` | 25, 6 and 6 lines; describe the Docker stack that is not in use |
| `docs/ARCHITECTURE.md` | Coherent, but describes the deleted platform API |
| `CLAUDE.md` | Accurate for the C2P Agency OS; wrong about what production tracks |
| `c2p-delivery-system/docs/`, `docs/mumtaz-jewel/`, `faizy/docs/`, `docs/pharma/` (branch) | Good, current, evidence-based — the best documentation in the repository sits beside the newest projects |
| Server runbook (how the VPS is laid out, how to rebuild it) | **Missing** |
| Ownership (who owns which database and domain) | **Missing** |

### 2.9 Naming — Confirmed inconsistent

`Mumtaz_ERP` / `mumtaz_erp` / `mumtaz_main` / `mumtaz_master`; `odoo`, `odoo2`, `odoo3`, `odoo4` (numbered by creation order, not by tenant) beside `odoo-pharma` and `faizy-odoo`; `jewel` / `jawhar` / `mumtaz_jewellery`; `zaki` / `zaki-ai` / `zaki-server`; `/opt/mumtaz` / `/opt/Mumtaz` / `/opt/custom_addons/Mumtaz`.

### 2.10 Dependencies shared unsafely — Confirmed

- Every Python `requirements.txt` outside Jewel uses lower bounds or no pins; there is no lockfile. Root `requirements.txt` is four unpinned names.
- `cryptography`, required for secret encryption in the C2P Agency OS, is not in its requirements (C2P-12).
- Third-party Odoo modules are fetched onto the server outside the repository (`/opt/thirdparty`), pinned by commit for Pharma but not recorded for IG2.
- CI uses `trufflesecurity/trufflehog@main` (a moving reference).

## 3. Monorepo or split?

A monorepo is not wrong in itself. The question is which projects genuinely change together.

| Group | Change together? | Same owner? | Same visibility need? | Recommendation |
|---|---|---|---|---|
| Mumtaz platform addons + Jewel addons + `apps/jawhar-web` + `website/jewel` | Yes — shared Odoo base modules, shared CI | Yes | Private | **Keep together** as the `mumtaz-platform` repository |
| C2P Agency OS | Loosely — it generates modules *into* the addons repo | Yes | Private | Keep in the platform repo as a workspace, **or** split; either is defensible. Keep for now (deploy path depends on `/opt/mumtaz`) |
| C2P internal addons (`c2p_*`) | With the C2P CRM only | Yes | **Private, sensitive** | Workspace inside the platform repo |
| Faizy | No | Same operator, separate product | Private | **Split** — its own docs already recommend this |
| Pharma | No | Staging tenant, possibly a client | Private | **Split** (or a `tenants/pharma` workspace if it stays a demo) |
| IG2 client modules (`c2p_pk_vouchers`, reports) | No | **Client** | Private, client-confidential | **Split** into a client repository |
| WordPress sites | No | Unrelated business line | Could stay public | **Split** |
| Scraper | No | Internal tool | Private | Move to a `tools` repository or delete |
| Legacy (`apps/erp`, `apps/platform`, `apps/zaki`, Docker stack, `ops/deployment`) | — | — | — | **Archive** in a read-only `mumtaz-legacy` repository, then remove from the active tree |

History is preserved in every case by using `git filter-repo --path <dir>` on a fresh clone to create the new repository; the original stays intact until the owner confirms the split.

The proposed target tree and the step-by-step migration are in `12_REORGANIZATION_PLAN.md`.
