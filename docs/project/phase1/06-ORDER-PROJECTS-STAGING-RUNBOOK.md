# 06. Order projects: staging runbook (module `c2p_order_projects`)

26 Nov 2026. Companion to `04-ORDER-TO-PROJECT-PATHS.md` and `05-ORDER-PROJECTS-CUTOVER.md`.
Run as root on the VPS. **Live is only read, by one `pg_dump`** (the same kind of read as the nightly backup). Everything else happens on a **copy**
named `c2p_stage_copy`, and the module code is kept in `/opt/stage-t01/addons`, a folder the live Odoo services do not look at.

## What this proves, and in what order

| Phase | State of the copy | What it shows |
|---|---|---|
| `baseline` | Module not installed, the live automations as they are | What one fictional deal does today on real configuration: expected 2 projects and 4 to-dos for a won lead, 1 project and 2 to-dos for a directly confirmed order, and 1 project and 2 to-dos for a won lead with no quotation |
| install | Module installed, switched off, with its own 22 tests run against the live-like data and rules | The module loads and passes on live's structure |
| `off` | Module installed, switched off | Nothing changes (same numbers as `baseline`) |
| `on` | Module switched on, **old automations still active** | One pair per order, no duplicate from action 919; this is the state during cutover step 4 |
| `edited` | The proposed text edits from `05-ORDER-PROJECTS-CUTOVER.md` applied | One kickoff and one portal to-do per deal, one weekly task per deal, and a won lead with no quotation creates nothing (decision D7) |
| race | Two processes confirm the same order at the same moment | Exactly one pair; the loser fails cleanly |

**Rehearsed before you got this:** all scripts ran end to end on a local stock Odoo 19 stand-in that holds the pasted code of actions 738, 748, 751, 766, 747, 919, 920, rules 2, 12, 19, 11, 30 and the custom `x_` fields, with fictional ids. Results there: baseline, off, on, edited and race all as expected, and the module's own tests `0 failed, 0 error(s) of 22`. **They have not run against live data.** If any step prints an error, a failed assertion or a line marked `DIFFERENT`, stop and paste it: a difference is a finding, not a mistake.

**Safety built in**
- The copy's name does not match the live `^Mumtaz` database filter, so nobody can open it by accident.
- Step 3 switches off in the copy every scheduled job, every outgoing and incoming mail server, and every automation except the seven under test (ids 2, 3, 10, 11, 12, 19, 30), and blanks credential-looking settings (names printed, never values).
- Every script refuses to run on any database other than `c2p_stage_copy`.
- Every `odoo` command carries `--smtp=127.0.0.1 --smtp-port=9` and `--max-cron-threads=0`, and each script process also disables SMTP, so no mail can leave.
- Customers are fictional ("ZZ Fictional Client Ltd"). The deal scripts roll back; only steps 6, 8, 9 and the race commit, in the copy only.
- Nothing here touches the 60% intercompany rule, accounting, users or permissions on live.

## Step 1. Get the module code (not into live's addons folder)
```bash
REF=claude/gifted-turing-jjdsb2      # use main once PR 209 is merged
rm -rf /opt/stage-t01 && mkdir -p /opt/stage-t01/addons && cd /opt/stage-t01
git clone -q --depth 1 --filter=blob:none --sparse --branch "$REF" https://github.com/Core2Plus-odoo/Mumtaz.git repo
cd repo && git sparse-checkout set addons/c2p_order_projects && git log -1 --format='%h %s'
cp -r addons/c2p_order_projects /opt/stage-t01/addons/ && cd /root && ls /opt/stage-t01/addons/c2p_order_projects
```
The commit shown should be `d675b28` or later on that branch (it is what CI tested).

