# Mumtaz Jewel staging — `jewel.mumtaz.digital`

**Status: proposal. Nothing in this directory has been run on any server, and
`jewel.mumtaz.digital` does not exist yet.** These are reviewable files that
implement section 2 of `docs/mumtaz-jewel/CLAUDE_CODE_HANDOFF.md`.

Everything here is deliberately separate from production: its own compose
project, network, Postgres volume and `.env`. It never shares a database,
volume or env file with the live C2P CRM or any production tenant, per
`docs/mumtaz-jewel/CLAUDE.md`.

## What needs your approval before anything runs

From the handoff's gate list (section 3), none of which this directory does
for you:

1. **The DNS record** — an A record for `jewel` pointing at the VPS
   (`187.77.128.199`). Made by whoever holds DNS for `mumtaz.digital`.
2. **The nginx block and certificate** — `nginx/jewel.mumtaz.digital.conf`
   installed on the VPS, after `certbot` issues the certificate. This is
   production infrastructure.
3. **The first start of the stack** on the VPS.
4. **Opening the host beyond the allow-list**, or putting any real client data
   on it.

## Files

| File | What it is |
| --- | --- |
| `docker-compose.yml` | The stack: `postgres:16-alpine` + `odoo:19`, own network and volumes, ports bound to `127.0.0.1` only |
| `odoo.conf.tmpl` | Odoo config template. `deploy.sh` renders it to `odoo.rendered.conf` (gitignored) with values from `.env` |
| `.env.example` | Every knob, documented. Copy to `.env` and set the two passwords. **Never commit `.env`** |
| `deploy.sh` | Pull the staging branch, render the config, restart, health-check. Refuses `main` and refuses any branch but `JEWEL_BRANCH` |
| `backup.sh` | Nightly dump, retention, and the restore drill |
| `nginx/jewel.mumtaz.digital.conf` | The server block: landing page public at `/`, demo system restricted on Odoo's own prefixes |
| `../../website/jewel/index.html` | The landing page itself (static, self-contained) |

## Order of operations, once approved

```bash
git clone <repo> /opt/mumtaz-jewel-staging   # NOT /opt/mumtaz, which tracks main
cd /opt/mumtaz-jewel-staging
git checkout claude/mumtaz-jewellery-phase2
```

```bash
cd deploy/jewel-staging && cp .env.example .env
```

Set `POSTGRES_PASSWORD` and `ADMIN_PASSWORD` in `.env` (`openssl rand -base64 32`),
then first run — install the addons, then seed the synthetic demo data:

```bash
./deploy.sh --install --seed
```

```bash
curl -fsS http://127.0.0.1:8072/web/health
```

Then, separately and only with approval, the DNS record, the certificate and
the nginx block. Later deploys are just `./deploy.sh`.

### The landing page

`jewel.mumtaz.digital/` serves a static landing page, publicly; the Odoo demo
sits behind the allow-list and password on Odoo's own URL prefixes
(`/odoo`, `/web`, `/websocket` and the rest). Odoo cannot be mounted under a
sub-path, which is why the split is by prefix rather than by folder. Keep any
new landing-page asset under `/site/` so it can never collide with an Odoo
route.

```bash
mkdir -p /opt/mumtaz/jewel-landing
cp -r website/jewel/. /opt/mumtaz/jewel-landing/
```

**Before it goes live:** the page has three `REPLACE-WITH-YOUR-EMAIL`
placeholders for the demo-request address, and carries `noindex` plus a
`Disallow: /` robots.txt on purpose, because this is a demo host. Both are
flagged in an HTML comment at the top of the file.

Updating the page later is a copy, not a deploy: it is static and needs no
restart.

## Guard rails built in

`deploy.sh` refuses to run from `main`, refuses any branch but the one named in
`.env`, refuses to run from `/opt/mumtaz` (the production checkout), and never
calls `c2p-delivery-system/deploy/update.sh`. It touches only the
`mumtaz-jewel-staging` compose project. `backup.sh` restores into a throwaway
database, so a drill cannot overwrite the demo database.

The addons are mounted **read-only**, so a demo container cannot edit the
working tree. Both Odoo ports bind to `127.0.0.1`, so nothing is reachable
except through nginx. The nginx block requires either a listed IP **or** the
demo password, and sends `X-Robots-Tag: noindex` plus a `Disallow: /`
`robots.txt`, because a demo database must never be indexed.

## Things worth deciding

- **Postgres version.** This pins `postgres:16-alpine`, because 16.15 is what
  the Slice 0 suite was actually run against. The production CRM compose pins
  `postgres:15-alpine`. If staging should match production, re-run
  `scripts/jewel_ci.sh` against 15 first and change the pin only if it passes.
- **Ports.** 8072/8073, since 8069 is the Odoo default and 8070 is the
  existing staging stack. Check they are free on the VPS before the first run.
- **`list_db = True`** is on, so the demo database can be dropped and
  re-seeded from the UI mid-demo. The allow-list and the master password are
  what protect it. Turn it off if you would rather reset only from the shell.
- **Monitoring.** The handoff asks for an uptime alert on the staging URL.
  Both services have Docker health checks, but no external alerting is wired
  up: that depends on which monitor the VPS already uses.
- **The landing page's claims.** Every capability is marked built, in
  development, or planned, and the page says plainly that the product is in
  pilot development and that no integration is connected. Please keep it that
  way when editing: it is the difference between a demo and a promise.
- **Nothing untested.** None of these scripts has been executed anywhere. The
  compose file and shell syntax were checked statically, and the landing page
  was rendered headless at desktop, mobile and dark-mode widths; the first
  real run will be the first time any of it executes on a server.
