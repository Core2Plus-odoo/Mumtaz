# 08. Tracker and forecast fixes: staging runbook

28 Nov 2026. Companion to `07-NEXT-BUILD-LIST.md` (items 1 and 2). Covers both fixes in one pass:
`c2p_project_tracker` 19.0.1.0.2 (milestone-history access) and `c2p_milestone_forecast` 19.0.1.0.1 (no context-key bypass).
Run as root on the VPS. **Live is only read** (one `pg_dump`, the same kind of read as the nightly backup, and three read-only queries).
Everything else happens on a **copy** named `c2p_stage_copy`, and the new code sits in `/opt/stage-fixes/addons`, a folder the live Odoo services do not look at.

## What this proves

| Step | Question it answers |
|---|---|
| 0 | Does any live automation or server action send one of the keys the forecast fix closes? What is installed, and how many history rows exist? |
| 5 | Do both modules upgrade cleanly on a copy of live data, with their own tests (63 and 21)? |
| 6 | After the upgrade: is the new column filled for existing rows, and are the access rows and the rule as designed? |
| 6 | On live's rules: can a Solutions member move a task and have the change logged; is a forged history row refused; do the four context keys stop bypassing the reason rule? (16 checks, all on fictional data, all rolled back) |

**Rehearsed before you got this:** the scenario script ran end to end on a local stock Odoo 19 stand-in with both modules installed: `ALL AS EXPECTED`, 16 of 16 checks, no mail attempts. **It has not run against live data.** If any step prints an error, a failed assertion or a line marked `FAIL` or `DIFFERENT`, stop and paste it: a difference is a finding, not a mistake.

**Safety built in**
- The copy's name does not match the live `^Mumtaz` database filter, so nobody can open it by accident.
- Step 2 switches off in the copy every scheduled job, every mail server and every automation, and blanks credential-looking settings (names printed, never values).
- Every script refuses to run on any database other than `c2p_stage_copy`.
- Every `odoo` command carries `--smtp=127.0.0.1 --smtp-port=9` and `--max-cron-threads=0`, and the script process also disables SMTP, so no mail can leave.
- The scenario's people and projects are fictional ("ZZ ..."), and it ends with a rollback.
- Nothing here touches the 60% intercompany rule, accounting, users or permissions on live.

## Step 0. Read-only checks on live
```bash
sudo -u postgres psql -d Mumtaz_C2P -c "SELECT name, state, latest_version FROM ir_module_module WHERE name IN ('c2p_project_tracker','c2p_milestone_forecast','c2p_work_hub','c2p_meeting_actions','c2p_client_onboarding') ORDER BY 1"
sudo -u postgres psql -d Mumtaz_C2P -c "SELECT count(*) AS history_rows FROM c2p_milestone_history"
sudo -u postgres psql -d Mumtaz_C2P -c "SELECT id, name::text FROM ir_act_server WHERE code ~ '(c2p_skip_change_reason|c2p_forecast_internal|install_mode)' ORDER BY id"
```
The third query lists server actions whose code sends one of the closed keys. **Expected: no rows.** Any row is a finding: that action would start being refused after the upgrade. Paste it before going on.

## Step 1. Get the code (not into live's addons folder)
```bash
REF=claude/gifted-turing-jjdsb2      # use main once the pull request is merged
rm -rf /opt/stage-fixes && mkdir -p /opt/stage-fixes/addons && cd /opt/stage-fixes
git clone -q --depth 1 --filter=blob:none --sparse --branch "$REF" https://github.com/Core2Plus-odoo/Mumtaz.git repo
cd repo && git sparse-checkout set addons/c2p_project_tracker addons/c2p_milestone_forecast && git log -1 --format='%h %s'
cp -r addons/c2p_project_tracker addons/c2p_milestone_forecast /opt/stage-fixes/addons/ && cd /root
grep -h '"version"' /opt/stage-fixes/addons/c2p_project_tracker/__manifest__.py /opt/stage-fixes/addons/c2p_milestone_forecast/__manifest__.py
```
Expected versions: `19.0.1.0.2` and `19.0.1.0.1`.

