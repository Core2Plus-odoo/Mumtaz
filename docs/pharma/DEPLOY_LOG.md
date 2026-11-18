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

## 2026-11-18 — VPS discovery (done, read-only, run by the owner on the VPS and pasted back)

`discover.sh` on `srv1446185` (187.77.128.199), Ubuntu 24.04, Odoo Server 19.0-20260719 native:

| Fact | Value | Consequence |
| --- | --- | --- |
| Odoo runtime | native `/usr/bin/odoo`, one systemd unit per tenant: `odoo` (`/etc/odoo/odoo.conf`, :8069), `odoo2` (:8070), `odoo3` (:8071), `odoo4`, `faizy-odoo`; jewel is the only Docker Odoo (:8072/:8073) | pharma gets its own unit the same way |
| Live `dbfilter` (`/etc/odoo/odoo.conf`) | `^Mumtaz` (case-sensitive, no `%d`), `db_name = Mumtaz_C2P`, `list_db = False` | `mumtaz_pharma` can never be selected by the live service; changing that means editing production config + restart. **Not done.** |
| Postgres | local, user `odoo`; `mumtaz_pharma` does not exist | install creates it |
| Free ports | 8076, 8077 | used for `odoo-pharma` |
| nginx | one vhost file per tenant in `sites-enabled`, HTTP block + certbot-managed 443 block, per-host certificate | `nginx/pharma.mumtaz.digital.conf` follows `erp.mumtaz.digital` |
| DNS | mumtaz.digital on Hostinger (`apollo/athena.dns-parking.com`); `pharma` does not resolve | A record in hPanel, same as `delivery` / `jewel` |
| Checkouts | `/opt/mumtaz` and `/opt/custom_addons/Mumtaz` are on `claude/resume-help-95ne9v`, not `main` | untouched; pharma lives in `/opt/mumtaz-pharma-staging` |

Pre-existing oddities seen and **left alone** (not part of this work): the
`erp.mumtaz.digital` vhost proxies `/longpolling` to 127.0.0.1:8073, which is
jewel's Docker websocket port; the `ig2.mumtaz.digital` vhost proxies
`/websocket` to 127.0.0.1:8074, where nothing listens; `erp-server.service` is
in `activating (auto-restart)`.

**Decision:** serve pharma from its own small unit `odoo-pharma.service` with
`/etc/odoo-pharma.conf` (`dbfilter = ^mumtaz_%d$`, addons path = the staging
checkout, same Postgres, 127.0.0.1:8076/8077, `workers = 2`). This honours the
requested dbfilter literally, matches how every other tenant on the box is
run, and never touches the production config or service.

---

## 2026-11-18 — install done on the VPS (evidence pasted back by the owner)

| Step | Status | Evidence |
| --- | --- | --- |
| `stage.sh backup` | done 11:27 UTC | `/var/local/pharma-staging/backups/{pg_globals,databases}_20261118_112747.*`, `conf_20261118_112747.tgz` (/etc/nginx, /etc/odoo*.conf, odoo*.service) |
| `stage.sh install` | **done** 11:31–11:33 UTC | Odoo log: `97 modules loaded in 70.73s`, `Modules loaded.`, `Registry loaded in 84.463s` for `mumtaz_pharma`. Odoo's own demo data off. |
| admin password | done 11:38 UTC | set interactively via `odoo shell`, not stored anywhere |
| `stage.sh verify` | done | `pharma.mode = demo`; pharma_core, pharma_pk_tax_core, pharma_reconciliation_hub, pharma_demo_data all `installed`; 97 modules total; company `Pharma Demo Co`; 2 DEMO tax rules; 3 DEMO reconciliation runs; 3 open exceptions |
| `stage.sh test` | **not yet** | first two attempts never reached Odoo (conf unreadable by `odoo`; see below), third was killed by a port clash (see below) |

Script defects found and fixed on the way (all in `stage.sh`, none on the server):
- `/var/local/pharma-staging` was created `root:staff 750`, so the `odoo` user could not read the rendered conf → Odoo exit 2 at option parsing. Fixed: dir is `root:odoo`.
- Odoo 19 lists server flags under `odoo server --help`, and takes a plain `--without-demo` (a value is refused with a warning). Fixed: version-based.
- The install success check read the stdout capture while the rendered conf sent Odoo's log to a file, so a **successful** install was reported as failed. Fixed: CLI conf has no logfile; one run log.
- `--test-enable` makes Odoo 19 start its HTTP server even with `--no-http`, and it took the default 8069 owned by the live `odoo.service` → "Port 8069 is in use". Fixed: CLI runs bind 127.0.0.1 on the first free pair from 8086.
- A cosmetic `(ERROR/3) Unexpected indentation` line during install is docutils rendering some module's description; harmless, module not yet identified (S4).

