# Pharma staging — deployment log

Tenant: generic **pharma** · host `pharma.mumtaz.digital` · DB `mumtaz_pharma`
(selected by the existing `dbfilter = ^mumtaz_%d$`) · Odoo 19 Community ·
branch `pharma-erp-v0.1` · **staging only, fictional DEMO data**.

Every entry says what was actually run and where. Nothing below is marked done
unless it was executed and its output seen.

---

## 2026-11-18 — code staged (done, in the cloud checkout, not on the VPS)

| Step | Status | Detail |
| --- | --- | --- |
| Read repo conventions | done | `CLAUDE.md`, `docs/DEPLOYMENT.md`, `docs/VPS_SETUP.md`, `docs/ARCHITECTURE.md`, `ops/deployment/*`, `deploy/jewel-staging/*` |
| Branch `pharma-erp-v0.1` | done | Did not exist on origin; created from `origin/main` at `fd646ab`. |
| Unzip `pharma-addons.zip` | done | `addons/pharma_core`, `addons/pharma_pk_tax_core`, `addons/pharma_reconciliation_hub`, `addons/pharma_demo_data`, `docs/pharma/` copied unchanged. Nothing renamed. |
| Static checks | done | `py_compile` clean; every XML parses; `pyflakes` reports only Odoo's `__init__` re-export pattern and 3 unused local names, left as-is. |
| Test inventory | done | `@tagged("post_install", "-at_install", "pharma")`: 18 in `pharma_pk_tax_core`, 16 in `pharma_reconciliation_hub` = **34**, matching the expectation. |
| Staging kit | done | `deploy/pharma-staging/{discover.sh, stage.sh, nginx/pharma.mumtaz.digital.conf, README.md}` — written, bash-syntax-checked, **not yet executed anywhere**. |
| Commit on branch | done | `c9a8605` (addons + docs), plus this log and the kit. Not pushed to `main`; no PR to `main`. |

The second archive attached, `pharma-erp.zip`, is the framework-independent
Python prototype (`pharma_core/*.py`, pytest suite, HTML demo builder). It is
not an Odoo addon set and was not added to the repo.

### Why the VPS steps are not done yet

The cloud session that did the above has no SSH client, no key, and the VPS
refuses port 22 from it; its HTTPS egress also blocks `*.mumtaz.digital`. Steps
1–5 below have to run from a machine that can SSH to `187.77.128.199`.

---

## Plan for the VPS (pending — each ⛔ is a gate that needs a named approval)

```bash
# 0. clone the branch beside, never inside, /opt/mumtaz (which tracks main)
git clone <repo> /opt/mumtaz-pharma-staging && cd /opt/mumtaz-pharma-staging && git checkout pharma-erp-v0.1
bash deploy/pharma-staging/discover.sh          # read-only; decides native-vs-docker, ports, dbfilter, addons_path
```