## Step 2. Make the copy and neutralise it
```bash
df -h /var/lib/postgresql | tail -1
sudo -u postgres psql -Atc "SELECT pg_size_pretty(pg_database_size('Mumtaz_C2P'))"
DUMP=/var/backups/pg/Mumtaz_C2P_for-fixes-staging-$(date +%F-%H%M).dump
sudo -u postgres pg_dump -Fc Mumtaz_C2P > "$DUMP" && ls -lh "$DUMP"
sudo -u postgres psql -c "DROP DATABASE IF EXISTS c2p_stage_copy WITH (FORCE)"
sudo -u postgres psql -c "CREATE DATABASE c2p_stage_copy OWNER postgres"
sudo -u postgres psql -c "REVOKE CONNECT ON DATABASE c2p_stage_copy FROM PUBLIC"
sudo -u postgres psql -c "GRANT CREATE ON DATABASE c2p_stage_copy TO odoo"
sudo -u postgres psql -d c2p_stage_copy -c "GRANT ALL ON SCHEMA public TO odoo"
sudo -u postgres pg_restore --no-owner --no-privileges --role=odoo -d c2p_stage_copy < "$DUMP"
sudo -u postgres psql -c "ALTER DATABASE c2p_stage_copy OWNER TO odoo"
mkdir -p /root/stage-fix-ops
cat > /root/stage-fix-ops/neutralise.sql <<'SQLEOF'
\set ON_ERROR_STOP on
SELECT (current_database() = :'target') AS right_db \gset
\if :right_db
\else
  \echo REFUSING TO RUN: this is not the target database
  \quit
\endif
UPDATE ir_cron SET active = false WHERE active;
UPDATE ir_mail_server SET active = false WHERE active;
DO $$ BEGIN IF to_regclass('fetchmail_server') IS NOT NULL THEN UPDATE fetchmail_server SET active = false WHERE active; END IF; END $$;
UPDATE base_automation SET active = false WHERE active;
\echo == config keys that look like credentials (names only; values are blanked in this copy)
SELECT key FROM ir_config_parameter
WHERE key ~* '(key|token|secret|passw)' AND key NOT IN ('database.secret','database.uuid','database.enterprise_code') ORDER BY 1;
UPDATE ir_config_parameter SET value = ''
WHERE key ~* '(key|token|secret|passw)' AND key NOT IN ('database.secret','database.uuid','database.enterprise_code');
\echo == after neutralising
SELECT (SELECT count(*) FROM ir_cron WHERE active) AS active_scheduled_jobs,
       (SELECT count(*) FROM ir_mail_server WHERE active) AS active_mail_servers,
       (SELECT count(*) FROM base_automation WHERE active) AS active_automations;
SQLEOF
sudo -u postgres psql -d c2p_stage_copy -v target=c2p_stage_copy -f /root/stage-fix-ops/neutralise.sql
```
Expected: the last three numbers are `0, 0, 0`. Check the free space first: the copy needs about as much room as the database. The filestore is not copied; these tests use no attachments.