**Finding on the server (pre-existing, not changed):** `odoo2.service` (Mumtaz_ERP) and `odoo3.service` (Mumtaz_IG2) have a `dbfilter` but **no `db_name`**. Odoo's scheduler ignores `dbfilter` and, without `db_name`, polls every database on the Postgres server for cron jobs. `pg_stat_activity` showed 8 idle sessions from exactly those two processes on `mumtaz_pharma` and `mumtaz_pharma_test` within seconds of their creation. Consequences: those production processes will run our DB's scheduled jobs with an addons path that lacks `pharma_*` (expect warnings in their logs), and one of them blocked a plain `dropdb`. Recommended fix, owner's decision, production change: `db_name = Mumtaz_ERP` in `/etc/odoo2.conf`, `db_name = Mumtaz_IG2` in `/etc/odoo3.conf`, restart each. Our side: `/etc/odoo-pharma.conf` carries `db_name = mumtaz_pharma` so it never does this to them; the throwaway test DB is dropped with `--force`.

---

## Plan for the VPS (⛔ = gate, needs a named approval first)

```bash
cd /opt/mumtaz-pharma-staging && git pull --ff-only
bash deploy/pharma-staging/stage.sh backup     # pg globals, DB list, /etc/nginx + /etc/odoo*.conf + odoo*.service tarball
bash deploy/pharma-staging/stage.sh install    # odoo -c <private cli conf> -d mumtaz_pharma -i base,account,sale_management,purchase,stock,mrp,website_sale,contacts,pharma_core,pharma_pk_tax_core,pharma_reconciliation_hub,pharma_demo_data --without-demo --stop-after-init --no-http
bash deploy/pharma-staging/stage.sh test       # same -i list into mumtaz_pharma_test + --test-enable --test-tags pharma, then dropdb
```
`install` ends by **setting the admin password** interactively (a CLI-created DB
starts as admin/admin). The private CLI conf is rendered from the live conf's
db credentials only, with its own logfile, no dbfilter, and `--no-http`.

Why a throwaway DB for tests: Odoo only runs post-install tests for modules it
is installing or updating, so `--test-tags pharma` on the finished tenant would
run nothing, and `-u` would exercise an update path the deployment never takes.
Expected log line: `0 failed, 0 error(s) of 34 tests when loading database 'mumtaz_pharma_test'`.

```bash
# ⛔ new unit (no other unit/conf touched; rollback = stage.sh service-remove)
bash deploy/pharma-staging/stage.sh service
bash deploy/pharma-staging/stage.sh smoke-local   # Host: pharma.mumtaz.digital -> 127.0.0.1:8076 — proves the dbfilter mapping before DNS
```

```bash
# ⛔ DNS: A record  pharma -> 187.77.128.199  (Hostinger hPanel > Domains > mumtaz.digital > DNS)
# ⛔ nginx vhost + certificate, the same way as the other tenants
cp deploy/pharma-staging/nginx/pharma.mumtaz.digital.conf /etc/nginx/sites-available/pharma.mumtaz.digital
ln -s /etc/nginx/sites-available/pharma.mumtaz.digital /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d pharma.mumtaz.digital
bash deploy/pharma-staging/stage.sh smoke        # /web/login 200, admin login, Pharma menus, pharma.mode=demo, DEMO counts, production refuses DEMO rules
```

## Rollback (reverse order, each step independent)

```bash
rm -f /etc/nginx/sites-enabled/pharma.mumtaz.digital && nginx -t && systemctl reload nginx
certbot delete --cert-name pharma.mumtaz.digital                      # optional
bash /opt/mumtaz-pharma-staging/deploy/pharma-staging/stage.sh service-remove   # stop+disable odoo-pharma, delete unit + /etc/odoo-pharma.conf
sudo -u postgres pg_dump -Fc mumtaz_pharma > /var/local/pharma-staging/backups/mumtaz_pharma_final.dump
sudo -u postgres dropdb mumtaz_pharma                                 # the only tenant DB this work created
rm -rf /opt/mumtaz-pharma-staging /var/local/pharma-staging           # checkout, rendered confs, logs (keep backups if wanted)
# remove the A record in Hostinger
```
The forward path never writes to `/etc/odoo/odoo.conf`, any other
`/etc/odooN.conf`, any other unit, any other vhost, `/opt/mumtaz`, or any other
database.

## Differences from the repo's usual deploy path

- `c2p-delivery-system/deploy/update.sh` and `ops/deployment/deploy.sh` pull a
  branch into the production checkout; this tenant has its own clone.
- The requested `dbfilter ^mumtaz_%d$` is **not** what the live service runs
  (`^Mumtaz`), so it is applied on a dedicated unit instead of the shared one.
- `--without-demo=all` became a plain `--without-demo` flag in Odoo 19;
  `stage.sh` probes `odoo --help` and uses whichever the build accepts.
- Tests run on a throwaway database created by the same `-i` list.
- The vhost adds `X-Robots-Tag: noindex` because the data is fictional.

## Known gaps (not changed, flagged)

- **There is no DEMO banner in the addons.** "DEMO" shows as the company name
  *Pharma Demo Co*, a `DEMO` column on every list, and `(fictional)` in record
  names. A visible banner when `pharma.mode = demo` would be a new feature;
  not added without approval.
- No `l10n_pk` in the install list, so the chart of accounts is Odoo's generic
  one; `pharma_pk_tax_core` does not depend on it.
- `pharma_demo_data` grants `admin` every Pharma role for convenience; its
  manifest says never to install it on production, and `pharma.mode` defaults
  to `production` in `pharma_pk_tax_core`, which refuses DEMO rules.