```bash
# 1. backup, then DB + modules (Odoo's own demo off, pharma DEMO data on)
bash deploy/pharma-staging/stage.sh backup      # pg globals, DB list, /etc/nginx + odoo.conf tarball
bash deploy/pharma-staging/stage.sh install     # odoo -d mumtaz_pharma -i base,account,sale_management,purchase,stock,mrp,website_sale,contacts,pharma_core,pharma_pk_tax_core,pharma_reconciliation_hub,pharma_demo_data --without-demo --stop-after-init
```
`install` runs with a rendered private config (live `odoo.conf` + this
checkout's `addons/`, no `dbfilter`, own logfile) and then **sets the admin
password** interactively, because a CLI-created database starts with
`admin/admin` and this host will be public.

```bash
# 2. tests — fresh install into a throwaway DB, exactly the deployment path, then dropped
bash deploy/pharma-staging/stage.sh test        # ... --test-enable --test-tags pharma --stop-after-init
# expected log line:  0 failed, 0 error(s) of 34 tests when loading database 'mumtaz_pharma_test'
```
Why a throwaway DB: Odoo only runs post-install tests for modules it is
installing or updating, so `--test-tags pharma` on the already-installed
`mumtaz_pharma` would run nothing, and `-u` would exercise an update path the
deployment never takes.

```bash
# 3. ⛔ DNS: A record  pharma -> 187.77.128.199  (Hostinger hPanel > Domains > mumtaz.digital > DNS; same as `delivery`)
# 3. ⛔ nginx block (mirrors erp.mumtaz.digital incl. /websocket) + certificate, same way as the other tenants
cp deploy/pharma-staging/nginx/pharma.mumtaz.digital.conf /etc/nginx/sites-available/pharma.mumtaz.digital
ln -s /etc/nginx/sites-available/pharma.mumtaz.digital /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d pharma.mumtaz.digital
```

```bash
# 3b. ⛔ make the four pharma addons visible to the LIVE service (pick one after serve-check)
bash deploy/pharma-staging/stage.sh serve-check
#   A) symlink addons/pharma_* into the live addons dir  (no restart; `rm` the links to roll back)
#   B) append /opt/mumtaz-pharma-staging/addons to addons_path in /etc/odoo/odoo.conf and `systemctl restart odoo`  (restart window)
```

```bash
# 4–5. smoke: /web/login 200, admin login, Pharma menus (Tax Centre, Reconciliation, Exception Queue),
#       pharma.mode == demo, DEMO record counts, and "production refuses DEMO rules" (odoo shell, rolled back)
bash deploy/pharma-staging/stage.sh smoke
```

## Rollback (reverse order, each step independent)

```bash
rm -f /etc/nginx/sites-enabled/pharma.mumtaz.digital && nginx -t && systemctl reload nginx   # site gone; cert can stay
certbot delete --cert-name pharma.mumtaz.digital                                             # optional
# undo 3b: remove the symlinks, or remove the addons_path entry and restart odoo
sudo -u postgres pg_dump -Fc mumtaz_pharma > /opt/mumtaz/pharma-staging/backups/mumtaz_pharma_final.dump
sudo -u postgres dropdb mumtaz_pharma                                                        # the only tenant DB this work created
rm -rf /opt/mumtaz-pharma-staging /opt/mumtaz/pharma-staging                                  # checkout, rendered conf, logs (keep backups if wanted)
# remove the A record in Hostinger
```
No other database, the live `odoo.conf`, `/opt/mumtaz`, or any other vhost is
touched by the forward path, so there is nothing else to undo.

## Differences from the repo's usual deploy path

- `c2p-delivery-system/deploy/update.sh` and `ops/deployment/deploy.sh` both
  pull **main** into the production checkout; this tenant lives on a feature
  branch, so it uses its own clone, like `deploy/jewel-staging` proposes.
- `--without-demo=all` became a plain `--without-demo` flag in Odoo 19;
  `stage.sh` probes `odoo --help` and uses whichever the installed build takes.
- Tests run on a throwaway database created by the same `-i` list (see above),
  not on the tenant database.
- The nginx block addresses `127.0.0.1:8069/8072` directly and has no
  `limit_req`, so it loads independently of the shared upstream/zone names in
  `nginx-mumtaz-platform.conf`; it adds `X-Robots-Tag: noindex` because the
  data is fictional.

## Known gaps (not changed, flagged)

- **There is no DEMO banner in the addons.** "DEMO" shows as the company
  name *Pharma Demo Co*, a `DEMO` column on every list, and `(fictional)` in
  record names. A visible banner (e.g. a systray/ribbon when
  `pharma.mode = demo`) would be a new feature; not added without approval.
- The install list has no `l10n_pk`, so the chart of accounts is Odoo's
  generic one; `pharma_pk_tax_core` does not depend on it.
- `pharma_demo_data` grants `admin` every Pharma role for convenience; its
  manifest says never to install it on production, and `pharma.mode`
  defaults to `production` in `pharma_pk_tax_core`, which refuses DEMO rules.
