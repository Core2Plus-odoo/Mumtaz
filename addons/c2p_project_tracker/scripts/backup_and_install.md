# Installing `c2p_project_tracker` — backup first, test DB second

`Mumtaz_C2P` is live: 41k CRM leads, 4 client engagements, 41 users. Install on
a copy, verify, then install on production. Never the other way round.

All commands run as `root` on the VPS.

## 1. Discover the service's real configuration

Do not assume paths — read them from the unit file.

```bash
systemctl cat odoo4.service
```

Note the `ExecStart` line. It contains `-c <config>`; read that file for the
addons path and the database settings:

```bash
CONF=$(systemctl cat odoo4.service | grep -oP '(?<=-c )\S+' | head -1)
echo "config: $CONF"
grep -E '^(addons_path|db_host|db_user|db_port|xmlrpc_port|http_port)' "$CONF"
```

As inspected on 2026-10-05 the addons path was:
`/usr/lib/python3/dist-packages/odoo/addons`, `/opt/custom_addons`,
`/opt/custom_addons/Mumtaz/addons`.

**`/opt/mumtaz/addons` was NOT on that path**, so the module cannot load until
it is reachable. There are two ways, and they are not equally safe.

### Check for shadowing first — this decides the answer

`/opt/custom_addons/Mumtaz/addons` is *another checkout of this same
repository*. Adding `/opt/mumtaz/addons` to the path would therefore put a
second copy of `mumtaz_lead_scraper`, `mumtaz_lead_nurture`, `c2p_appointment`
and `c2p_proposal` on it. Odoo resolves a module name to the **first** matching
directory in `addons_path` order, so whichever copy wins is decided by config
order rather than intent — and the code running the BD engine could change on a
restart that nobody associates with a deploy.

```bash
for d in /opt/mumtaz/addons /opt/custom_addons /opt/custom_addons/Mumtaz/addons; do
  echo "== $d"; ls "$d" 2>/dev/null
done
```

Any name appearing under more than one path is a shadowing risk.

### Preferred: symlink the one module

Adds exactly one module, shadows nothing, and keeps git as the source of truth —
`git pull` in `/opt/mumtaz` updates the deployed code.

```bash
ln -sfn /opt/mumtaz/addons/c2p_project_tracker \
        /opt/custom_addons/Mumtaz/addons/c2p_project_tracker
ls -l /opt/custom_addons/Mumtaz/addons/c2p_project_tracker
```

First confirm what that checkout tracks, since it is a clone of this repo and
will fight a different branch:

```bash
git -C /opt/custom_addons/Mumtaz status -sb
```

### Alternative: extend `addons_path`

Only after the shadowing check comes back clean. Back the config up, and put the
new entry **last** so existing modules keep resolving as they do today:

```bash
cp -a "$CONF" "$CONF.bak-$(date +%F-%H%M)"
grep -n addons_path "$CONF"
# append ,/opt/mumtaz/addons to that line, then restart against the TEST
# database on the spare port — never production first.
```

Whichever is chosen, record it. The same ambiguity is why `c2p_appointment` and
`c2p_proposal` are on disk in production but in no repository, and why
`c2p_master_agent` is installed with no source on the path at all.

## 2. Back up the database

```bash
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p /var/backups/odoo
sudo -u postgres pg_dump -Fc Mumtaz_C2P \
  > "/var/backups/odoo/Mumtaz_C2P-$TS.dump"
ls -lh "/var/backups/odoo/Mumtaz_C2P-$TS.dump"
```

Also back up the filestore, which `pg_dump` does not cover:

```bash
tar czf "/var/backups/odoo/filestore-Mumtaz_C2P-$TS.tgz" \
  -C ~odoo/.local/share/Odoo/filestore Mumtaz_C2P 2>/dev/null \
  || echo "check the filestore path in $CONF (data_dir)"
```

## 3. Duplicate to a test database

`Mumtaz_C2P_staging` already exists on this server and is owned by `postgres`.
Decide whether to reuse it or make a fresh copy; these steps make a fresh one.

```bash
sudo -u postgres dropdb --if-exists Mumtaz_C2P_test
sudo -u postgres createdb -O odoo -T template0 Mumtaz_C2P_test
sudo -u postgres pg_restore -d Mumtaz_C2P_test \
  "/var/backups/odoo/Mumtaz_C2P-$TS.dump"
```

Copy the filestore so attachments resolve:

```bash
DATA=$(grep -oP '(?<=^data_dir = ).*' "$CONF" || echo ~odoo/.local/share/Odoo)
cp -a "$DATA/filestore/Mumtaz_C2P" "$DATA/filestore/Mumtaz_C2P_test"
chown -R odoo: "$DATA/filestore/Mumtaz_C2P_test"
```

**Neutralise the copy before touching it** — a restored database still has
production's crons and outgoing mail server, and 40 crons on this instance:

```bash
sudo -u postgres psql -d Mumtaz_C2P_test -c "UPDATE ir_cron SET active = false;"
sudo -u postgres psql -d Mumtaz_C2P_test -c "UPDATE ir_mail_server SET active = false;"
```

Without that, the copy will email real clients and run the BD engine again.

## 4. Install on the test database

Stop nothing — run a separate process against the test DB on another port.

```bash
sudo -u odoo /usr/bin/odoo -c "$CONF" \
  -d Mumtaz_C2P_test \
  --http-port 8171 \
  -i c2p_project_tracker \
  --stop-after-init \
  --log-level=warn
```

The install must finish with no `WARNING` or `ERROR` lines. Expect log lines
from the hook reporting how many engagements paired and how many milestones
linked — read them, because they are how a drifted id shows up.

## 5. Run the tests

```bash
sudo -u odoo /usr/bin/odoo -c "$CONF" \
  -d Mumtaz_C2P_test \
  --http-port 8171 \
  -u c2p_project_tracker \
  --test-enable --test-tags /c2p_project_tracker \
  --stop-after-init \
  --log-level=test
```

## 6. Verify by hand on the test database

Start it on the spare port and log in:

```bash
sudo -u odoo /usr/bin/odoo -c "$CONF" -d Mumtaz_C2P_test --http-port 8171
```

Check:

1. All four engagements appear with a RAG status and readable reasons.
2. Moving a Solutions task to **Waiting on Client** turns the matching
   Consultants milestone **Blocked**, and posts a chatter note. **Confirm no
   email was queued**: `SELECT count(*) FROM mail_mail;` should not grow.
3. Log in as a C2P Solutions user and confirm **no AED figure is visible
   anywhere**.
4. Every milestone will read Amber on "open milestones have no deadline" —
   expected, because all 24 delivery milestones currently have none.

## 7. Only then, production

```bash
sudo -u postgres pg_dump -Fc Mumtaz_C2P > "/var/backups/odoo/Mumtaz_C2P-pre-install.dump"
sudo -u odoo /usr/bin/odoo -c "$CONF" -d Mumtaz_C2P \
  -i c2p_project_tracker --stop-after-init --log-level=warn
systemctl restart odoo4.service
systemctl status odoo4.service --no-pager
```

### Rolling back

```bash
systemctl stop odoo4.service
sudo -u postgres dropdb Mumtaz_C2P
sudo -u postgres createdb -O odoo -T template0 Mumtaz_C2P
sudo -u postgres pg_restore -d Mumtaz_C2P "/var/backups/odoo/Mumtaz_C2P-pre-install.dump"
systemctl start odoo4.service
```

Uninstalling the module instead would drop its columns and every
`c2p.milestone.history` row with them. Restoring the dump is the safer undo.