## Step 2. Make the copy
```bash
df -h /var/lib/postgresql | tail -1
sudo -u postgres psql -Atc "SELECT pg_size_pretty(pg_database_size('Mumtaz_C2P'))"
DUMP=/var/backups/pg/Mumtaz_C2P_for-order-projects-staging-$(date +%F-%H%M).dump
sudo -u postgres pg_dump -Fc Mumtaz_C2P > "$DUMP" && ls -lh "$DUMP"
sudo -u postgres psql -c "DROP DATABASE IF EXISTS c2p_stage_copy WITH (FORCE)"
sudo -u postgres psql -c "CREATE DATABASE c2p_stage_copy OWNER postgres"
sudo -u postgres psql -c "REVOKE CONNECT ON DATABASE c2p_stage_copy FROM PUBLIC"
sudo -u postgres psql -c "GRANT CREATE ON DATABASE c2p_stage_copy TO odoo"
sudo -u postgres psql -d c2p_stage_copy -c "GRANT ALL ON SCHEMA public TO odoo"
sudo -u postgres pg_restore --no-owner --no-privileges --role=odoo -d c2p_stage_copy < "$DUMP"
sudo -u postgres psql -c "ALTER DATABASE c2p_stage_copy OWNER TO odoo"
```
Check the free space first: the copy needs about as much room as the database. The filestore is not copied; these tests use no attachments.

