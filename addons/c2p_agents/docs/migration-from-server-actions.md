# Migrating off the database-resident server actions

Moving the four nightly agents from `ir.actions.server.code` into this module,
**without losing the schedules the existing crons already carry**.

Nothing here deletes anything. Every step is reversible, and the old records are
archived rather than removed so the original configuration stays inspectable.

---

## The v19 detail that decides the whole procedure

`ir.cron` does not *reference* a server action — it **is** one:

```python
class IrCron(models.Model):
    _name = "ir.cron"
    _inherits = {"ir.actions.server": "ir_actions_server_id"}
```

The `code`, `state` and `model_id` fields you edit on a Scheduled Action are
delegated fields living on the `ir.actions.server` row behind it. So:

- There is **no separate server action to disable.** Archiving the cron archives
  the action, because they are one record seen through two models.
- Deleting the `ir.actions.server` row would delete the cron with it, taking the
  schedule (`nextcall`, `interval_number`, `interval_type`, `user_id`) with it.
  That is the thing this procedure exists to avoid.

Confirm which shape you actually have before starting — step 1 tells you.

---

## Step 1 — Snapshot what is there (read-only)

Run this against `Mumtaz_C2P` and **keep the output**. It is the only record of
the original schedules once step 4 archives them.

```sql
SELECT  c.id                AS cron_id,
        a.id                AS action_id,
        a.name->>'en_US'    AS name,
        c.active,
        c.interval_number,
        c.interval_type,
        c.nextcall,
        c.lastcall,
        c.priority,
        c.user_id,
        a.state             AS action_state,
        a.model_id,
        length(coalesce(a.code, '')) AS code_length,
        a.code
FROM ir_cron c
JOIN ir_act_server a ON a.id = c.ir_actions_server_id
ORDER BY c.id;
```

**Already run, on 2026-08-10.** The four agents are crons **44, 45, 46 and 47**,
and — contrary to the original report — none was empty:

| id | name | interval | code | last run |
|---|---|---|---|---|
| 44 | C2P Agent: Lead Scoring (Daily) | 1 day | 1033 chars | 2026-08-10 09:00 |
| 45 | C2P Agent: Stale Lead Detection (Daily) | 1 day | 1150 chars | 2026-08-10 09:00 |
| 46 | C2P Agent: Proposal Follow-up (Daily) | 1 day | 1504 chars | 2026-08-10 09:00 |
| 47 | C2P Agent: Invoice Chaser (Weekly) | **7 days** | 955 chars | 2026-08-10 09:00 |

All four fire at **09:00**. Note the invoice chaser is weekly, not daily — the
module's cron matches.

Re-run the query before migrating anyway: `code_length` of `0` or `NULL` beside a
recent `lastcall` is still the signature of the failure originally reported, and
these numbers are a snapshot.

Three more agents live in database code fields and are **not** covered by this
module — worth the same treatment later:

| id | name | interval | code |
|---|---|---|---|
| 38 | Project — Weekly Status Update Task Creation | 1 week | 1011 chars |
| 39 | Project — Overdue Task Reminder | 1 day | 964 chars |
| 40 | Project — Duplicate Cleanup Safety Net | 10 min | 353 chars |

If any of the four crons has `action_state` other than `code` — say it calls a
*separate* server action via `env.ref('...').run()` — note that action's XML ID
or database ID too; step 4 has a variant for it.

---

## Step 2 — Install the module in dry-run mode

```bash
sudo systemctl stop odoo          # or however the service is managed
sudo -u odoo /opt/odoo/odoo-bin \
     -c /etc/odoo/odoo.conf \
     -d Mumtaz_C2P \
     --addons-path=/opt/custom_addons,/opt/odoo/addons \
     -i c2p_agents --stop-after-init
sudo systemctl start odoo
```

The module installs with `c2p_agents.dry_run = True`. Its four crons are active
immediately, so from that night onward **Settings → Technical → C2P Agent Runs**
fills with real selection counts against real data while nothing is written.

Both sets of crons are running at this point. That is fine and deliberate: the
old four do nothing (empty `code`), and the new four are in dry run.

Let it run for **at least two nights** before step 3. What you are looking for:

| What you see | What it means |
|---|---|
| `scanned` in the tens, `acted` a sensible fraction | Ready to proceed |
| `scanned` in the thousands | A domain is too broad — tune before arming |
| `scanned = 0` every night for an agent | Its domain matches nothing. Read the row's `note` — the proposal agent says outright when no stage name matched — then check the priority values before assuming it is correct |
| No row at all for an agent | It crashed. Odoo will have flagged the cron as failed; the traceback is in `odoo.log` |

The **Acted on Nothing** filter on that list is the check that the old setup
lacked entirely.

---

## Step 3 — Transfer the schedules

Move the timing off the old crons onto the new ones, so the agents keep firing
in the same window the business is used to.

```bash
sudo -u odoo /opt/odoo/odoo-bin shell -c /etc/odoo/odoo.conf -d Mumtaz_C2P
```

