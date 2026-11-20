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
| `stage.sh test` | **done** 11:41–11:43 UTC | fresh `-i` of the full list into `mumtaz_pharma_test` on 127.0.0.1:8086 with `--test-enable --test-tags pharma`: **`0 failed, 0 error(s) of 34 tests when loading database 'mumtaz_pharma_test'`**, `34 post-tests in 2.55s, 2040 queries`. Log: `/var/local/pharma-staging/logs/test_20261118_114145.log`. Test DB dropped (`--force`, 5 poller sessions from odoo2/odoo3 ended). Two `odoo.sql_db: bad query` ERROR lines are the `pharma_tax_event` unique constraint firing inside the duplicate-withholding test, expected; add `@mute_logger('odoo.sql_db')` to that test (S4). |

Script defects found and fixed on the way (all in `stage.sh`, none on the server):
- `/var/local/pharma-staging` was created `root:staff 750`, so the `odoo` user could not read the rendered conf → Odoo exit 2 at option parsing. Fixed: dir is `root:odoo`.
- Odoo 19 lists server flags under `odoo server --help`, and takes a plain `--without-demo` (a value is refused with a warning). Fixed: version-based.
- The install success check read the stdout capture while the rendered conf sent Odoo's log to a file, so a **successful** install was reported as failed. Fixed: CLI conf has no logfile; one run log.
- `--test-enable` makes Odoo 19 start its HTTP server even with `--no-http`, and it took the default 8069 owned by the live `odoo.service` → "Port 8069 is in use". Fixed: CLI runs bind 127.0.0.1 on the first free pair from 8086.
- A cosmetic `(ERROR/3) Unexpected indentation` line during install is docutils rendering some module's description; harmless, module not yet identified (S4).

**Finding on the server (pre-existing, not changed):** `odoo2.service` (Mumtaz_ERP) and `odoo3.service` (Mumtaz_IG2) have a `dbfilter` but **no `db_name`**. Odoo's scheduler ignores `dbfilter` and, without `db_name`, polls every database on the Postgres server for cron jobs. `pg_stat_activity` showed 8 idle sessions from exactly those two processes on `mumtaz_pharma` and `mumtaz_pharma_test` within seconds of their creation. Consequences: those production processes will run our DB's scheduled jobs with an addons path that lacks `pharma_*` (expect warnings in their logs), and one of them blocked a plain `dropdb`. Recommended fix, owner's decision, production change: `db_name = Mumtaz_ERP` in `/etc/odoo2.conf`, `db_name = Mumtaz_IG2` in `/etc/odoo3.conf`, restart each. Our side: `/etc/odoo-pharma.conf` carries `db_name = mumtaz_pharma` so it never does this to them; the throwaway test DB is dropped with `--force`.

---

## 2026-11-18 — service, neutralize, nginx done; DNS + certificate pending (owner-run, evidence pasted back)

| Step | Status | Evidence |
| --- | --- | --- |
| `stage.sh service` (gate 1, approved by owner) | **done** 11:45 UTC | `odoo-pharma.service` active, enabled; PIDs: main, 2 workers, gevent, cron; 254 MB; `/web/health` on 127.0.0.1:8076 → 200. Re-run correctly refused ("port in use"). |
| `smoke-local` | partial | `/web/login` via 127.0.0.1:8076 with `Host: pharma.mumtaz.digital` → **200** (dbfilter `^mumtaz_%d$` maps the host to `mumtaz_pharma`). XML-RPC login returned 500 — client sent two Host headers (python xmlrpc adds its own); replaced by JSON-RPC with one header, re-run pending; server-side log not yet read. |
| `stage.sh neutralize` (approved by owner) | **done** 11:48 UTC | `odoo.cli.neutralize: Neutralization finished`; `database.is_neutralized = true`; `pharma.mode = demo`; 1 active cron (autovacuum, as Odoo leaves it); 1 active mail server = Odoo's placeholder "neutralization - disable emails" → nothing can send. `odoo-pharma` restarted alone; health 200. |
| Memory / other units | ok | `free`: 4.1 GiB used, 3.6 GiB available. `odoo`, `odoo2`, `odoo3`, `odoo4`, `faizy-odoo`, `odoo-pharma` all `active`. |
| nginx vhost (gate 2, approved) | **done** ~11:56 UTC | `/etc/nginx/sites-available/pharma.mumtaz.digital` + symlink in `sites-enabled`; `nginx -t` ok; reloaded; `curl -H 'Host: pharma.mumtaz.digital' http://127.0.0.1/web/login` → **200**. |
| DNS A record `pharma → 187.77.128.199` | **pending** | not yet added in Hostinger hPanel; `getent hosts pharma.mumtaz.digital` empty |
| `certbot --nginx -d pharma.mumtaz.digital` | **failed once, expected** | Let's Encrypt: `NXDOMAIN looking up A for pharma.mumtaz.digital`. Retry only after DNS resolves (5 failures/hour limit). |
| `stage.sh smoke` (HTTPS), browser login, banner + menus | pending | needs DNS + certificate |

---

## 2026-11-18 — public side: DNS, certificate, HTTPS live (owner-run, evidence pasted back)