## Step 3. Write the scripts, then neutralise the copy
```bash
mkdir -p /root/stage-ops
cat > /root/stage-ops/neutralise.sql <<'SQLEOF'
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
UPDATE base_automation SET active = false WHERE active AND id NOT IN (2,3,10,11,12,19,30);
\echo == config keys that look like credentials (names only; values are blanked in this copy)
SELECT key FROM ir_config_parameter
WHERE key ~* '(key|token|secret|passw)' AND key NOT IN ('database.secret','database.uuid','database.enterprise_code') ORDER BY 1;
UPDATE ir_config_parameter SET value = ''
WHERE key ~* '(key|token|secret|passw)' AND key NOT IN ('database.secret','database.uuid','database.enterprise_code');
\echo == after neutralising
SELECT (SELECT count(*) FROM ir_cron WHERE active) AS active_scheduled_jobs,
       (SELECT count(*) FROM ir_mail_server WHERE active) AS active_mail_servers,
       (SELECT count(*) FROM base_automation WHERE active) AS active_automations,
       (SELECT string_agg(id::text, ',' ORDER BY id) FROM base_automation WHERE active) AS automation_ids;
SQLEOF
cat > /root/stage-ops/prelude.py <<'PYEOF'
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
cat > /root/stage-ops/configure.py <<'PYEOF'
# Switch the module on in THIS COPY, using the company and template that action 919 uses today. Commits.
act = env['ir.actions.server'].search([('name', 'ilike', 'Create Solutions delivery project')])
assert len(act) == 1, 'expected exactly one action 919, found %d' % len(act)
tmpl = re.search(r'SOL_TMPL\s*=\s*(\d+)', act.code)
comp = re.search(r'with_company\((\d+)\)', act.code)
assert tmpl and comp, 'could not read the template and company from action 919'
t = env['project.project'].with_context(active_test=False).browse(int(tmpl.group(1)))
c = env['res.company'].browse(int(comp.group(1)))
assert t.exists() and t.is_template and c.exists(), 'the template or company named by action 919 does not exist'
icp = env['ir.config_parameter']
icp.set_param('c2p.order_projects.delivery_company_id', str(c.id))
icp.set_param('c2p.order_projects.default_delivery_template_id', str(t.id))
icp.set_param('c2p.order_projects.pair_in_tracker', '1')
icp.set_param('c2p.order_projects.enabled', '1')
env.cr.commit()
print('SWITCHED ON in', env.cr.dbname, '| delivery company:', c.name, '| default delivery template:', t.name,
      '| template stages:', t.type_ids.mapped('name'))
PYEOF
cat > /root/stage-ops/apply_edits.py <<'PYEOF'
# Apply the PROPOSED text changes of docs/project/phase1/05-ORDER-PROJECTS-CUTOVER.md to THIS COPY. Commits.
# Each edit asserts the exact old text, so a difference from the pasted live code aborts with nothing committed.
A = env['ir.actions.server']
def one(fragment):
    r = A.search([('name', 'ilike', fragment)])
    assert len(r) == 1, 'expected exactly one action named like %r, found %d' % (fragment, len(r))
    return r
def edit(rec, old, new):
    assert old in rec.code, 'action %r: the text to change is not there, nothing applied' % rec.name
    rec.code = rec.code.replace(old, new, 1)
a738, a748, a751 = one('Send Project Kickoff Email'), one('Grant portal access and notify client'), one('Weekly Status Update Task Creation')
a766, a919, a747 = one('Won opportunity -> delivery project'), one('Create Solutions delivery project'), one('Clone project template')
assert 'c2p_project_role' not in a738.code, 'the proposed edits are already applied in this database'
edit(a738, "for record in records:\n", "for record in records:\n    if record.c2p_project_role == 'delivery':\n        continue\n")
edit(a748, "for project in records:\n", "for project in records:\n    if project.c2p_project_role == 'delivery':\n        continue\n")
edit(a751, "('partner_id','!=',False)])", "('partner_id','!=',False), ('c2p_project_role','!=','delivery')])")
line = [l for l in a766.code.split('\n') if ".browse(" in l and ".run()" in l]
assert len(line) == 1, 'action 766: expected exactly one line that runs another action'
edit(a766, line[0] + '\n', '')
# decision D7 (26 Nov 2026): retire the branch that copies the billing template for a Won lead with no quotation
cut = a766.code.find("    marker = '[OPP:%s]' % lead.id")
assert cut > 0 and 'Won without a quotation' in a766.code[cut:], 'action 766: the no-quotation branch is not where the pasted text had it, nothing applied'
a766.code = a766.code[:cut].rstrip() + '\n'
a919.code = ("if env['ir.config_parameter'].sudo().get_param('c2p.order_projects.enabled') in ('1', 'true', 'True'):\n"
             "    raise UserError('Retired: projects are created when the order is confirmed (module c2p_order_projects).')\n") + a919.code
for rule in env['base.automation'].search([('action_server_ids', 'in', a747.ids)]):
    rule.active = False
for cron in env['ir.cron'].search([('ir_actions_server_id.name', 'ilike', 'Duplicate Cleanup')]):
    cron.active = False
env.cr.commit()
print('PROPOSED EDITS APPLIED in', env.cr.dbname, ': actions', [a.id for a in (a738, a748, a751, a766, a919)],
      '| rule for action 747 off | duplicate cleanup job off')
PYEOF
cat > /root/stage-ops/scenarios.py <<'PYEOF'
# Fictional deals against the copy. Every deal is rolled back. usage: PHASE=baseline|off|on|edited
from odoo.exceptions import UserError
PHASE = os.environ.get('PHASE'); assert PHASE in ('baseline', 'off', 'on', 'edited'), 'set PHASE'
FRAG = os.environ.get('PROD', 'Odoo Implementation|Milestone').split('|')
P = env['project.project'].with_context(active_test=False)
KEYED = 'c2p_project_role' in P._fields
prods = env['product.product'].search([('name', 'ilike', f) for f in FRAG])
assert len(prods) == 1, 'expected exactly one product for %s, found %d: %s' % (FRAG, len(prods), prods.mapped('name'))
prod = prods
WON = env['crm.stage'].browse(4)
if not (WON.exists() and WON.is_won):
    WON = env['crm.stage'].search([('is_won', '=', True)], limit=1)
bad = []
def say(label, ok, detail):
    print('  %-46s %s  %s' % (label, 'OK       ' if ok else 'DIFFERENT', detail))
    if not ok:
        bad.append(label)
def todos(projects):
    return env['mail.activity'].search_count([('res_model', '=', 'project.project'), ('res_id', 'in', projects.ids)])
def keyed(order):
    return P.search([('c2p_source_order_id', '=', order.id)]) if KEYED else P.browse()
def new_partner():
    return env['res.partner'].create({'name': 'ZZ Fictional Client Ltd', 'is_company': True, 'email': 'client@example.invalid'})
def make_order(partner, product=prod, user=None):
    Order = env['sale.order'].with_company(con)
    if user:
        Order = Order.with_user(user).with_context(allowed_company_ids=[con.id])
    return Order.create({'partner_id': partner.id, 'company_id': con.id,
                         'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 1})]})
def describe(projects):
    return [('%s|%s|tpl=%s|layer=%s|tasks=%d' % ('Cons' if p.company_id == con else 'Sol', getattr(p, 'c2p_project_role', None) or '-',
             p.is_template, p.c2p_layer or '-', len(p.task_ids))) for p in projects]
def run_deal(kind):
    before = set(P.search([]).ids)
    partner = new_partner()
    if kind == 'crm':
        lead = env['crm.lead'].create({'name': 'ZZ Fictional deal', 'type': 'opportunity', 'partner_id': partner.id})
        order = make_order(partner); order.opportunity_id = lead.id
        lead.write({'stage_id': WON.id})
    else:
        order = make_order(partner); order.action_confirm()
    env.flush_all()
    return order, P.search([('id', 'not in', list(before))])
EXPECT = {  # projects, keyed, to-dos for the owner
    ('baseline', 'crm'): (2, 0, 4), ('baseline', 'direct'): (1, 0, 2),
    ('off', 'crm'): (2, 0, 4), ('off', 'direct'): (1, 0, 2),
    ('on', 'crm'): (2, 2, 4), ('on', 'direct'): (2, 2, 4),
    ('edited', 'crm'): (2, 2, 2), ('edited', 'direct'): (2, 2, 2)}
print('PHASE', PHASE, '| database', env.cr.dbname, '| module fields present:', KEYED, '| product:', prod.name)
for kind in ('crm', 'direct'):
    sp = env.cr.savepoint()
    order, new = run_deal(kind)
    got = (len(new), len(keyed(order)), todos(new))
    exp = EXPECT[(PHASE, kind)]
    print(' [%s] order %s state=%s' % (kind, order.name, order.state))
    for line in describe(new):
        print('        ', line)
    say('%s deal: projects / keyed / to-dos' % kind, got == exp, 'got %s expected %s' % (got, exp))
    sp.rollback(); env.invalidate_all()
NOQUOTE = {'baseline': (1, 2), 'off': (1, 2), 'on': (1, 2), 'edited': (0, 0)}
sp = env.cr.savepoint(); before = set(P.search([]).ids)
lead = env['crm.lead'].create({'name': 'ZZ Won with no quotation', 'type': 'opportunity', 'partner_id': new_partner().id})
lead.write({'stage_id': WON.id}); env.flush_all()
made = P.search([('id', 'not in', list(before))])
print(' [no quotation] projects:', describe(made))
say('won lead with no quotation: projects / to-dos', (len(made), todos(made)) == NOQUOTE[PHASE], 'got %s expected %s' % ((len(made), todos(made)), NOQUOTE[PHASE]))
sp.rollback(); env.invalidate_all()
if PHASE in ('on', 'edited'):
    sp = env.cr.savepoint(); order, new = run_deal('direct')
    oversight = new.filtered(lambda p: p.c2p_project_role == 'oversight'); delivery = new.filtered(lambda p: p.c2p_project_role == 'delivery')
    say('pair: one oversight, one delivery', len(oversight) == 1 and len(delivery) == 1, '%d / %d' % (len(oversight), len(delivery)))
    say('companies: Consultants and Solutions', oversight.company_id == con and delivery.company_id == sol, '%s / %s' % (oversight.company_id.name, delivery.company_id.name))
    say('customer on both', oversight.partner_id == delivery.partner_id and bool(delivery.partner_id), delivery.partner_id.name)
    say('old links filled (x_ fields)', ('x_delivery_project_id' not in P._fields) or (oversight.x_delivery_project_id == delivery and delivery.x_billing_project_id == oversight),
        'billing<->delivery links')
    paired = bool(oversight.c2p_counterpart_id)
    print('   tracker pairing: paired=%s | delivery template stages: %s (paired only if there is a Backlog stage)' % (paired, delivery.type_ids.mapped('name')))
    notes = [m.body for m in order.message_ids if 'not paired' in (m.body or '')]
    say('pairing outcome matches the Backlog rule', paired == ('backlog' in [s.lower().strip() for s in delivery.type_ids.mapped('name')]), 'note on order: %s' % bool(notes))
    # repeats
    base = keyed(order)
    try:
        order.action_confirm(); refused = False
    except UserError:
        refused = True
    say('confirming again is refused', refused, '')
    order._action_cancel(); order.action_draft(); order.action_confirm(); env.flush_all()
    order._c2p_ensure_project_pair(); order._c2p_ensure_project_pair()
    say('cancel, reset, confirm, repeat: nothing new', keyed(order) == base, '%d keyed projects' % len(keyed(order)))
    # archived
    delivery.active = False; order._c2p_ensure_project_pair()
    say('archived delivery project blocks a new one', keyed(order) == base, '%d keyed projects' % len(keyed(order)))
    oversight.active = False; order._c2p_ensure_project_pair()
    say('archived oversight project blocks a new one', keyed(order) == base, '%d keyed projects' % len(keyed(order)))
    sp.rollback(); env.invalidate_all()
    # template carrying a key
    sp = env.cr.savepoint(); partner = new_partner(); order = make_order(partner)
    tpl = P.create({'name': 'ZZ template carrying a key', 'is_template': True, 'c2p_source_order_id': order.id, 'c2p_project_role': 'delivery'})
    order.action_confirm(); env.flush_all()
    real = keyed(order).filtered(lambda p: not p.is_template and p.c2p_project_role == 'delivery')
    say('a template with the key is ignored', len(real) == 1 and real != tpl, '%d real delivery project' % len(real))
    sp.rollback(); env.invalidate_all()
    # product without a project
    sp = env.cr.savepoint()
    plain = env['product.product'].create({'name': 'ZZ plain service', 'type': 'service', 'service_tracking': 'no', 'list_price': 1})
    order = make_order(new_partner(), plain); order.action_confirm(); env.flush_all()
    say('order without a project product: nothing keyed', len(keyed(order)) == 0, '')
    sp.rollback(); env.invalidate_all()
    # Consultants-only salesperson
    sp = env.cr.savepoint()
    user = env['res.users'].with_context(no_reset_password=True).create({'name': 'ZZ salesperson', 'login': 'zz_salesperson_stage',
        'company_id': con.id, 'company_ids': [(6, 0, [con.id])], 'group_ids': [(6, 0, [env.ref('sales_team.group_sale_salesman').id])]})
    order = make_order(new_partner(), user=user); order.with_user(user).with_context(allowed_company_ids=[con.id]).action_confirm(); env.flush_all()
    seen = env['project.project'].with_user(user).with_context(allowed_company_ids=[con.id]).search_count(
        [('c2p_source_order_id', '=', order.id), ('company_id', '=', sol.id)])
    say('Consultants-only salesperson can confirm', len(keyed(order)) == 2, '%d keyed; sees %d Solutions project' % (len(keyed(order)), seen))
    sp.rollback(); env.invalidate_all()
    # billing milestone to-do (rule 30) and the weekly job
    sp = env.cr.savepoint(); order, new = run_deal('direct')
    delivery = new.filtered(lambda p: p.c2p_project_role == 'delivery')
    for ms in delivery.milestone_ids:
        a0 = env['mail.activity'].search_count([('summary', 'like', 'Invoice milestone')]); ms.is_reached = True; env.flush_all()
        print('   reach %-40s -> invoice to-dos +%d' % (ms.name + (' (billing-linked)' if getattr(ms, 'x_billing_milestone_id', False) else ''),
              env['mail.activity'].search_count([('summary', 'like', 'Invoice milestone')]) - a0))
    wk = env['ir.actions.server'].search([('name', 'ilike', 'Weekly Status Update Task Creation')], limit=1)
    if wk:
        t0 = set(env['project.task'].search([('name', '=', 'Weekly Status Update')]).ids); wk.run(); env.flush_all()
        made = env['project.task'].search([('name', '=', 'Weekly Status Update'), ('id', 'not in', list(t0))])
        mine = made.filtered(lambda t: t.project_id in new)
        want = (1, 0) if PHASE == 'edited' else None
        got = (len(mine.filtered(lambda t: t.project_id.c2p_project_role == 'oversight')), len(mine.filtered(lambda t: t.project_id.c2p_project_role == 'delivery')))
        print('   weekly status job created %d task(s) in total across all active projects; on this pair (oversight, delivery) = %s' % (len(made), got))
        if want:
            say('weekly task: oversight only', got == want, 'got %s expected %s' % (got, want))
    sp.rollback(); env.invalidate_all()
# what the duplicate cleanup would delete (counted, never run)
groups = {}
for p in env['project.project'].search([('partner_id', '!=', False)], order='id asc'):
    groups.setdefault((p.name, p.partner_id.id, p.company_id.id, bool(p.is_template)), []).append(p)
print('  duplicate cleanup would remove', sum(len(v) - 1 for v in groups.values() if len(v) > 1), 'project(s) right now (counted only, nothing deleted)')
env.cr.rollback()
print('PHASE', PHASE, 'finished:', 'ALL AS EXPECTED' if not bad else 'DIFFERENCES: %s' % bad)
PYEOF
cat > /root/stage-ops/race_setup.py <<'PYEOF'
# Create one fictional draft order and keep it, for the two-process confirmation test. Commits (in the copy only).
frag = os.environ.get('PROD', 'Odoo Implementation|Milestone').split('|')
prods = env['product.product'].search([('name', 'ilike', f) for f in frag]); assert len(prods) == 1
partner = env['res.partner'].create({'name': 'ZZ Race Client Ltd', 'is_company': True, 'email': 'client@example.invalid'})
order = env['sale.order'].with_company(con).create({'partner_id': partner.id, 'company_id': con.id,
    'order_line': [(0, 0, {'product_id': prods.id, 'product_uom_qty': 1})]})
env.cr.commit()
print('ORDER_ID=%d' % order.id)
PYEOF
cat > /root/stage-ops/race_confirm.py <<'PYEOF'
# Confirm the same order; waits for START (epoch seconds) so two processes confirm at the same moment.
import time
oid = int(os.environ['ORDER_ID']); start = float(os.environ['START'])
order = env['sale.order'].browse(oid); order.state
time.sleep(max(0.0, start - time.time()))
try:
    order.action_confirm(); env.cr.commit(); print('process', os.environ.get('WHO'), ': confirmed')
except Exception as ex:
    env.cr.rollback(); print('process', os.environ.get('WHO'), ': refused cleanly (%s)' % type(ex).__name__)
PYEOF
cat > /root/stage-ops/race_check.py <<'PYEOF'
oid = int(os.environ['ORDER_ID'])
Pj = env['project.project'].with_context(active_test=False)
kept = Pj.search([('c2p_source_order_id', '=', oid)])
order = env['sale.order'].browse(oid)
lines_projects = order.order_line.sudo().mapped('project_id')
print('order state:', order.state, '| keyed projects:', [(p.c2p_project_role, p.company_id.name) for p in kept],
      '| projects on the order lines:', len(lines_projects))
print('RACE RESULT:', 'OK, exactly one pair' if len(kept) == 2 and len(lines_projects) == 1 else 'DIFFERENT, look at the numbers above')
env.cr.rollback()
PYEOF
sudo -u postgres psql -d c2p_stage_copy -v target=c2p_stage_copy < /root/stage-ops/neutralise.sql
```
Expect `active_scheduled_jobs 0`, `active_mail_servers 0`, and `automation_ids` containing only ids from 2, 3, 10, 11, 12, 19, 30. Paste the list of credential-looking setting **names** too.

