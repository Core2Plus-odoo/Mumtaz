# 12 — Organization and Restructuring Plan

**Status: proposal. Nothing here has been done.** Every change below needs the approval named in its row, and the server-side ones need the verification pack (`13_REMEDIATION_BACKLOG.md`, V-01 … V-12) first, because the server's real layout has not been inspected.

## 1. Conventions

| Topic | Convention |
|---|---|
| Product names | `platform` (Mumtaz SaaS), `c2p` (group internal CRM/ERP), `agency-os` (C2P delivery console), `jawhar` (jewellery), `faizy`, `pharma`, `ig2` (client), `sites` (WordPress) |
| Repositories | `mumtaz-platform`, `faizy`, `client-ig2`, `tenant-pharma`, `content-sites`, `mumtaz-legacy` (read-only archive). All **private** |
| Environments | `dev`, `ci`, `staging`, `demo`, `prod` |
| Hostnames | `prod`: `<product>.<domain>` · `staging`: `<product>.staging.<domain>` · `demo`: `<product>.demo.<domain>` |
| Databases | `<product>_<env>` lower case: `c2p_prod`, `erp_prod`, `ig2_prod`, `faizy_prod`, `jawhar_demo`, `pharma_demo`, `c2p_staging` |
| DB roles | Same as the product: `c2p`, `erp`, `ig2`, `faizy`; plus `backup_ro` |
| systemd units | `odoo-<product>.service`, `delivery-api.service` |
| OS users | `odoo-<product>` |
| Config | `/etc/odoo/<product>.conf`; `/etc/<service>/env` |
| Code on server | `/opt/odoo/<product>/{src,vendor,data}`; `/opt/agency-os` |
| Logs | `/var/log/odoo/<product>.log`; logrotate weekly, keep 8 |
| Backups | `s3://<bucket>/<product>/<env>/<YYYY>/<MM>/<product>_<env>_<timestamp>.{dump,filestore.tar}.age` |
| Release tags | `<product>-vMAJOR.MINOR.PATCH` (monorepo) or `vMAJOR.MINOR.PATCH` (single-product repo) |
| Branches | `main` + short-lived `feat/…`, `fix/…`, `sec/…`. No per-client or per-environment long-lived branches |

Renaming live databases and services is **optional and last** (R-14). The conventions apply to anything new from today; existing names can stay behind clear documentation if the owner prefers to avoid the downtime.

## 2. Target repository structure

### `mumtaz-platform` (private) — what remains in this repository

```
mumtaz-platform/
├── README.md                      what this repo is, which products, where each runs
├── CLAUDE.md                      one file; per-product rules live beside each product
├── infra/
│   ├── INVENTORY.md               hosts, services, ports, databases, domains, owners
│   ├── PORTS.md                   port registry
│   ├── SECRETS.md                 names + locations + rotation dates (never values)
│   ├── RUNBOOK.md                 rebuild a host from zero; restore a database
│   ├── nginx/                     one template per hostname + shared snippets/
│   ├── systemd/                   unit templates
│   ├── odoo/                      conf templates per instance
│   ├── backup/                    backup + restore-drill scripts, timers
│   └── bootstrap/                 host setup (firewall, users, packages)
├── products/
│   ├── platform/
│   │   ├── addons/                the 37 mumtaz_* modules
│   │   ├── web/                   the one marketing site (today: website/index.html)
│   │   ├── deploy/                deploy.sh (stage.sh pattern), DEPLOY_LOG.md
│   │   └── docs/
│   ├── c2p/
│   │   ├── addons/                c2p_project_tracker, c2p_command_center, c2p_proposal,
│   │   │                          c2p_appointment, c2p_agents (once recovered into git)
│   │   ├── deploy/
│   │   └── docs/
│   ├── jawhar/
│   │   ├── addons/                the 14 mumtaz_jewellery* modules
│   │   ├── web/                   apps/jawhar-web
│   │   ├── site/                  website/jewel
│   │   ├── deploy/                deploy/jewel-staging
│   │   └── docs/                  docs/mumtaz-jewel
│   └── agency-os/                 c2p-delivery-system (unchanged inside)
├── docs/
│   ├── infrastructure-audit/      this pack
│   └── adr/                       decisions
└── .github/workflows/             one path-filtered workflow per product
```

Odoo needs every addon directory on its `addons_path`; splitting `addons/` into `products/*/addons/` only means listing two or three paths per instance instead of one. It also makes it impossible to install a jewellery module into the client accounting database by accident.

### Other repositories

