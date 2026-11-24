# Scripts

Run from the repository root. The three groups are not interchangeable:
the first is safe anywhere, the second needs a throwaway PostgreSQL, the
third touches a server.

## Checks (safe anywhere, change nothing)

| Script | What it does | Run by |
| --- | --- | --- |
| `module_registry.py` | `--check`: every Odoo module is classified and no module depends on a higher layer. `--write`: regenerate `registry.yaml` | `ci.yml` |
| `check_sudo.py` | Every `sudo()` in `addons/` carries a `# sudo: <reason>` comment | `ci.yml` |
| `check_links.py` | Every link in the Jawhar public site resolves | `ci.yml` |
| `validate-deployment.py` | Key files exist before a deploy | by hand |
| `audit/` | Read-only inventory of the addons tree (module list with risk flags, access-rule coverage, field list). Parses source; runs nothing from `addons/`. Its own `README.md` has the commands | by hand |

## Test runs (create and drop their own databases)

They refuse to run on `main` and only touch databases whose names they build.

| Script | What it proves | Run by |
| --- | --- | --- |
| `platform_ci.sh` | Every non-jewellery module installs, upgrades and passes its tests on a fresh Odoo 19 database | `platform-odoo-install.yml` |
| `jewel_ci.sh` | The Jawhar modules install and pass their suite; seeds the synthetic demo | `jewel-odoo-tests.yml` |
| `tenant_journey_ci.sh` (+ `tenant_journey/`) | Registration → entitlement → a real staging tenant database → sign-in over HTTP | `platform-odoo-install.yml` |

## Server-side (do not run without approval)

These act on a server. Several target a Docker Compose stack that the audit
could not find on the VPS (`docs/infrastructure-audit/08_DEPLOYMENT_AND_CICD_AUDIT.md`, audit decision D-06).

| Script | Intended purpose | State |
| --- | --- | --- |
| `deploy-production.sh`, `deploy-staging.sh`, `rollback.sh`, `health-check.sh` | Compose-based deploy, rollback and health check | Called by `deploy-production.yml` / `deploy-staging.yml`; target stack unverified |
| `backup.sh` | Database and filestore backup | Called by `backup.yml`, which has never succeeded |
| `setup-vps.sh`, `update-nginx-domains.sh`, `deploy-architecture-review.sh` | One-off server set-up and nginx generation | Not called by any workflow; review before use |
| `migrate.py` | Upgrade selected modules in a named database | By hand; back up first |
| `smoke-test.sh` | End-to-end smoke test against a running platform | By hand |
| `mumtaz_site_add_blocks.py` | Adds blocks to an existing Mumtaz website preview page | By hand, in an Odoo shell |

The deploy commands that are actually used live with their product:
`c2p-delivery-system/deploy/update.sh`, `deploy/jewel-staging/`, `faizy/`.