## Step 3. Write the scenario scripts and the helper
```bash
cat > /root/stage-fix-ops/prelude.py <<'PYEOF'
import os, re, smtplib
from datetime import date, datetime, timedelta
TARGET = os.environ.get('STAGE_DB', 'c2p_stage_copy')
assert env.cr.dbname == TARGET, 'REFUSING TO RUN: database is %r, expected %r' % (env.cr.dbname, TARGET)
# Nothing can leave this process: outgoing mail is recorded, never sent.
import odoo.addons.base.models.ir_mail_server as _ms
SENT = []
def _stub(self, message, *a, **k):
    SENT.append((message['To'], message['Subject']))
    return 'stubbed'
for _n in dir(_ms):
    _o = getattr(_ms, _n)
    if isinstance(_o, type) and hasattr(_o, 'send_email'):
        _o.send_email = _stub
smtplib.SMTP = None
smtplib.SMTP_SSL = None
con = env['res.company'].search([('name', 'ilike', 'Consultants')], limit=1)
sol = env['res.company'].search([('name', 'ilike', 'Solutions')], limit=1)
assert con and sol, 'could not find the Consultants and Solutions companies'
PYEOF
cat > /root/stage-fix-ops/scenario.py <<'PYEOF'
# Fictional engagement in the copy: proves both fixes on live's rules. Everything is rolled back at the end.
from odoo.exceptions import AccessError, UserError
from odoo.addons.c2p_milestone_forecast.models.project_milestone import skip_change_reason

Project, Task, Stage = env['project.project'], env['project.task'], env['project.task.type']
Hist, Milestone, Users = env['c2p.milestone.history'], env['project.milestone'], env['res.users'].with_context(no_reset_password=True)
results = []
def check(label, ok):
    results.append(ok)
    print(('PASS  ' if ok else 'FAIL  ') + label)
def refused(fn, exc=(AccessError, UserError)):
    try:
        with env.cr.savepoint():
            fn()
    except exc:
        return True
    return False

today = date.today()
pf = Project.create({'name': 'ZZ Fictional - Milestones', 'company_id': con.id, 'c2p_layer': 'portfolio', 'allow_milestones': True})
dl = Project.create({'name': 'ZZ Fictional - Delivery', 'company_id': sol.id, 'c2p_layer': 'delivery', 'allow_milestones': True})
pf.c2p_counterpart_id = dl
def stages(project, names):
    return {n: Stage.create({'name': n, 'sequence': i, 'fold': n == 'Done', 'project_ids': [(6, 0, [project.id])]}) for i, n in enumerate(names, 1)}
ps = stages(pf, ['Not Started', 'In Progress', 'Blocked', 'Client Review', 'Done'])
ds = stages(dl, ['Backlog', 'To Do', 'In Progress', 'Waiting on Client', 'Review', 'Done'])
dm = Milestone.create({'name': 'M1 ZZ Fictional', 'project_id': dl.id, 'deadline': today + timedelta(days=30)})
pm = Task.create({'name': 'M1 ZZ Fictional', 'project_id': pf.id, 'stage_id': ps['Not Started'].id, 'delivery_milestone_id': dm.id})

def user(login, company, group_xmlids):
    return Users.create({'name': 'ZZ ' + login, 'login': 'zz-' + login, 'company_id': company.id, 'company_ids': [(6, 0, [company.id])],
                         'group_ids': [(4, env.ref(g).id) for g in group_xmlids]})
member = user('member', sol, ['c2p_project_tracker.group_c2p_delivery_member'])
manager = user('portfolio-manager', con, ['c2p_project_tracker.group_c2p_portfolio_manager'])
other = env['res.company'].create({'name': 'ZZ Unrelated Company'})
outsider = user('outsider', other, ['c2p_project_tracker.group_c2p_delivery_member'])
pmgr = user('project-manager', sol, ['project.group_project_manager'])

print('== Fix 1: milestone history (c2p_project_tracker)')
task = Task.create({'name': 'ZZ task', 'project_id': dl.id, 'stage_id': ds['To Do'].id, 'milestone_id': dm.id,
                    'user_ids': [(6, 0, [member.id])], 'date_deadline': datetime.combine(today + timedelta(days=5), datetime.min.time())})
before = Hist.sudo().search_count([])
try:
    task.with_user(member).write({'stage_id': ds['In Progress'].id})
    moved = True
except Exception as e:
    moved = False
    print('      the save failed with: %s' % e)
rows = Hist.sudo().search([('milestone_id', '=', pm.id)])
check('a Solutions member can move a task, and the change is logged', moved and Hist.sudo().search_count([]) > before and bool(rows))
check('the row records the paired delivery company', bool(rows) and rows[0].paired_company_id == sol)
check('the member can read the history of their own paired engagement', bool(rows) and rows[0] in Hist.with_user(member).search([]))
check('an unrelated company sees no history', not Hist.with_user(outsider).search([('milestone_id', '=', pm.id)]))
vals = {'milestone_id': pm.id, 'source': 'manual', 'new_stage_id': ps['In Progress'].id}
check('a forged create is refused for a member', refused(lambda: Hist.with_user(member).create(vals)))
check('a forged create is refused for a Portfolio Manager', refused(lambda: Hist.with_user(manager).create(vals)))
check('a member cannot edit a row', bool(rows) and refused(lambda: rows[:1].with_user(member).write({'note': 'tampered'})))
check('a member cannot delete a row', bool(rows) and refused(lambda: rows[:1].with_user(member).unlink()))

print('== Fix 2: forecast reason rule (c2p_milestone_forecast)')
dmu = dm.with_user(pmgr)
for key in ('c2p_skip_change_reason', 'install_mode', 'module', 'c2p_forecast_internal'):
    check('context key %s does not skip the reason' % key,
          refused(lambda k=key: dmu.with_context(**{k: True}).write({'deadline': today + timedelta(days=40)}), UserError) and dm.deadline == today + timedelta(days=30))
check('a context key cannot set the health colour', refused(lambda: dmu.with_context(c2p_forecast_internal=True).write({'c2p_health': 'red'}), UserError))
check('a change with a reason still works', not refused(lambda: dmu.write({'deadline': today + timedelta(days=35), 'c2p_change_reason': 'ZZ staging check'})))
with skip_change_reason():
    dmu.write({'deadline': today + timedelta(days=36)})
check('trusted code can skip the reason inside its block', dm.deadline == today + timedelta(days=36))
check('and the skip ends with the block', refused(lambda: dmu.write({'deadline': today + timedelta(days=37)}), UserError))

env.cr.rollback()
print('== rolled back; mail attempts recorded: %d' % len(SENT))
print('ALL AS EXPECTED' if all(results) else 'DIFFERENT: %d of %d checks failed' % (results.count(False), len(results)))
PYEOF
AP=$(grep -E '^addons_path' /etc/odoo4.conf | head -1 | cut -d= -f2 | tr -d ' '); echo "$AP"
# The new code goes FIRST, so it shadows the installed copy of the same two modules, in the copy only.
ODOO_ARGS="-c /etc/odoo4.conf -d c2p_stage_copy --addons-path=/opt/stage-fixes/addons,$AP --no-http --max-cron-threads=0 --smtp=127.0.0.1 --smtp-port=9"
run() { cat /root/stage-fix-ops/prelude.py "$1" | sudo -u odoo env "${@:2}" /usr/bin/odoo shell $ODOO_ARGS --log-level=warn --logfile=/tmp/stage-fix-shell.log; }
```
The addons path printed must not be empty.

