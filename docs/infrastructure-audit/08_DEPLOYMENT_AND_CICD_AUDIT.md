# 08 — Deployment and CI/CD Audit

## 1. How things actually reach the server

| Project | Real deployment method | Evidence | Reproducible? |
|---|---|---|---|
| C2P Agency OS | SSH to VPS, `bash /opt/mumtaz/c2p-delivery-system/deploy/update.sh` → `git pull --ff-only origin main`, re-symlink console, restart API, health check | V-repo | Yes for code. No backup, test or rollback step |
| Jewel staging | `deploy/jewel-staging/deploy.sh` — refuses `main`, refuses the production checkout, renders config, restarts its own compose project, health-checks | V-repo | **Yes** — the reference implementation in this repo |
| Pharma staging | `deploy/pharma-staging/stage.sh` — gated sub-commands, automatic pre-upgrade dump, printed rollback | R-doc | **Yes** |
| Faizy | One documented `&&`-chained command: stop service, `git pull`, `-u` modules, start | R-doc (branch) | Yes for code; data rollback undocumented |
| C2P CRM, Platform ERP, IG2 | By hand: `git pull` in `/opt/custom_addons/Mumtaz` (on a feature branch), then `odoo -u …`. Some modules copied onto the server directly; some logic edited in the database UI | R-doc | **No** |
| Static sites | `rsync`/`cp` scripts into `/var/www/*` | V-repo | Partly; scripts pin a stale branch |
| WordPress | One-shot `setup-lemp.sh` | V-repo | Install only |

**No production deployment has ever gone through CI.** The pipeline that claims to do it (`deploy-production.yml`) is an invalid workflow file and targets a Docker stack that does not exist on the server.

## 2. GitHub Actions — state on `main` (V-gh, 2026-11-20 run set)