| Repository | Content moved from | History |
|---|---|---|
| `faizy` | `faizy/` on branch `claude/repo-audit-faizy-instance-fck6o3` (+ its stacked branches) | `git filter-repo --path faizy/ --path .github/workflows/faizy-ci.yml` |
| `client-ig2` | `addons/c2p_pk_vouchers`, IG2-specific parts of `mumtaz_financial_reports`, `docs/erp/` from branch `claude/resume-help-95ne9v` | `git filter-repo` with those paths |
| `tenant-pharma` | `addons/pharma_*`, `deploy/pharma-staging/`, `docs/pharma/` from `pharma-erp-v0.1` | same |
| `content-sites` | `wordpress-sites/` (+ PR #134) | same |
| `mumtaz-legacy` (archived, read-only) | `apps/erp`, `apps/platform`, `apps/zaki`, `apps/portal`, `apps/marketplace`, `apps/website`, `apps/addons`, `apps/zaki-ai`, `platform/`, `ops/deployment/`, root Docker files, legacy `scripts/`, `config/`, `tools/scrapers/` | Full clone of today's repo, then archived |

## 3. Path-by-path mapping

| Current path | Status | Target | Action |
|---|---|---|---|
| `addons/mumtaz_jewellery*` (14) | Active | `products/jawhar/addons/` | Relocate |
| `addons/mumtaz_*` (37 others) | Active / partly unused | `products/platform/addons/` | Relocate; triage unused modules first (`06_ODOO_INSTANCES_AUDIT.md`) |
| `addons/c2p_project_tracker`, `c2p_command_center` | Active | `products/c2p/addons/` | Relocate |
| `apps/jawhar-web/` | Active | `products/jawhar/web/` | Relocate; move model binaries to LFS |
| `website/jewel/` | Active | `products/jawhar/site/` | Relocate |
| `deploy/jewel-staging/` | Active | `products/jawhar/deploy/` | Relocate |
| `docs/mumtaz-jewel/` | Active | `products/jawhar/docs/` | Relocate |
| `c2p-delivery-system/` | Active, **production deploy path** | `products/agency-os/` | Relocate **last**, with a server-side symlink (R-10) |
| `website/index.html`, `website/assets/` | Active-ish | `products/platform/web/` | Retain as the one marketing site |
| `apps/website/`, `platform/marketing/` | Superseded | `mumtaz-legacy` | Retire |
| `apps/zaki/` | Duplicate | `mumtaz-legacy` | Retire |
| `apps/zaki-ai/`, `platform/zaki/` | Orphaned, unsafe as written | `mumtaz-legacy` until a product decision (D-08) | Review → consolidate or retire |
| `apps/portal/`, `apps/marketplace/` | Orphaned (backend deleted) | `mumtaz-legacy` | Retire after confirming what serves `app.` and `marketplace.` today |
| `apps/erp/`, `apps/platform/`, `apps/addons/` | Abandoned | `mumtaz-legacy` | Retire |
| `platform/db/`, `platform/ops/` | Unknown (rebuild stalled) | `mumtaz-legacy` | Review (D-08) |
| `ops/deployment/` | Legacy | useful templates → `infra/`; rest → `mumtaz-legacy` | Consolidate |
| `scripts/jewel_ci.sh`, `check_links.py`, `platform_ci.sh` (PR #172) | Active CI helpers | beside their product | Relocate |
| `scripts/backup.sh`, `deploy-*.sh`, `rollback.sh`, `health-check.sh`, `setup-vps.sh`, `migrate.py`, `update-nginx-domains.sh`, `smoke-test.sh`, `validate-deployment.py`, `deploy-architecture-review.sh` | Legacy Docker path | `mumtaz-legacy`; replaced by `infra/` | Retire |
| `Dockerfile`, `docker-compose*.yml`, `config/odoo.conf`, `.env.example` | Legacy | keep **one** `docker-compose.dev.yml` for local development; rest → `mumtaz-legacy` | Consolidate |
| `faizy/` | Stale copy on `main` | repository `faizy` | Split, then remove from `main` |
| `wordpress-sites/` | Unrelated | repository `content-sites` | Split |
| `tools/scrapers/` | Dormant | `mumtaz-legacy` (or delete) | Retire after owner decision |
| `brand/` | Dormant | `products/platform/web/brand/` or delete | Review |
| `docs/ARCHITECTURE.md`, `DEPLOYMENT.md`, `MONITORING.md`, `VPS_SETUP.md` | Stale | replaced by `infra/*.md` | Rewrite |
| `docs/05-build-log.md` | Active log | `products/agency-os/docs/` (merge with the other build log) | Consolidate |
| `.mcp.json` | Tooling | keep | Retain |
| branch `claude/resume-help-95ne9v` | **What production runs** | reconcile into `main` (C2P parts) and `client-ig2` (IG2 parts) | Repair — R-05 |
| branches `pharma-*` | Staging tenant | repository `tenant-pharma` | Split |
| branches `claude/faizy-*`, `claude/repo-audit-faizy-instance-*` | Faizy production | repository `faizy` | Split |
| 28 merged branches | Dead | — | Delete after owner confirmation |
| PR #127 `pay-order.html` | See F-19 | — | Close and delete branch (owner decision) |

### Server mapping (to be confirmed by V-01 … V-12)

| Current | Target | Phase |
|---|---|---|
| `odoo4.service` / `/etc/odoo4.conf` / `Mumtaz_C2P` / :8075 | `odoo-c2p` / `/etc/odoo/c2p.conf` / role `c2p` | 4 |
| `odoo.service` / `/etc/odoo/odoo.conf` / :8069 (also `Mumtaz_C2P`) | Retire **after** proving nothing routes to it | 2 → 4 |
| `odoo2.service` / `Mumtaz_ERP` / :8070 | `odoo-erp` / role `erp` | 4 |
| `odoo3.service` / `Mumtaz_IG2` / :8071 public | `odoo-ig2` / role `ig2` / loopback + nginx + TLS | **2** (exposure), 4 (rest) |
| `faizy-odoo.service` | unchanged (already conforms) | — |
| `odoo-pharma.service`, Jewel compose | move to `stage-1` | 4 |
| `/opt/mumtaz`, `/opt/custom_addons/Mumtaz` (both on a feature branch) | `/opt/odoo/<product>/src` at a tag; `/opt/agency-os` | 4 |
| `erp-server.service` (crash loop) | Disable, then remove | 2 |
| `zaki-server`, pm2 apps | Confirm state; retire or rebuild | 2 → 5 |
| stray DBs `mumtaz_erp`, `IG2`, `Mumtaz_C2P_staging`, `scratch_pre` | Dump → archive → drop, per owner sign-off | 4 |

## 4. Change register

Risk is the risk of **making the change**. Downtime is per affected service.

| ID | Change | Why | Risk | Systems affected | Depends on | Backup prerequisite | Validation | Rollback | Downtime | Approval |
|---|---|---|---|---|---|---|---|---|---|---|
| R-01 | Make the GitHub repository private | Stops ongoing disclosure of server layout, client details and known weaknesses (F-03) | Low | Any server doing unauthenticated `git clone`/`pull` over HTTPS (`update.sh`, Faizy and Pharma checkouts); forks keep what they have | A deploy key or token on each server checkout **first** | None | `git ls-remote` from each checkout succeeds with the new credential; anonymous clone fails | Set back to public | None if credentials are in place first | **Owner** |
| R-02 | Write `infra/INVENTORY.md`, `PORTS.md`, `RUNBOOK.md` from the verification pack | No document matches the server | None | Docs only | V-01 … V-12 | None | Second person can find any service from the doc | Revert commit | None | Tech lead |
| R-03 | Fix the four invalid workflows (PR #168) with `backup.yml` and `deploy-*.yml` set to manual-only until redesigned | CI is noise; but a naive fix starts SSH jobs against production | Low | GitHub Actions | D-06 | None | Workflows parse; no scheduled SSH run occurs | Revert | None | Tech lead |
| R-04 | Get `main` green; merge PR #172; enable branch protection | Nothing is enforceable while red | Low | Developers | R-03 | None | Required checks pass on a test PR | Disable protection | None | Tech lead |
| R-05 | Reconcile `claude/resume-help-95ne9v` with `main`; bring untracked server modules into git | Production code is on an unmerged branch and partly outside git (F-04, F-05) | **Medium** — 224 commits of drift | C2P CRM, Platform ERP, IG2 | V-04, V-05; staging twin | Dump of each affected DB | Fresh-install CI + upgrade on a staging copy of each DB | Server stays on the old branch until staging passes | None (merge is repo-side); switch-over is R-11 | Owner + tech lead |
| R-06 | Split Faizy, Pharma, IG2, WordPress into their own repos (history preserved) | Different owners and confidentiality (07 §3) | Low | Developers; server checkouts' remotes | R-01 | None | New repo builds; CI green; `git log` history intact | Old paths remain until R-08 | None | Owner |
| R-07 | Re-point server checkouts at the new repositories | Follows R-06 | Low–Medium | Faizy, Pharma | R-06 | None | `git remote -v`; `git status` clean; next deploy succeeds | Re-point back | None | Tech lead |
| R-08 | Create `mumtaz-legacy` archive; remove legacy/orphaned paths from `main` | Dead code misleads and carries unsafe defaults (APP-11, APP-26) | Low | Anything still copying from those paths on the server | V-06, V-07 confirm nothing live depends on them | None | grep the server for references; site checks | `git revert`; archive repo still has everything | None | Owner |
| R-09 | Restructure into `products/*` and `infra/` | Clear ownership; safer `addons_path` | **Medium** — every server `addons_path` and CI path changes | All Odoo instances built from this repo; CI | R-05, R-08 | Config tarball of `/etc/odoo*` | Staging instance starts with new paths; module list unchanged (`ir_module_module` diff) | Compatibility symlink `addons → products/*/addons` kept for one release | Restart per instance (~1 min) at switch-over | Tech lead |
| R-10 | Move `c2p-delivery-system/` → `products/agency-os/` | Consistency | Low–Medium — nginx root symlink and unit `WorkingDirectory` depend on the path | `delivery.mumtaz.digital` | R-09 | Copy of SQLite stores + `.env` | Health endpoint; console loads; login works | Server-side symlink from old path; revert unit | < 1 min restart | Tech lead |
| R-11 | Production instances check out a release **tag** of `main` | Know what is running; enable rollback | Medium | C2P, ERP, IG2 | R-05, backups (B-1) | Dump + filestore per instance | Staging upgrade first; then health + module versions | Check out previous ref; restore dump if a migration ran | Minutes per instance, scheduled | Owner |
| R-12 | One nginx template per hostname in `infra/nginx/`; remove the nine competing definitions | Five definitions of `app.` and four of `zaki.` (07 §2.2) | Low in repo; Medium when applied | All sites, at apply time | V-02 (dump of live nginx config) | Tarball of `/etc/nginx` | `nginx -t`; diff rendered template vs live before swap; curl each host | Restore tarball; reload | None (reload) | Tech lead |
| R-13 | Per-application PostgreSQL roles and OS users | Shared role = shared fate (F-06) | **Medium–High** | C2P, ERP, IG2, Pharma | B-1 backups proven; staging rehearsal | Dump per DB + `pg_dumpall --globals-only` | App starts; `\du`; cross-role connect is refused | `REASSIGN OWNED` back; restore conf | 5–10 min per instance, scheduled | Owner |
| R-14 | Rename services/databases to the convention | Readability | Medium | Each instance in turn | R-13 | Dump + filestore | Login, attachments open (filestore dir follows DB name), crons run | Rename back | 10–15 min per instance | Owner — **optional** |
| R-15 | Stand up `stage-1`; move Jewel, Pharma and staging twins | Separates production from non-production (F-07) | Low | Staging tenants; DNS for `jewel.`, `pharma.` | Budget (D-04) | Dumps of both staging DBs | Sites answer from the new host; old units stopped, not deleted, for 2 weeks | Point DNS back | Minutes (DNS TTL) | Owner |
| R-16 | Archive and drop stray databases | Unknown copies of real data (F-13) | Low after sign-off | PostgreSQL | V-DB-2, -4, -5; owner sign-off per name | `pg_dump -Fc` of each, kept 90 days off-site | No app errors for a week after connections are revoked (`ALTER DATABASE … ALLOW_CONNECTIONS false`) **before** dropping | Re-enable connections; or restore dump | None | Owner, per database |
| R-17 | Delete the 28 merged branches; triage 12 open PRs | Sprawl | None | GitHub | Owner glance at the list | None | — | Branch tips are recoverable from PR refs / reflog for ~90 days | None | Tech lead |

### Sequencing

```
R-01 ─► R-02 ─► R-03 ─► R-04 ─► R-17
              └► (Phase 2 security + backups, see 14)
R-05 ─► R-06 ─► R-07 ─► R-08 ─► R-09 ─► R-10 ─► R-11 ─► R-12
                                             R-13 ─► R-14 (optional)
R-15 can run in parallel once backups are proven.   R-16 after V-DB checks.
```

Rules for the whole plan: one change per maintenance window; never two products in one window; each window starts with a fresh dump and ends with the validation step written into that product's `DEPLOY_LOG.md`.

## 5. Handling archived projects

1. Tag the last commit that contained the project: `archive/<name>-<date>`.
2. Copy to `mumtaz-legacy`; set that repository to **archived** (read-only) on GitHub.
3. Add one line to `infra/INVENTORY.md` under "Retired": name, date, reason, where the archive is, who approved.
4. Remove from the active repository in a single commit that references the tag.
5. On the server: stop and disable the unit, keep files for 30 days, then remove. Keep one final dump of any database for 12 months.