## Step 4. Before the upgrade, on the copy
```bash
sudo -u postgres psql -d c2p_stage_copy -c "SELECT name, latest_version FROM ir_module_module WHERE name IN ('c2p_project_tracker','c2p_milestone_forecast') ORDER BY 1"
sudo -u postgres psql -d c2p_stage_copy -c "SELECT count(*) AS history_rows FROM c2p_milestone_history"
echo "print('MODULE PATH:', odoo.modules.get_module_path('c2p_project_tracker'))" > /root/stage-fix-ops/path.py
run /root/stage-fix-ops/path.py
```
Expected: the path printed starts with `/opt/stage-fixes/addons`. If it shows live's folder, stop: the new code is not being used.

## Step 5. Upgrade the copy and run both modules' tests
```bash
sudo -u odoo /usr/bin/odoo -c /etc/odoo4.conf -d c2p_stage_copy --addons-path="/opt/stage-fixes/addons,$AP" -u c2p_project_tracker,c2p_milestone_forecast --test-enable --test-tags /c2p_project_tracker,/c2p_milestone_forecast --stop-after-init --no-http --http-port=8799 --max-cron-threads=0 --smtp=127.0.0.1 --smtp-port=9 --log-level=test --logfile=/tmp/stage-fix-upgrade.log
grep -aE "post-tests in|failed,|ERROR|CRITICAL" /tmp/stage-fix-upgrade.log | cut -c1-200 | tail -8
```
Expected: `0 failed, 0 error(s) of 84 tests` (63 tracker plus 21 forecast) and no ERROR lines. The upgrade also upgrades the modules that depend on the tracker (work hub, meeting actions, client onboarding); that is expected, and their code on the copy is live's own.

## Step 6. After the upgrade: the data, then the scenario
```bash
sudo -u postgres psql -d c2p_stage_copy -c "SELECT name, latest_version FROM ir_module_module WHERE name IN ('c2p_project_tracker','c2p_milestone_forecast') ORDER BY 1"
sudo -u postgres psql -d c2p_stage_copy -c "SELECT count(*) AS history_rows, count(paired_company_id) AS with_paired_company FROM c2p_milestone_history"
sudo -u postgres psql -d c2p_stage_copy -c "SELECT name, perm_read::int AS r, perm_write::int AS w, perm_create::int AS c, perm_unlink::int AS d FROM ir_model_access WHERE name ILIKE 'c2p.milestone.history%' ORDER BY 1"
sudo -u postgres psql -d c2p_stage_copy -c "SELECT domain_force FROM ir_rule WHERE name::text ILIKE '%Milestone history%'"
run /root/stage-fix-ops/scenario.py
```
Expected:
- versions `19.0.1.0.2` and `19.0.1.0.1`;
- `history_rows` equal to step 0; `with_paired_company` equal to the number of rows whose engagement is paired (rows of an unpaired engagement stay empty, which is correct);
- four access rows; the new `project user (create only)` row shows `0, 0, 1, 0`;
- the rule text contains `paired_company_id`;
- the scenario prints `PASS` on all 16 checks and ends `ALL AS EXPECTED`.

## Step 7. Clean up
```bash
sudo -u postgres psql -c "DROP DATABASE c2p_stage_copy WITH (FORCE)"
rm -rf /root/stage-fix-ops /opt/stage-fixes /tmp/stage-fix-shell.log /tmp/stage-fix-upgrade.log
ls -lh /var/backups/pg/*for-fixes-staging*
```
The dump still holds live data in the root-only backup folder; remove it with `rm` when you are done, if you do not want to keep it.

## What to paste back
The output of steps 0 (all three), 2 (the last lines), 4, 5 and 6.

## What this does not cover
- The browser screens, and a real Solutions member's session on live.
- Anything on live itself: no module, parameter or automation on live is changed by this runbook. The live upgrade is a separate step that needs your approval after these results, with its own rollback plan (a fresh backup first).