## Step 4. Helpers
```bash
AP=$(grep -E '^addons_path' /etc/odoo4.conf | head -1 | cut -d= -f2 | tr -d ' '); echo "$AP"
ODOO_ARGS="-c /etc/odoo4.conf -d c2p_stage_copy --addons-path=$AP,/opt/stage-t01/addons --no-http --max-cron-threads=0 --smtp=127.0.0.1 --smtp-port=9"
run() { cat /root/stage-ops/prelude.py "$1" | sudo -u odoo env "${@:2}" /usr/bin/odoo shell $ODOO_ARGS --log-level=warn --logfile=/tmp/stage-shell.log; }
```
The addons path printed must not be empty. The module folder is added only on the command line, so the live services never see it.

## Step 5. Phase `baseline`: what live does today
```bash
run /root/stage-ops/scenarios.py PHASE=baseline PROD='Odoo Implementation|Milestone'
```
Expected: `crm deal ... got (2, 0, 4)`, `direct deal ... got (1, 0, 2)` and `won lead with no quotation ... got (1, 2)`, finishing `ALL AS EXPECTED`. The three numbers are projects created, projects keyed to the order (none yet), and to-dos for the owner. If it differs, that is what live really does; paste it whole.

## Step 6. Install the module (switched off) and run its own tests
```bash
sudo -u odoo /usr/bin/odoo -c /etc/odoo4.conf -d c2p_stage_copy --addons-path="$AP,/opt/stage-t01/addons" -i c2p_order_projects --test-enable --test-tags /c2p_order_projects --stop-after-init --no-http --http-port=8799 --max-cron-threads=0 --smtp=127.0.0.1 --smtp-port=9 --log-level=test --logfile=/tmp/stage-install.log
grep -aE "post-tests in|failed,|ERROR|CRITICAL" /tmp/stage-install.log | cut -c1-200 | tail -8
```
Expected: `0 failed, 0 error(s) of 22 tests` and no ERROR lines. The tests create their own fictional companies and roll back; they run here against live's structure with the live automations loaded.