```python
# Map each OLD cron to its replacement. Fill in the old IDs from step 1.
# IDs confirmed on Mumtaz_C2P, 2026-08-10. Re-check them before running.
PAIRS = [
    (44, "c2p_agents.cron_lead_scoring"),
    (45, "c2p_agents.cron_stale_opportunities"),
    (46, "c2p_agents.cron_proposal_followup"),
    (47, "c2p_agents.cron_invoice_chaser"),
]

CARRIED = ["interval_number", "interval_type", "nextcall", "priority", "user_id"]

for old_id, new_xmlid in PAIRS:
    old = env["ir.cron"].browse(old_id)
    new = env.ref(new_xmlid)
    values = {}
    for field in CARRIED:
        value = old[field]
        # Many2one fields come back as recordsets; write() wants an id.
        values[field] = value.id if hasattr(value, "id") else value
    new.write(values)
    print("%-40s <- %s (next: %s)" % (new.name, old.name, new.nextcall))

env.cr.commit()
```

The new crons' XML records are `noupdate="1"`, so a later `-u c2p_agents` will
not overwrite what you just wrote.

---

## Step 4 — Disable the old crons

Archiving, not deleting. `active = False` stops the schedule and leaves the row —
including its now-empty `code` — available for reference.

```python
from odoo import fields  # the shell namespace does not provide it

old = env["ir.cron"].browse([44, 45, 46, 47])
old.write({"active": False})

# Rename so nobody re-enables one by accident in six months.
for cron in old:
    if not cron.name.startswith("[RETIRED]"):
        cron.name = "[RETIRED %s] %s" % (fields.Date.today(), cron.name)

env.cr.commit()
```

Because of the `_inherits` relationship, archiving the cron archives the server
action behind it. There is nothing further to switch off.

**Variant — a genuinely separate server action.** If step 1 showed a cron
calling a standalone `ir.actions.server`, archive that action too, *after* the
cron, and again do not delete it:

```python
env["ir.actions.server"].browse(SEPARATE_ACTION_ID).write({"active": False})
```

---

## Step 5 — Arm the agents

Only once the dry-run numbers from step 2 look right.

**Settings → Technical → System Parameters**, find `c2p_agents.dry_run`, set the
value to `False`.

The next night's rows in C2P Agent Runs will show `Dry Run` unticked and real
activities appearing on leads and invoices. Check the first live run the
following morning.

### The other settings

There are none in the database. `c2p_agents.dry_run` is the only system
parameter; every threshold and limit is a constant in `models/`:

| Constant | File | Default |
|---|---|---|
| `LEAD_SCORING_LIMIT` | `models/crm_lead.py` | `200` |
| `STALE_DAYS` / `STALE_LIMIT` | `models/crm_lead.py` | `21` / `50` |
| `PROPOSAL_DAYS` / `PROPOSAL_LIMIT` | `models/crm_lead.py` | `7` / `50` |
| `INVOICE_CHASER_LIMIT` | `models/account_move.py` | `50` |

Changing one is an edit, a commit and a module upgrade (`-u c2p_agents`) —
which is the point: the value that decides what four nightly agents do to live
client data should be reviewable, not a row somebody edited in Settings a year
ago for reasons nobody recorded.

The limits are deliberately low. Raise them once a live run looks right —
preferably one agent at a time.

---

## Rolling back

**Back to dry run** — set `c2p_agents.dry_run` to `True`. Immediate, no restart.
This is the first move if a live run does something unexpected.

**Back to the old crons** — un-archive them and archive the new four:

```python
env["ir.cron"].browse([44, 45, 46, 47]).write({"active": True})
for xmlid in ["c2p_agents.cron_lead_scoring", "c2p_agents.cron_stale_opportunities",
              "c2p_agents.cron_proposal_followup", "c2p_agents.cron_invoice_chaser"]:
    env.ref(xmlid).active = False
env.cr.commit()
```

Rolling back genuinely restores the previous behaviour here: those four records
carry working code and ran this morning. That was not true of the situation
originally described, but it is true of the database as it stands.

**Removing the module** — `Apps → C2P Agents → Uninstall` drops the four new
crons and the run log. It does **not** remove
activities the agents already created; those are ordinary `mail.activity`
records and stay with their leads and invoices. To clear them:

```python
env["mail.activity"].search([
    ("summary", "in", [
        "C2P Agent: stale opportunity",
        "C2P Agent: proposal follow-up",
        "C2P Agent: overdue invoice",
    ]),
]).unlink()
```

---

## What this buys you

- The logic is in git: diffable, reviewable, revertable, with tests.
- `import` works normally. The server-action sandbox forbade `import` and
  pre-injected `datetime`; module code has no such restriction, which is why
  `crm_lead.py` imports `timedelta` at the top like ordinary Python.
- An agent that silently does nothing now leaves a visible trail of zeroes
  rather than a success it did not earn.
- A dry-run mode, so the next change to these rules can be watched against live
  data before it writes to it.