| Workflow | Intent | Actual state | Cause |
|---|---|---|---|
| `ci.yml` — Mumtaz CI (10 jobs) | Manifest, flake8, bandit, XML, dependency graph, TruffleHog, pip-audit, npm audit, hadolint, website check | **Red.** 8 jobs pass; `flake8` fails; `TruffleHog` fails within one second | Lint debt on `main`. The TruffleHog step exits in under a second, which points to a configuration error rather than a detected secret (likely the action's base/head handling on push; job log not read). Either way the secret scan is not providing coverage on `main` |
| `test.yml` | Lint, tests, Docker image build and push to GHCR | **Startup failure** on every push | `secrets.*` used in `if:` |
| `deploy-staging.yml` | Deploy on push to `develop` | **Startup failure**; `develop` does not exist | Same |
| `deploy-production.yml` | Manual deploy with backup, health check, rollback | **Startup failure**; never ran | Same |
| `backup.yml` | Nightly backup | **Startup failure**; 920 failed runs | Same |
| `jewel-odoo-tests.yml` | Install jewellery addons on Odoo 19 + PostgreSQL 16, run 242 tests | **Green** | — |
| `jawhar-web.yml` | Typecheck, test, build | **Green** | — |
| `faizy-ci.yml` | Compile, manifest/ACL/view cross-checks | Not checked | — |

PR #168 fixes the four startup failures. PR #172 adds a fresh-database install test for the 39 non-jewellery modules (it found four that could not install on a clean database).

### Consequences

- A red default branch means failures are ignored. The two green workflows are trusted only because they are scoped to one project.
- 39 of 53 Odoo modules have no `tests/` directory. Until PR #172 merges, nothing proves the platform modules install.
- The delivery API's test file is not run by any workflow (C2P-18).
- Every push to any branch fires eight workflows; five of them fail by construction. Roughly 1,350 runs have accumulated.

## 3. Pipeline security review

| # | Observation | Where | Severity |
|---|---|---|---|
| CI-1 | Third-party action pinned to a moving branch | `ci.yml` — `trufflesecurity/trufflehog@main` | Medium |
| CI-2 | Workflow input interpolated straight into a remote shell command (`${{ github.event.inputs.version }}`) — anyone who can dispatch the workflow can run commands on the production host | `deploy-production.yml` | Medium (only reachable once the file parses) |
| CI-3 | Deployment by long-lived SSH private key in repository secrets, as whatever user `PROD_USER` is; no per-job restriction | `deploy-*.yml`, `backup.yml` | Medium |
| CI-4 | `rollback.sh` is `git checkout HEAD~1` + rebuild: leaves a detached HEAD, assumes one commit per deploy, restores no database | `scripts/rollback.sh` | Medium |
| CI-5 | `deploy-production.sh` ignores its `version` argument and always pulls `main`; `docker compose pull || true` hides failures | `scripts/deploy-production.sh` | Low |
| CI-6 | Health check is two unauthenticated GETs against `localhost:8069` — passes if *any* Odoo answers | `scripts/health-check.sh` | Low |
| CI-7 | Slack step announces success regardless of outcome | `backup.yml` | Low |
| CI-8 | No `permissions:` block in most workflows — jobs get the default token scope | all | Low |
| CI-9 | Workflows are not path-filtered (except Jewel, Jawhar, Faizy) | `ci.yml`, `test.yml` | Low |
| CI-10 | Public repository + workflows that hold production SSH secrets. Fork PRs do not receive secrets by default, but `environment: production` has no documented required reviewers | repo settings — **NV** | Verify |
| CI-11 | `update.sh` pulls `main` of a public repo and restarts production with no gate; merge to `main` is therefore a production release for the C2P Agency OS | `c2p-delivery-system/deploy/update.sh` | Medium |

## 4. Version control practice

| Practice | State |
|---|---|
| Protected `main` | **NV** (settings not readable). The root `CLAUDE.md` instructs committing and pushing straight to `main`, so protection is unlikely to be enforced |
| Required reviews | None evidenced. PRs are opened and merged by the same account |
| Required status checks | Cannot be required while `main` is red |
| Release identification | No tags, no changelog outside per-project build logs |
| Branch naming | `claude/<topic>-<suffix>`, `ccr-<id>`, `pharma-*`, `fix/*`, `security/*` — no environment branches (`develop` is referenced but absent) |
| What production tracks | An unmerged feature branch (R-doc) |
| Secrets | GitHub repository/environment secrets for CI; plaintext `.env` and `/etc/odoo*.conf` on the VPS; no secret manager; no rotation record |

## 5. Recommended release flow

Simple, and built from what already works here (the Jewel and Pharma kits):

```
feature branch ──PR──► main ──tag vX.Y.Z──► staging (auto) ──approval──► production (manual, gated)
      │                 │                      │                              │
   path-filtered     required:              restore last                 pre-deploy dump
   CI for that       green CI +             prod dump,                   + filestore snapshot
   project only      1 review               neutralise,                  → upgrade → health
                                            upgrade, smoke               → auto-rollback on fail
```

| Element | Standard |
|---|---|
| Branching | Trunk-based. `main` is always releasable. Short-lived feature branches. No long-lived per-client branches — client code lives in its own repository or workspace |
| Protection | `main`: PR required, one approval, required checks, no force-push, linear history |
| CI | One workflow per project, path-filtered. Required jobs: lint, unit tests, Odoo fresh-install + tests on a throwaway database, dependency audit, secret scan (pinned by commit SHA, full-history on schedule) |
| Artifacts | A release is a git tag. For Docker-based services, an image tagged with the same version. For native Odoo, the tag is what the server checks out |
| Staging | Every production Odoo database gets a staging twin on a separate unit and port, refreshed from the latest backup, **neutralised** before first start |
| Migrations | Odoo `-u` with module `migrations/` scripts, rehearsed on staging against a copy of production data. SQLite/PostgreSQL app schemas get a numbered migration directory |
| Approval | GitHub Environment `production` with required reviewers; one environment per product so a Faizy deploy cannot touch IG2 |
| Deploy | The server-side script pattern from `stage.sh`: refuse wrong branch/tag, dump first, upgrade, health-check the *named* instance, print and test the rollback command |
| Access | A dedicated `deploy` OS user with a forced-command SSH key per product, or a pull-based agent. No root over SSH from CI |
| Rollback | Code: check out the previous tag. Data: restore the pre-deploy dump + filestore. Both scripted and rehearsed |
| Record | Each deploy appends a line (who, tag, database, dump path, result) to a per-product `DEPLOY_LOG.md` — the Pharma log is the model |

## 6. Order of work (none of this is done yet)

1. Decide what `backup.yml` and `deploy-production.yml` should do **before** merging PR #168; otherwise disable those two files in the same PR (D-06).
2. Get `main` green: fix or scope the flake8 job; fix the TruffleHog invocation; merge PR #172.
3. Turn on branch protection once green.
4. Add path filters so each project only runs its own checks.
5. Introduce tags and the per-product deploy script pattern, one product at a time, starting with the C2P Agency OS (lowest data risk).