| Step | Status | Evidence |
| --- | --- | --- |
| 1. DNS A record | **done** by the owner in Hostinger hPanel, ~16:00 Dubai (12:00 UTC) | `Type A | Name pharma | Content 187.77.128.199 | TTL 14400`. Nothing else added or changed; no pharma record existed before. Resolution confirmed externally by the owner. |
| 2. Resolution on the VPS | done ~12:05 UTC | `getent hosts pharma.mumtaz.digital` → 187.77.128.199; `dig +short pharma.mumtaz.digital @1.1.1.1` → 187.77.128.199 |
| 3. Certificate | **done** 12:06 UTC, one attempt | `certbot --nginx -d pharma.mumtaz.digital --redirect --non-interactive`: "Successfully received certificate", deployed to `/etc/nginx/sites-enabled/pharma.mumtaz.digital`; `nginx -t` ok; reloaded. Certificate Name `pharma.mumtaz.digital`, ECDSA, Domains `pharma.mumtaz.digital`, **Expiry 2027-02-16 11:06:37 UTC (89 days)**, path `/etc/letsencrypt/live/pharma.mumtaz.digital/`. Auto-renew scheduled by certbot. (The earlier NXDOMAIN failure at 11:57 UTC was before the record existed.) |
| 4. HTTPS smoke | **done** 12:12 UTC | `https://pharma.mumtaz.digital/web/login` → **200**. Admin login over HTTPS (JSON-RPC `/web/session/authenticate`): **OK, uid 2**, session on `mumtaz_pharma`; 14 Pharma menus reachable through the web session. Shell checks: company `Pharma Demo Co`; `pharma.mode: demo`; `neutralized: true`; **14 of 14 Pharma menus visible to admin**, including Tax Centre, Reconciliation, Reconciliation/Exception Queue (`required menus present: YES`); DEMO data all flagged: tax rules 2/2, tax events 8/8, recon runs 3/3, exceptions 3/3, partner stock lines 2/2, raw events 6/6. **Production mode refuses DEMO rules:** `needs_approval | rule DEMO-RULE-1 is DEMO-only and refused in production`; transaction rolled back; `pharma.mode` re-read by SQL = `demo`; `stage.sh verify` independently shows `pharma.mode = demo`. Earlier runs at 12:07 showed `Access Denied` (password typed did not match) and a misleading post-rollback line read from the ORM cache; both script-side, fixed. |
| Admin login | changed by owner request 12:09 UTC | `base.user_admin` login set to the owner's work e-mail via `stage.sh admin-login`; password set interactively by the owner, not recorded. Owner was warned that the chosen password is weak for an internet-facing host; their call for a neutralized demo. |
| 5. Browser check (banner, Pharma menu, screenshot) | owner, pending | — |
| 6a. Cause of the earlier XML-RPC 500 | **explained** | `/var/log/odoo/odoo-pharma.log`: `ValueError: Port could not be cast to integer value as '8076,pharma.mumtaz.digital'` on `POST /xmlrpc/2/common` at 11:48:08 — the Python xmlrpc client sent its own Host header plus mine, werkzeug merged them. Client-side bug in the smoke script, not the server; replaced by a single-header JSON-RPC call. |
| 6b. `smoke-local` re-run | same as 4 | loopback `/web/login` with Host header → 200; login Access Denied (same typed password); same shell-step gap. |

**Live:** https://pharma.mumtaz.digital (staging, fictional DEMO data, neutralized, noindex). Certificate expires **2027-02-16**, certbot auto-renews.

Remaining script tidy-ups noted, none affecting the deployment (S4): `@mute_logger('odoo.sql_db')` on the duplicate-withholding test; `_()` wrapping of user-facing strings in the addons; unused names flagged by pyflakes; identify the module whose RST description triggers the docutils warning at install.

---

## 2026-11-18 — build: website + demo data for every scenario (committed on the branch, NOT yet on staging)

Owner asked for "design website, demo data, all scenarios". Built, compile- and XML-checked, not yet run on any Odoo:

- **`pharma_demo_data` 19.0.1.0.0 → 19.0.1.1.0.** The one-shot `post_init_hook` became an idempotent seeder
  (`pharma.demo.seed.seed()`), called by the hook on install and by `migrations/19.0.1.1.0/post-migrate.py` on
  `-u`, so the live staging DB gets the new scenarios through the real upgrade path (version bump → migration),
  never by reinstall. Natural keys (rule code, SKU, login, run name, event id, order ref) prevent duplicates.
  Scenarios added: 4 demo users (one per Pharma role); rules draft / evidence-missing / effective-dated /
  overlapping (ambiguous) / superseded; SKU D (ambiguous class) and E (classification proposed, awaiting approver);
  a tax-event reversal; raw-event replay and conflict; a clean COD batch, a bank-vs-ledger run with exact match,
  amount difference, ambiguous amount/date and a low-confidence match; exceptions in all four states driven through
  the real buttons (take ownership, propose, approve by a second controller); two more partner stock lines
  (surplus and zero variance) and an incomplete commercial-model record (gate blocked); a confirmed sale order
  and posted invoice for the approved SKU, and a quotation plus draft invoice for the pending SKU that the gate
  refuses. Placeholder product images generated with Pillow, stamped DEMO. `set_demo_passwords()` for the
  staging script; no password in code. 12 new tests (`tests/test_demo_seed.py`), tagged `pharma`.
- **`pharma_website_demo` 19.0.1.0.0 (new).** Depends on `website_sale` + `pharma_demo_data`. DEMO ribbon
  inserted before `div#wrapwrap/header` of `website.layout` (verified against Odoo 19 source) while
  `pharma.mode = demo`; demo home page at `/pharma` set as `website.homepage_url`; products published into
  two public categories; website renamed "Pharma Demo Co (DEMO)". Idempotent seeder, post_init_hook.
- **`docs/pharma/DEMO_SCENARIOS.md`**: presenter script, per scenario: user, menu, action, expected result.
- **`stage.sh`**: module list includes `pharma_website_demo`; `upgrade` (dump → `-u` installed pharma modules /
  `-i` new ones → restart `odoo-pharma` only → verify, prints the exact rollback); `demo-passwords`; `verify`
  shows exceptions/rules by state, demo users, published products, homepage; `smoke` also checks `/`, `/pharma`,
  `/shop` return 200 and that the DEMO ribbon and product names appear in `/shop`.

Expected test count after upgrade: 34 + 12 = **46**. Staging steps pending owner approval (gate: restart of
`odoo-pharma` only; nothing else touched).

---

## 2026-11-18 — upgrade attempt 1 of the demo build, findings, and the wellness redesign (committed, NOT yet on staging)