## Step 7. Phase `off`: installing changed nothing
```bash
run /root/stage-ops/scenarios.py PHASE=off PROD='Odoo Implementation|Milestone'
```
Expected: the same numbers as step 5, and `module fields present: True`.

## Step 8. Switch it on, old automations still active: phase `on`
```bash
run /root/stage-ops/configure.py
run /root/stage-ops/scenarios.py PHASE=on PROD='Odoo Implementation|Milestone'
```
`configure.py` reads the delivery company and template from action 919 itself, so the copy uses what live uses today, and prints them. Expected: both deals `got (2, 2, 4)`, then a column of `OK` lines. This is the moment that matters for the cutover order: the old action 919 is still on, and the module must not create a second delivery project (it fills the old link fields, so 919 skips). The tracker pairing line prints whether the pair was paired; with a delivery template that has no Backlog stage it is expected to be unpaired, with a note on the order.

## Step 9. Apply the proposed edits to the copy: phase `edited`
```bash
run /root/stage-ops/apply_edits.py
run /root/stage-ops/scenarios.py PHASE=edited PROD='Odoo Implementation|Milestone'
```
`apply_edits.py` asserts the exact old text of each action; if the live text differs from what was pasted, it stops and applies nothing. Expected: both deals `got (2, 2, 2)`, `won lead with no quotation ... got (0, 0)`, and `weekly task: oversight only ... OK`. It also prints how many projects the duplicate-cleanup logic would remove right now (counted, never run), which is worth reading before that job is ever switched back on.

