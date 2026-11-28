# Staff work: production runbook (for Umer or the VPS session)

Everything below runs on the VPS, as root, in one sitting. Nothing here is done from a cloud session.
It follows decisions §20–§27 and the deploy rules in `faizy/CLAUDE.md`: chain with `&&`, back up first,
paste the output back before the next step. **Do not start without Umer's written go-ahead (D10).**

## 0. Preconditions (read, do not skip)

- `main` contains PR #203 (faizy_ai 19.0.1.5.0) and the consolidation PR (§27). CI green on both.
- Real logins for Mashood and Raza exist (they do, per `docs/work/README.md`); write their exact logins here:
  `CARE_LOGIN=________  OPS_LOGIN=________  MANAGER_LOGIN=________` (Umer's own login).
- Outgoing mail (SMTP) is **not** configured. Step 6 (two-factor) therefore waits.
- Customer WhatsApp sending stays off (`faizy.whatsapp_send_mode` unset). Nothing below changes it.

## 1. Backup

```bash
sudo -u postgres pg_dump -Fc faizy_prod > /opt/faizy/backups/faizy_prod-$(date +%F-%H%M).dump && ls -la /opt/faizy/backups | tail -3
```

## 2. Pull and upgrade (installs the standard Project app and the faizy_work bridge)

```bash
sudo systemctl stop faizy-odoo && sudo -u faizy git -C /opt/faizy/src pull && cd /opt/faizy && sudo -u faizy /opt/faizy/venv/bin/python3 /opt/faizy/odoo/odoo-bin -c /opt/faizy/odoo.conf --logfile= -d faizy_prod -u faizy_core,faizy_ai,faizy_pilot,faizy_website,faizy_work --stop-after-init && echo "upgrade exit: $?" && sudo systemctl start faizy-odoo
```

Then confirm, and paste back:

```bash
sudo -u postgres psql -d faizy_prod -c "select name, state, latest_version from ir_module_module where name in ('project','faizy_core','faizy_ai','faizy_pilot','faizy_website','faizy_work','faizy_work_project') order by name;"
```

Expected: all `installed`; `faizy_ai` 19.0.1.5.0, `faizy_work` 19.0.1.1.0, `project` installed, `faizy_work_project` installed (auto).

## 3. Provision the two workspaces (idempotent; re-run is safe)

Edit the plan first if you want different targets: `faizy/odoo/tools/staff_plan_30d.py`, then commit.
`START` is the plan's first day (a Monday). The admin password is asked for by the tool; never put it in a file.

```bash
cd /opt/faizy/src/faizy/odoo/tools && python3 provision_staff.py --url http://127.0.0.1:8069 --db faizy_prod --login admin --password "$ADMIN_PASSWORD" --start START --care CARE_LOGIN --ops OPS_LOGIN --manager MANAGER_LOGIN --align-crm-rights --write-doc /opt/faizy/src/faizy/docs/plans/STAFF_30_DAY_PLAN.md
```

What it does: role holders, home action = My desk, `faizy_ai.route_leads = on`, SOP notes, two sales
teams, two projects with "Evidence before Done", the daily plan, the ten milestones per person, Faizy Work
checklists on the end-of-day and weekly review tasks, and (with `--align-crm-rights`) own-documents CRM for
both. It never creates real logins.

Check, and paste back:

```bash
sudo -u postgres psql -d faizy_prod -c "select key, value from ir_config_parameter where key in ('faizy_ai.care_user_id','faizy_ai.ops_user_id','faizy_ai.escalation_user_id','faizy_ai.route_leads','faizy.checklist_enforce','faizy.checklist_orders','faizy.show_plan_prices','faizy.whatsapp_send_mode') order by key;" -c "select p.name, count(t.id) tasks from project_project p left join project_task t on t.project_id = p.id where p.faizy_role is not null group by p.name;"
```

## 4. Scorecards and recurring checklists (Faizy Work)

In Odoo as Umer: Settings › Technical › Parameters: `faizy.kpi_start` = the plan start date;
`faizy.kpi_conversion_target` stays 0.20 unless decided otherwise. Faizy › Configuration › Checklist
templates: assign Mashood on `daily_start`/`daily_end`/`weekly_review_cx` and Raza on `daily_start`/
`daily_end`/`weekly_review_ops` only if you want the standalone daily checklists **in addition** to the ones
already on the planned tasks (recommended: leave unassigned to avoid two lists).
`faizy.checklist_orders`: set `on` only when Raza should get an order checklist on every new order.

## 5. Each person signs in

Home opens on My desk. They read today's plan, open the first task, tick the checklist or log the note,
mark Done. The morning summary arrives at 09:30 Karachi in the Odoo Inbox. Nothing goes to WhatsApp.

## 6. Two-factor authentication (after SMTP only)

The standard "Enforce two-factor authentication" emails a code at login. Without outgoing mail it locks
everyone out. Order: configure SMTP (FD-06) → test an email → then
`provision_staff.py ... --enforce-totp`, or Settings › General › Permissions › Enforce two-factor.
Until then each person can turn on app-based two-factor themselves: avatar › My profile › Account security.

## 7. Rollback

```bash
sudo systemctl stop faizy-odoo && sudo -u postgres dropdb faizy_prod && sudo -u postgres createdb -O faizy faizy_prod && sudo -u postgres pg_restore -d faizy_prod /opt/faizy/backups/faizy_prod-<stamp>.dump && sudo -u faizy git -C /opt/faizy/src checkout <previous-main-sha> && sudo systemctl start faizy-odoo
```

Rollback restores the database and the code together; do not roll back one without the other.