**Evidence from the VPS (owner-run, pasted back):**
- `stage.sh test` on the throwaway DB: `1 failed, 2 error(s) of 12 tests`. Original `test_tax` / `test_recon` died in `setUpClass`
  with *"You can not have two users with the same login!"*: my seeder created `demo_ops`, `demo_maker`, `demo_approver`,
  which the handed-over test suites create themselves. `test_seed_is_idempotent` failed because the two invoice scenarios were
  skipped on a fresh install (the chart of accounts is loaded after the post-install hook) and created on the second `seed()`.
  The upgrade was nevertheless run (owner's call) and **succeeded on the live staging DB**: dump
  `/var/local/pharma-staging/backups/mumtaz_pharma_pre_upgrade_20261118_123551.dump` (11 MB), migration 19.0.1.1.0 ran,
  `pharma_demo_data: seed complete (idempotent)`, `98 modules loaded`, `pharma_website_demo` installed, `odoo-pharma` restarted
  alone, health 200, `stage.sh smoke` fully green (`/`, `/pharma`, `/shop` 200, DEMO ribbon YES, five products listed, login OK,
  14 of 14 menus, demo counts, production refusal, mode `demo` by SQL). `demo-passwords` set on the four demo users.

**Fixes (pharma_demo_data 19.0.1.1.1, migration `19.0.1.1.1` renames in place, nothing deleted):**
- Seeded logins are now `pharma.ops`, `pharma.maker`, `pharma.approver`, `pharma.finance`; the seeder renames the four
  `demo_*` users already on staging (same records, same passwords) instead of creating a second set. Handed-over tests untouched.
- The seeder loads the generic chart of accounts itself when no sales journal exists, so the invoice scenarios exist on a fresh
  install; the idempotency test reaches the steady state first.

**Health and wellness look (owner request), pharma_website_demo 19.0.1.1.0:**
- `static/src/css/wellness.css` (plain CSS, no external fonts or images, declared in `web.assets_frontend`): sage / forest / cream /
  sand / terracotta palette, serif headings, pill buttons, rounded soft-shadow cards, calm header and footer, restyled shop grid,
  product page and DEMO ribbon (now terracotta, still unmissable). Selectors verified against Odoo 19 `website_sale` markup
  (`.oe_product`, `.o_wsale_product_grid_wrapper`, `#product_detail`, `#add_to_cart`).
- New `/pharma` home: hero with product art, trust strip, featured products read live from the shop, three control cards, a
  "demonstration, clearly marked" panel. Verified in the real source: `slug`, `len`, `website.currency_id`, the monetary
  `t-options` pattern are all used by stock templates.
- Generated artwork (Pillow, no files committed): five pastel pack illustrations with botanical sprigs, every one stamped DEMO /
  fictional / "no health claims"; a leaf-and-wordmark logo set on the website. Versioned (`pharma.demo.image_version`), so an
  existing DB gets the new art exactly once.
- Products renamed in place by SKU to shop-ready names (Green Leaf Infusion, Golden Chai Blend, Rose Petal Tea, Lavender Evening
  Infusion, Warm Spice Mix, each "(DEMO)"); the control each one demonstrates moved from the name into the internal note.
  Categories renamed Infusions / Blends & Mixes; shop order A to E. Copy makes no health claim; a test asserts that.
- Rendered the real template markup with the real CSS plus Bootstrap 5.3.3 in headless Chromium at 1440 px and 390 px (home, shop,
  product page) and fixed what it showed: invisible heading on the dark note panel (selector specificity) and an over-crowded
  hero collage. This is a design check only; it is not Odoo, so the render test below is the integration check.
- 7 new HTTP tests fetch `/pharma`, `/shop` and a product page as a visitor, check ribbon, names, no-health-claims wording, the
  frontend CSS bundle (fetched and searched for the wellness variables), seeded state and website-seed idempotency.

Expected on a fresh install: **54 tests** (18 + 16 + 13 + 7). Pending on staging: `test`, then `upgrade` (restarts `odoo-pharma` only),
`smoke`, and a browser look. Rollback of the upgrade is the dump above plus the command `stage.sh upgrade` prints.

---

## 2026-11-18 — wellness build is LIVE on staging: 54/54 tests, upgrade 2, smoke green (owner-run, output pasted back)

| Step | Result | Evidence |
| --- | --- | --- |
| `stage.sh test` (fresh install, throwaway DB, 12:46–12:48 UTC) | **PASS** | `54 post-tests in 38.72s, 3738 queries`; `0 failed, 0 error(s) of 54 tests when loading database 'mumtaz_pharma_test'`. Log `/var/local/pharma-staging/logs/test_20261118_124627.log`. Test DB dropped (`--force`, 2 poller sessions ended). The two `bad query` ERROR lines are the tax-event unique constraint firing inside the duplicate-withholding test (expected). The per-module stats add to 62 because Odoo also counts class-level setup entries; the result line is the authoritative 54. |
| `stage.sh upgrade` (12:48 UTC) | **done** | dump `/var/local/pharma-staging/backups/mumtaz_pharma_pre_upgrade_20261118_124848.dump` (11 MB). `-u` of all five pharma modules. `pharma_demo_data: Running upgrade [19.0.1.1.1>] post-migrate` → `seed complete (idempotent)`; `pharma_website_demo: Running upgrade [19.0.1.1.0>] post-migrate`; `98 modules loaded in 5.39s`; `Modules loaded.` `odoo-pharma` restarted alone, health 200. Rollback: the command the script printed, using that dump. |
| verify | as designed | `pharma.mode = demo`; demo users now `pharma.approver, pharma.finance, pharma.maker, pharma.ops` (the earlier `demo_*` users renamed in place, passwords carried over); published DEMO products 5; `website homepage_url = /pharma`; exceptions closed=1 investigating=1 open=3 pending_approval=1; rules approved=5 draft=2 superseded=1 |
| `stage.sh smoke` (HTTPS) | **PASS** | `/web/login`, `/`, `/pharma`, `/shop` all 200; `DEMO ribbon on /shop: YES`; shop lists Golden Chai Blend, Green Leaf Infusion, Lavender Evening Infusion, Rose Petal Tea, Warm Spice Mix; login as the owner's admin OK uid 2; 14 of 14 Pharma menus; demo counts all flagged (tax rules 8, tax events 9, recon runs 5, exceptions 6, stock lines 4, raw events 8); production mode refuses DEMO rules; `pharma.mode` by SQL = `demo`. |

History note: the first upgrade at 12:35 UTC (dump `..._pre_upgrade_20261118_123551.dump`) ran the earlier build whose seeded `demo_*` logins collided with the handed-over tests; it is superseded by the run above. Both dumps are still on the VPS.

**Not yet verified by anyone:** the visual result in a browser (wellness theme, DEMO ribbon, neutralized banner, `/pharma` layout). The 7 storefront HTTP tests prove the pages render and contain the right content; they cannot judge how it looks. Owner to look at https://pharma.mumtaz.digital and report.

---

## 2026-11-18 — accounting kit: fetched, reviewed, hardening module and test steps written (NOT installed)

Owner asked for "the accounting module" from the Cybrosys page. Details, findings and decisions: `docs/pharma/ACCOUNTING_KIT.md`.

- Network: `www.cybrosys.com` added to the allowed hosts of the personal `mumtaz` environment (owner approved on the card). Reads of the
  public vendor repository went through the session's git proxy (read only). Nothing was downloaded to or run on the VPS.
- Source pinned: CybroOdoo/cybroaddons, branch 19.0, commit `fdeea97df75b7b45a6ed0f9af3c0e9850399f517`: `base_accounting_kit` 19.0.3.3.1,
  `base_account_budget` 19.0.1.0.2, `cybrosys_support_client` 19.0.1.1.0, all LGPL-3. Not vendored into this repository.
- Two S2 findings: unguarded superuser Excel export route; support form open to every user that can post data to the vendor.
  Also: the kit rewrites core accounting group records (S3).
- New module `pharma_accounting_hardening` 19.0.1.0.0: guards `/xlsx_report`, makes the support form administrator-only, forces the support
  endpoint to a dead loopback address on every upgrade. 8 tests, tagged `pharma`, including two that prove the tax gate still fires with the kit.
- `stage.sh`: `thirdparty`, `deps`, `test-kit`, `test-combined`, `install-accounting`, `accounting-off`; `verify` shows the kit modules, the endpoint
  and the support form's group. Dry-tested here: config renderer with and without the third-party path, version extraction against the real manifests,
  shellcheck (no errors). Fixed on the way: a heredoc cut that left the old unit body in `cmd_service` (caught by `bash -n`), and a quoting bug in the
  version extraction that would have missed double-quoted manifests (caught by testing the exact script text).
- Not run on any Odoo: the hardening tests have never executed. First run is `test-combined`.
- Expected: `test-kit` all vendor tests pass; `test-combined` **62 tests** (54 + 8), `0 failed, 0 error(s)`.

---

## 2026-11-18 — accounting kit: fetched on the VPS, packages present, vendor tests pass (owner-run, output pasted back)

| Step | Result | Evidence |
| --- | --- | --- |
| `stage.sh thirdparty` (~12:57 UTC) | **done** | `/opt/thirdparty/cybroaddons` at the pinned commit `fdeea97df75b7b45a6ed0f9af3c0e9850399f517` (2026-11-13); `base_accounting_kit` 19.0.3.3.1, `base_account_budget` 19.0.1.0.2, `cybrosys_support_client` 19.0.1.1.0, all LGPL-3. Source only, nothing installed. |
| `stage.sh deps` | **nothing to do** | `openpyxl`, `ofxparse`, `qifparse`, `xlsxwriter` already importable by the odoo user. No pip run, `/opt/thirdparty/pydeps` not created, no system change. |
| `stage.sh test-kit` (12:58–13:00 UTC) | **PASS** | fresh throwaway DB with only the kit: `83 post-tests in 49.30s, 44025 queries`; `0 failed, 0 error(s) of 83 tests`. The vendor's own suite (kit, budget, support client) passes on this Odoo 19 build. Log `/var/local/pharma-staging/logs/test_kit_20261118_125838.log`. Test DB dropped (`--force`, 5 poller sessions ended). |
| `stage.sh test-combined` (started ~13:01 UTC) | **result not yet seen** | the paste ends at the line announcing the run. Expected `0 failed, 0 error(s)` of 62 tests (54 + 8 hardening). Never run before; its hardening tests have not executed on any Odoo until now. |

Still gated and not done: `install-accounting` (dump, install, neutralize, restart `odoo-pharma` only). Waits for a green `test-combined` and the owner's go.

---

## 2026-11-18 — accounting kit: first combined run, 61 of 62, one test defect fixed (owner-run, output pasted back)

`stage.sh test-combined` (13:00–13:03 UTC), fresh throwaway DB with our five modules, the kit, the budget and support modules and the
hardening module, tag `pharma`: `62 post-tests in 35.86s, 4432 queries`; **`1 failed, 0 error(s) of 62`**. Log
`/var/local/pharma-staging/logs/test_combined_20261118_130028.log`.

- **Passed, first time they ever ran:** the guard on `/xlsx_report` (403 for portal and plain internal users, 403 for a model that is not an
  exporter, reaches the kit for an accountant), the administrator-only support form, the dead support endpoint, and both tax-gate tests with the
  kit installed (an unclassified product still cannot be posted; an approved one still posts). All 54 earlier pharma tests also pass with the kit installed.
- **Failed:** `test_endpoint_is_enforced_on_every_upgrade`. Defect in the test, not the control: it asserted the data file never contains the text
  "noupdate", and the file's own comment says "Not noupdate on purpose". The data record is a plain `<function>` call outside any `noupdate` block.
- **Fix:** the test now parses the XML and asserts that no element carries `noupdate="1"` and that exactly one `ir.config_parameter.set_param` call exists.
  Checked against the real file here. Needs one more `test-combined` run for a clean record; expect `0 failed, 0 error(s) of 62`.

---

## 2026-11-18 — accounting kit: combined run green, 62/62; live install is the next gate (owner-run, output pasted back)

`stage.sh test-combined` after the test fix (13:03–13:06 UTC): `62 post-tests in 30.84s, 4432 queries`; **`0 failed, 0 error(s) of 62 tests`**.
Log `/var/local/pharma-staging/logs/test_combined_20261118_130348.log`. Test DB dropped (`--force`, 6 poller sessions ended).

Evidence now in hand for the live install:

| Check | Result |
| --- | --- |
| vendor suite (kit, budget, support client) on this Odoo 19 build, database without our modules | 83 of 83 pass |
| our 54 earlier tests with the kit installed in the same database | pass |
| `/xlsx_report`: 403 for portal and plain internal users, 403 for a non-exporter model, reaches the kit for an accountant | pass |
| vendor support form: administrator-only; endpoint is a dead loopback address | pass |
| tax gate with the kit installed: unclassified product refuses to post, approved product posts | pass |

**Not yet done:** `stage.sh install-accounting` (dump, install the four modules, neutralize again, add the kit folder to `/etc/odoo-pharma.conf`,
restart `odoo-pharma` only, verify, print rollback). Gated on the owner's go.

---

## 2026-11-18 — accounting kit INSTALLED in mumtaz_pharma (owner-run `stage.sh install-accounting`, output pasted back)

| Step | Result | Evidence |
| --- | --- | --- |
| dump (13:06 UTC) | done | `/var/local/pharma-staging/backups/mumtaz_pharma_pre_accounting_20261118_130642.dump` (11 MB) |
| install | **done** | `-i base_accounting_kit,base_account_budget,cybrosys_support_client,pharma_accounting_hardening`; `103 modules loaded in 6.74s, 4006 queries`; `Modules loaded.`; no ERROR lines (the script aborts on any). Log `/var/local/pharma-staging/logs/accounting_20261118_130642.log`. |
| neutralize again | done | `odoo.modules.neutralize: Neutralization finished`: the kit's new scheduled actions are switched off again. |
| service | done | kit folder added to `/etc/odoo-pharma.conf`; only `odoo-pharma` restarted; health 200. No python-packages folder was needed (all four packages were already installed), so the unit has no `PYTHONPATH`. |
| verify | as designed | modules installed total **103** (was 98); `base_accounting_kit` 19.0.3.3.1, `base_account_budget` 19.0.1.0.2, `cybrosys_support_client` 19.0.1.1.0, `pharma_accounting_hardening` 19.0.1.0.0 all `installed`; `pharma.mode = demo`; all earlier demo counts unchanged. |
| the two controls, live | in place | vendor support endpoint = `http://127.0.0.1:9/support-disabled-by-pharma-accounting-hardening`; vendor support form open to group `Role / Administrator` only; an anonymous POST to `/xlsx_report` answers **303** (redirect to login), no file. |

Rollback if ever needed (printed by the script): stop `odoo-pharma`, drop and recreate `mumtaz_pharma`, `pg_restore` the dump above, `stage.sh accounting-off`.

**Not yet verified:** (1) that only the expected scheduled actions are active after neutralize; (2) `stage.sh smoke` after the install; (3) how the Accounting menus and reports look and export in a browser. Also open from before: nobody has looked at the wellness storefront in a browser.
**Known and accepted for staging:** the kit rewrote core accounting group records on install (finding 3 in `ACCOUNTING_KIT.md`); the demo books are nearly empty, so most reports will show little until accounting demo data is seeded.

---

## 2026-11-18 — accounting kit: post-install checks green (owner-run, output pasted back)

- **Scheduled actions:** `select cron_name from ir_cron where active` returns one row, `Base: Auto-vacuum internal data`. The kit's follow-up,
  recurring-entry and bank auto-reconcile actions are all off, as neutralize intends.
- **`stage.sh smoke` with the kit installed:** `/web/login`, `/`, `/pharma`, `/shop` all 200; DEMO ribbon on `/shop` YES; the five shop products listed;
  login as the owner's admin OK uid 2; 14 of 14 Pharma menus; demo counts unchanged (tax rules 8, tax events 9, recon runs 5, exceptions 6, stock lines 4,
  raw events 8); production mode still refuses DEMO rules; `pharma.mode` by SQL `demo`.