## Step 10. Two processes confirm the same order at once
```bash
OID=$(run /root/stage-ops/race_setup.py PROD='Odoo Implementation|Milestone' | grep -o 'ORDER_ID=[0-9]*' | cut -d= -f2); echo "order $OID"
START=$(python3 -c 'import time; print(time.time()+90)')
( run /root/stage-ops/race_confirm.py ORDER_ID=$OID START=$START WHO=A > /tmp/race_A.out 2>&1 & run /root/stage-ops/race_confirm.py ORDER_ID=$OID START=$START WHO=B > /tmp/race_B.out 2>&1 & wait )
grep -h process /tmp/race_A.out /tmp/race_B.out
run /root/stage-ops/race_check.py ORDER_ID=$OID
```
Expected: one process `confirmed`, the other `refused cleanly (SerializationFailure)` or similar, and `RACE RESULT: OK, exactly one pair`. Both processes load first and then wait for the same second; if loading takes longer than 90 seconds the test is not simultaneous and says nothing: raise the 90.

## Step 11. Clean up
```bash
sudo -u postgres psql -c "DROP DATABASE c2p_stage_copy WITH (FORCE)"
rm -rf /root/stage-ops /opt/stage-t01 /tmp/stage-shell.log /tmp/stage-install.log /tmp/race_A.out /tmp/race_B.out
ls -lh /var/backups/pg/*for-order-projects-staging*
```
The dump still holds live data in the root-only backup folder; remove it with `rm` when you are done, if you do not want to keep it.

## What to paste back
The output of steps 3 (the three expected lines and the setting names), 5, 6, 7, 8, 9 and 10.

## What this does not cover
- The browser screens; the T01 template and product (not built yet); a template with a Backlog stage on live data.
- Real traffic: the first real order after cutover is step 6 of the cutover plan.
- Anything on live itself: no automation, parameter or module on live is changed by this runbook.