Closed: the install checks in the previous entry marked "not yet verified" items (1) and (2). Still open and owned by the owner: the browser look at the Accounting menus and reports
(and an Excel export), and at the wellness storefront. Suggested next step, not started: seed fictional accounting data (invoices, bills, payments, a bank
statement, an asset, a budget) through the normal flows so the reports have something to show.

---

## 2026-11-18 — slice 1: Courier COD ledger with statement upload (written and committed, NOT yet run on Odoo)

Pakistan cash-on-delivery, built as generic `pharma_` addons that extend the reconciliation hub. Nothing client-, courier-
or partner-specific is in the repository (demo couriers are "Courier A (DEMO)" and "Courier B (DEMO)"). **Never executed
against Odoo yet: first-run failures are possible and expected; the throwaway-database test step is what finds them.**

What was added

| Module | Version | What it does |
| --- | --- | --- |
| `pharma_courier_cod` | 19.0.1.0.0 | Couriers, shipments (declared / collected / remitted ledger, ageing from the delivery date in four buckets, overdue against each courier's cycle), remittances (slips with itemised deductions: freight, COD fee, withholding income tax, withholding sales tax, other; posted then reconciled against the bank through the hub's matcher), statement uploads (header + staging rows loaded with Odoo's own import screen, validated row by row, built into shipments or a draft remittance only by a Finance Controller), exceptions (collection, remittance, overdue, deduction, returned COD, intake) raised once per finding, a daily cron. 67 tests. |
| `pharma_courier_cod_demo` | 19.0.1.0.0 | Idempotent seeder for every scenario above plus two sample CSV files for the live upload. 9 tests. |

Rules held

- Maker-checker and the tax gate are untouched; matching and building are Finance Controller actions, run as `pharma.finance` by the seeder.
- Every uploaded row is archived unchanged in the immutable raw-event log; a thinner later file never blanks a field.
- Reconciled remittances are locked; a posted slip cannot gain lines; deductions above the authorized amount are a finding, never absorbed.
- Nothing posts to accounting. Booking COD settlement into the ledger is a separate, later slice (1b).

`stage.sh` changes: both modules added to `MODULES` / `PHARMA_MODULES` (so `test` and `upgrade` include them); `verify` prints courier COD counts, exceptions by category and the number of active courier crons; `upgrade` now runs `odoo neutralize` again afterwards when the database is neutralized, so the new scheduled action stays off.

Static checks done here: `py_compile` and `pyflakes` clean, XML well-formed, `bash -n stage.sh` clean. No Odoo is available in the cloud checkout, so no test has run.

Next (owner-run on the VPS, in this order, each gated)

```bash
cd /opt/mumtaz-pharma-staging && git fetch origin pharma-erp-v0.1 && git merge --ff-only FETCH_HEAD
bash deploy/pharma-staging/stage.sh test        # throwaway DB: expect 0 failed of 130 (54 + 67 + 9)
# only after that is green, and on a named go:
bash deploy/pharma-staging/stage.sh upgrade     # dumps mumtaz_pharma first, installs the two modules, restarts odoo-pharma only
bash deploy/pharma-staging/stage.sh smoke
```

## 2026-11-18 — slice 1 first run on the VPS: one defect found and fixed (owner-run, output pasted back)

- `stage.sh test` (fresh throwaway DB) and the live `stage.sh upgrade` both failed while loading `pharma_courier_cod_demo` with
  `psycopg2.ProgrammingError: can't adapt type 'method'` during `ir.model._reflect_models`.
- Cause: the seeder defined a helper named `_order`, which replaced Odoo's own `_order` class attribute (default sort order),
  so a bound method reached the `ir_model` INSERT. Fixed by renaming it `_sale_order`. A scan of every pharma model for methods that
  shadow reserved model attributes (`_order`, `_name`, `_table`, `_rec_name`, ...) found no other collision.
- State left on `mumtaz_pharma` by the aborted upgrade (read from `ir_module_module`): `pharma_courier_cod` installed 19.0.1.0.0 (its menus are visible),
  `pharma_courier_cod_demo` uninstalled, everything else unchanged, service not restarted. Pre-upgrade dump kept:
  `backups/mumtaz_pharma_pre_upgrade_20261118_135909.dump`. No rollback was needed.
- Note: `pharma_courier_cod` itself loaded without error, but its 67 tests have still not run.

## 2026-11-18 — slice 1 on staging: 129 of 130 tests green, courier modules INSTALLED in mumtaz_pharma (owner-run, output pasted back)

- Fresh-install test on the throwaway DB: 130 tests ran, 0 failed, 1 error. The error was a defect in my own demo test (it searched
  statements by tracking number only, and the DEMO-A-0001 slip statement matches too: "Expected singleton"); the module code
  was not at fault. Fixed by also filtering on statement type. Per module: pharma_courier_cod 75 tests, pharma_courier_cod_demo 11,
  pharma_demo_data 15, pharma_pk_tax_core 20, pharma_reconciliation_hub 18, pharma_website_demo 9. The `bad query ... pharma_tax_event`
  lines in the log are the pre-existing negative tests that provoke a database constraint on purpose; they are not failures.
- Live `stage.sh upgrade` (owner ran it with the single test error above in hand, dump
  `backups/mumtaz_pharma_pre_upgrade_20261118_140410.dump`): updated six modules, installed `pharma_courier_cod_demo`, 105 modules loaded,
  odoo-pharma restarted, health 200. Smoke green: ribbon present, five products, 20 Pharma menus visible.
- Seeded: 2 couriers, 19 shipments, 3 remittances, 4 statements, 18 open exceptions in total. Courier COD findings by category:
  collection 1, remittance 1, deduction 1, returned COD 1, intake 1, overdue 6 (see DEMO_SCENARIOS C6b).
- **Found: `courier COD crons active = 1`, expected 0.** The re-neutralize step I added to `upgrade` did not fire: Odoo stores
  `database.is_neutralized` as lowercase `true`, my check compared with `True`. Fixed in `stage.sh` (case-insensitive). The scheduled
  action is therefore active on staging until `stage.sh neutralize` is run (gate: restarts odoo-pharma only).
- **Found, not caused by this slice: the accounting hardening is no longer installed.** `pharma_accounting_hardening = uninstalled (-)`,
  the vendor support endpoint is back at the vendor URL and its form is open to *Role / User*; right after the install-accounting step it
  was installed, disabled and Administrator-only. The kit modules themselves are still installed. This was already the case before the
  courier upgrade (visible in the module-state query run after the first failed upgrade). Cause not established from the pasted output.

## 2026-11-18 — courier COD cron switched off (owner-run `stage.sh neutralize`, output pasted back)

- Neutralize re-run on `mumtaz_pharma` (twice; idempotent), odoo-pharma restarted, health 200.
- Result: `database.is_neutralized = true`, active crons = 1 (`Base: Auto-vacuum internal data` only),
  outgoing mail server forced to `invalid:1025`, `courier COD crons active = 0`. The slice-1 data is intact (2 couriers, 19 shipments, 3 remittances, 4 statements).
- Still open: `pharma_accounting_hardening` is not installed (see the entry above); waiting for the owner to say whether that was intended.

## 2026-11-18 — accounting hardening reinstalled (owner-run `stage.sh install-accounting`, output pasted back)

- Dump first: `backups/mumtaz_pharma_pre_accounting_20261118_140810.dump`. Installed `pharma_accounting_hardening` (kit modules were already present),
  neutralize re-run, odoo-pharma restarted, health 200. 106 modules installed.
- Verified: vendor support endpoint = `http://127.0.0.1:9/support-disabled-by-pharma-accounting-hardening`, support form open to
  *Role / Administrator* only, anonymous `POST /xlsx_report` refused (303), courier COD crons active = 0, slice-1 data intact
  (2 couriers, 19 shipments, 3 remittances, 4 statements, 18 open exceptions in total).
- Cause of the earlier uninstall was not established from the pasted output (it predates the courier upgrade). Nothing else changed.
  The separate `pharma-hide-cybrosys` branch (hides the support button in the UI) is not merged here.

## 2026-11-18 — slice 1b: COD settlement accounting (written and committed, NOT yet run on Odoo)

New addon `pharma_courier_cod_accounting` 19.0.1.0.0 (depends `pharma_courier_cod`, `account`; separate so a tenant without Accounting keeps the lean ledger).
One action on a reconciled remittance, **Create journal entry**, builds a **draft** miscellaneous entry: credit the courier clearing account with the gross
remitted, debit the bank/receipts account with what actually arrived, each deduction (freight, COD fee, withholding income tax, withholding sales tax, other)
to its own account, and any bank difference to a difference account (debit if short, credit if over). Accounts and journal are per courier, configured on a new
*Accounting* tab; only accounts a slip uses are required and a missing one is named. Finance Controllers do not need Accounting rights (the draft is created with
elevated rights and records the Finance user as creator); nothing is ever posted by the module. 17 tests. Details: `docs/pharma/COURIER_COD_ACCOUNTING.md`.

`pharma_courier_cod_demo` 19.0.1.1.0: now depends on the accounting addon, creates eight fictional accounts if absent (codes 1999xx / 5999xx), points both demo couriers at them and creates one draft
entry (clean batch `DEMO-SL-A-1001`); the other two reconciled slips are left for the live demonstration. Migration re-seeds on `-u`. 12 tests.
`stage.sh`: new module in the lists; `verify` prints journal entries by state.

Static checks done here only (py_compile, pyflakes, XML well-formed, `bash -n`). **Never executed against Odoo**; first-run failures are possible. Not in this slice:
the collection entry itself, reversing a posted settlement.

Next (owner-run): `git pull --ff-only` then `stage.sh test` (expect 0 failed of 148), and only when green and on a named go `stage.sh upgrade` then `smoke`.

## 2026-11-18 — slice 1b: 148 of 148 tests green on the throwaway DB, first run (owner-run, output pasted back)

- Fresh install of the full module list into `mumtaz_pharma_test` with `--test-tags pharma`: **0 failed, 0 error(s) of 148 tests**, no code change needed.
  Per module: pharma_courier_cod 75, pharma_courier_cod_accounting 19, pharma_courier_cod_demo 12, pharma_demo_data 15, pharma_pk_tax_core 20,
  pharma_reconciliation_hub 18, pharma_website_demo 9. The two `bad query ... pharma_tax_event` log lines are the same intentional negative tests as before.
- Staging was left at the earlier state while the throwaway DB was tested: accounting hardening installed, courier cron off. `mumtaz_pharma` is untouched by this run.
- Next gate (owner's go needed): `stage.sh upgrade` installs `pharma_courier_cod_accounting`, updates `pharma_courier_cod_demo` to 19.0.1.1.0 (its migration seeds the accounts and one draft entry),
  re-runs neutralize, restarts odoo-pharma only.

## 2026-11-18 — slice 1b LIVE on staging: accounting addon installed, one draft entry seeded, smoke green (owner-run, output pasted back)

- `stage.sh upgrade` (dump `backups/mumtaz_pharma_pre_upgrade_20261118_141934.dump`): installed `pharma_courier_cod_accounting`, updated the other seven pharma modules,
  `pharma_courier_cod_demo` 19.0.1.1.0 migration ran (post-migrate), 107 modules loaded, neutralize re-ran automatically this time (the lowercase-flag fix works),
  odoo-pharma restarted, health 200.
- Verified after: `courier COD journal entries: draft=1`, `courier COD crons active = 0`, accounting hardening still installed with the support endpoint at
  `http://127.0.0.1:9/support-disabled-by-pharma-accounting-hardening` and the form limited to *Role / Administrator*, 18 open exceptions and the slice-1 counts unchanged
  (2 couriers, 19 shipments, 3 remittances, 4 statements). Smoke: ribbon present, five products, 20 Pharma menus visible.
- The upgrade was run a second time (command block pasted twice, dump `..._143232.dump`): updated all eight modules, installed nothing, counts identical (draft entry still 1),
  which is the idempotency proof on a live database. The first smoke's XML-RPC login returned "Access Denied" (password prompt, most likely mistyped); the second smoke logged in as uid 2.
- Still owner-side and not yet done by anyone: a browser walkthrough of C1-C14 in DEMO_SCENARIOS.md as `pharma.finance` / admin.

## 2026-11-18 — branch pharma-functionality taken onto pharma-erp-v0.1 (cherry-picked, NOT yet tested or on staging)

Cherry-picked, in order, with no conflicts and no file overlap with the slice-1/1b work (no PR, nothing to main, no merge of the other branch):

| Source | Here | What |
| --- | --- | --- |
| `7886a47` | `bf79bd4` | `pharma_accounting_hardening` 19.0.1.1.0: removes the vendor support button (top-bar icon and user-menu item) from the web client; asset bundle change, so a hard refresh is needed after the upgrade |
| `3fee1ae` | `3ecb8c8` | `pharma_pk_tax_core` 19.0.1.1.0: a tax rule can be linked to a standard Odoo sales tax (opt-in); a sale-order or invoice line for a product resolved by such a rule must carry exactly that tax or it cannot be confirmed / posted. Demo rules are not linked, so existing demo behaviour is unchanged |
| `8838578` | `84beb56` | new `pharma_partner_stock` 19.0.1.0.0 (depends `pharma_reconciliation_hub`, `stock`): derives the Distribution Partner stock roll-forward from done stock move lines instead of typed numbers; undocumented loss moves show as variance |

`stage.sh` changes made here so the gate does what was asked: `pharma_partner_stock` added to `MODULES` and `PHARMA_MODULES` (so `test`, `test-combined`, `install`, `upgrade` include it);
`upgrade` now also updates `pharma_accounting_hardening` when it is installed (it is not in `PHARMA_MODULES` because it needs the third-party kit, so it would previously have been skipped);
`verify` prints the versions of the three changed modules and how many tax rules are linked to an Odoo tax. Simulated against the current staging module set the upgrade list is:
update `pharma_core, pharma_pk_tax_core, pharma_reconciliation_hub, pharma_demo_data, pharma_website_demo, pharma_courier_cod, pharma_courier_cod_accounting, pharma_courier_cod_demo, pharma_accounting_hardening`; install `pharma_partner_stock`.

Static checks only here (py_compile, pyflakes, XML well-formed, `bash -n`, no method shadows a reserved model attribute, no names or secrets in the new module). Next: owner runs `stage.sh test-combined` (must be green) and pastes the output;
then a named go is needed before `stage.sh upgrade` on `mumtaz_pharma`.

## 2026-11-18 — pharma-functionality commits LIVE on staging: test-combined 176/176, upgrade and smoke green (owner-run, output pasted back)

- `stage.sh test-combined` (fresh throwaway DB, every pharma module plus the accounting kit and hardening): **0 failed, 0 error(s) of 176 tests**; DB dropped. `mumtaz_pharma` untouched by it.
- `stage.sh upgrade`, run once after the owner's named go (dump `backups/mumtaz_pharma_pre_upgrade_20261118_145151.dump`). Upgrade line:
  `update: pharma_core, pharma_pk_tax_core, pharma_reconciliation_hub, pharma_demo_data, pharma_website_demo, pharma_courier_cod, pharma_courier_cod_accounting, pharma_courier_cod_demo, pharma_accounting_hardening   install: pharma_partner_stock`.
  108 modules loaded, neutralize re-ran automatically, odoo-pharma restarted, health 200.
- Verified after (`verify`): `pharma_pk_tax_core` 19.0.1.1.0, `pharma_accounting_hardening` 19.0.1.1.0, `pharma_partner_stock` 19.0.1.0.0 installed, 108 modules installed;
  support endpoint still `http://127.0.0.1:9/support-disabled-by-pharma-accounting-hardening` and the form still *Role / Administrator*; courier COD crons active 0; journal entries `draft=1`;
  the earlier data is unchanged (2 couriers, 19 shipments, 3 remittances, 4 statements, 18 open exceptions, 8 tax rules, 9 tax events, 10 recon runs, 4 partner stock lines).
- `smoke`: HTTP 200, `/`, `/pharma`, `/shop` 200, DEMO ribbon present, five products listed, admin login OK (uid 2), 20 of 20 Pharma menus visible, production mode still refuses DEMO rules (rolled back, mode `demo`).
- Not exercised yet on staging: `tax rules linked to an Odoo sales tax = 0`, so the new tax-link gate is covered by the automated tests but has no live data; the partner-stock derivation has not been run against a real stock location.
  The vendor support button removal is a web-client asset: it needs a hard refresh in the browser and a visual check (owner).

## 2026-11-18 — slice 1c: COD collection entry (written and committed, NOT yet run on Odoo)

`pharma_courier_cod_accounting` 19.0.1.1.0 adds **Create collection entry** on a delivered COD shipment (form button, and list Action for several at once, all or nothing):
a draft entry that debits the courier COD clearing account with what the courier **collected** and credits the customer's receivable with the customer on the line, so the accountant
reconciles it to the invoice in Accounting. With the settlement entry (1b) the clearing balance now means what the couriers still hold. Refused, with the reason named: not COD, not delivered
(returned parcels too), nothing collected, no matching sale order, already has an active entry. Finance Controllers need no Accounting rights; nothing is posted by the module.
I deliberately did not use Odoo's payment wizard: it cannot be tested from here and it changes between versions; a plain draft entry keeps the same review-and-post control as 1b.
`pharma_courier_cod_demo` 19.0.1.2.0: draft collection entries for `DEMO-A-0001` to `-0003` (they cancel the clean-batch settlement on the clearing account); migration re-seeds on `-u`.
12 new tests for the collection entry, 1 for the demo; shared account fixtures moved to `tests/common.py`. `stage.sh verify` prints collection entries by state; docs and presenter script (C15, C16) updated.

Static checks only (py_compile, pyflakes, XML well-formed, `bash -n`). **Never executed against Odoo.** Next (owner-run): `git pull --ff-only`, `stage.sh test-combined` (expect 0 failed; 176 + 13 = 189 tests),
and only when green and on a named go `stage.sh upgrade` (updates the accounting and demo modules) then `smoke`.

## 2026-11-18 — slice 1c LIVE on staging: test-combined 189/189, upgrade and smoke green (owner-run, output pasted back)

- `stage.sh test-combined` (fresh throwaway DB, every pharma module plus the accounting kit): **0 failed, 0 error(s) of 189 tests** (176 + 13 new), first run, no code change needed. DB dropped.
- `stage.sh upgrade`, run once after the owner's named go (dump `backups/mumtaz_pharma_pre_upgrade_20261118_150007.dump`): updated ten modules including
  `pharma_courier_cod_accounting` 19.0.1.1.0 and `pharma_courier_cod_demo` 19.0.1.2.0 (post-migrate ran), installed nothing, 108 modules loaded, neutralize re-ran automatically, odoo-pharma restarted, health 200.
- Verified after (`verify`): `courier COD collection entries: draft=3` (the clean batch) and `journal entries: draft=1` (its settlement), crons active 0, accounting hardening 19.0.1.1.0 with the support endpoint still
  `http://127.0.0.1:9/support-disabled-by-pharma-accounting-hardening` and the form *Role / Administrator*, `pharma_pk_tax_core` 19.0.1.1.0, `pharma_partner_stock` 19.0.1.0.0, and every earlier count unchanged
  (2 couriers, 19 shipments, 3 remittances, 4 statements, 18 open exceptions). Smoke: ribbon present, five products, admin login OK, 20 of 20 menus, production mode still refuses DEMO rules.
- Not exercised yet on staging: pressing Create collection entry / Create journal entry in the browser (C13, C16), the list Action for several shipments, reconciling a collection credit against a real customer invoice,
  and the tax-link gate (no rule is linked to an Odoo tax). These need the owner's browser pass.

## 2026-11-18 — slice 1d: reversal of posted collection and settlement entries (cherry-picked `de063d4`, NOT yet tested or on staging)

Cherry-picked from `origin/pharma-reversal` as `a3f31ba` on top of `6b09f6d` (single commit, no conflicts; main untouched, no PR). `pharma_courier_cod_accounting` 19.0.1.2.0:
a Finance Controller asks to reverse a **posted** collection or settlement entry with a required reason; Odoo's own reversal is created as a **draft** (`_reverse_moves(cancel=False)`, reconciliations untouched);
an accountant posts it; once the reversal is posted the record is released so a corrected entry can be created, and the withdrawn entry is kept in *Superseded Entries*. A draft reversal keeps the original standing, so nothing is booked twice meanwhile.
Shared behaviour lives in the abstract `pharma.cod.entry.reversal` mixin; one transient wizard `pharma.courier.entry.reverse` with one access row (Finance, read/write/create/unlink); 14 tests.

Schema note for the upgrade: **three** new tables, not two: the wizard's transient table plus one many2many relation table each for remittances and shipments (`pharma_courier_remittance_prev_move_rel`, `pharma_courier_shipment_prev_move_rel`). The abstract mixin has no table.

Made here: `stage.sh upgrade` takes an optional module argument (`stage.sh upgrade pharma_courier_cod_accounting` updates only that module; unknown names are refused before anything is dumped; no argument keeps the old behaviour);
`verify` prints the accounting module's version and reversal entries by state; docs (COURIER_COD_ACCOUNTING.md, DEMO_SCENARIOS C17). No demo data is seeded for this (it needs posted entries). Static checks only (py_compile, pyflakes, XML, `bash -n`); expected suite: 189 + 14 = 203.
Next (owner-run): `git pull --ff-only`, `stage.sh test-combined` (must be green); then a named go for `stage.sh upgrade pharma_courier_cod_accounting`, `verify`, `smoke`. Neutralize needs no separate step; `upgrade` re-runs it only as a no-op safeguard on a neutralized database.
Caveat to test in the browser: reversing an entry that was already reconciled against a customer invoice leaves that reconciliation for the accountant to resolve.

## 2026-11-18 — structure: one app per area instead of one "Pharma" menu (written and committed, NOT yet tested or on staging)

The single shared "Pharma" menu (four unrelated areas hung under `pharma_core.menu_pharma_root`) is replaced by five apps in the app switcher, each owned by the module that provides it and with its own icon:
**Tax Centre** (`pharma_pk_tax_core`), **Reconciliation** and **Distribution Partner** (`pharma_reconciliation_hub`), **Courier COD** (`pharma_courier_cod`, now with its own Configuration › Couriers),
**Pharma Admin** (`pharma_core`, Source Events, Administrator only). Menu items keep their technical ids and are re-parented; the old shared root and section menus are removed. Visibility is unchanged
(Pharma users see the apps; Commercial Model stays Finance-only; configuration stays Administrator-only). Module technical names are untouched.

Why new root ids rather than reusing the old ones: Odoo does not clear a menu's parent when a data file simply drops it, and a menu cannot be deleted while it still has children, so the roots are new records and the old ones are garbage-collected at the end of the upgrade.
That upgrade-path behaviour is exactly what a fresh-install test cannot show, so `stage.sh rehearse-upgrade [mod,...]` is new: it copies `mumtaz_pharma` into the throwaway database (`pg_dump` read only), runs the same upgrade on the copy, prints the app roots and any leftover shared "Pharma" root, and drops it.
`smoke` now counts the app roots and checks the menu paths per app. Docs: DEMO_SCENARIOS has an "apps" table and updated headings; COURIER_COD_ACCOUNTING paths updated.

Static checks only (XML and SVG well-formed, `bash -n`, no stale menu references). Next (owner-run): `git pull --ff-only`, `stage.sh test-combined`, then `stage.sh rehearse-upgrade` (this must say PASSED), and only then a named go for `stage.sh upgrade` and `smoke`, followed by a hard refresh in the browser.

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
