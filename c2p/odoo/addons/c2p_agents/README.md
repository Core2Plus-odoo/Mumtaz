# C2P Agents

Four nightly agents for `Mumtaz_C2P`, as a versioned module instead of Python in
`ir.actions.server.code`.

| Agent | Model | Method | What it does |
|---|---|---|---|
| Lead scoring | `crm.lead` | `_cron_score_leads` | Sets `priority` from source, country, business email, expected revenue, phone and named contact |
| Stale opportunities | `crm.lead` | `_cron_flag_stale_opportunities` | To-Do on high-priority opportunities quiet for 21+ days |
| Proposal follow-up | `crm.lead` | `_cron_followup_proposals` | Call on leads 7+ days in a proposal stage |
| Invoice chaser | `account.move` | `_cron_chase_overdue_invoices` | Call on the owner of an overdue posted customer invoice |

## Why it exists

All four previously ran as Python stored in database fields, and all four were
found silently empty — running every night, executing nothing, reporting
success. Code in a database field cannot be reviewed, diffed, tested or rolled
back, and a cron that does nothing looks exactly like a cron that works.

## Safety model

The module **installs inert**. `c2p_agents.dry_run` defaults to `True`: the
crons are active and run on schedule, they select records and report what they
would have done, and they write nothing. Setting the parameter to `False` arms
them.

Every run — dry or live — writes a `c2p.agent.run` row recording the agent, the
timestamp, how many records were scanned, how many were acted on, and any error.
**CRM → Configuration → C2P Agent Runs**, with an *Acted on Nothing* filter. This
is the check the previous setup did not have.

Each method takes `limit` (default from a system parameter, conservative) and
`dry_run` (an explicit argument overrides the parameter).

```python
# Read-only, safe on production, returns a summary dict:
env["crm.lead"]._cron_flag_stale_opportunities(limit=10, dry_run=True)
```

## Configuration

Thresholds and limits are `ir.config_parameter` entries under `c2p_agents.*` —
see the table in `docs/migration-from-server-actions.md`.

Nothing resolves a database ID. Activity types come from `mail.mail_activity_data_todo`
and `mail.mail_activity_data_call` by XML ID, countries from `res.country.code`,
sources by name. Proposal stages are identified by a **Proposal Stage** checkbox
added to `crm.stage` — seeded at install from the existing stage names, editable
thereafter under CRM → Configuration → Stages. Selecting on a flag rather than
matching stage names at runtime means renaming a stage cannot silently switch the
follow-up agent off.

## Idempotency

Before creating an activity each agent checks for an **open** activity carrying
that agent's `summary` marker on the same record, in one query for the whole
batch. Re-running creates no duplicates.

The trade-off, tested deliberately in
`tests/test_dry_run_and_idempotency.py::test_completing_the_activity_lets_a_still_stale_record_be_flagged_again`:
the check keys on open activities, so once a rep marks the activity done and the
record is *still* stale, the next run raises a fresh one. For a chaser that is
usually wanted. If it should instead go quiet for a period, that is a cooldown
window and a small change to `_c2p_already_flagged`.

## Migration

`docs/migration-from-server-actions.md` — how to move the existing crons over
without losing their schedules, including the Odoo 19 `_inherits` detail that
means there is no separate server action to disable.

## Tests

```bash
odoo-bin -d <test-db> -i c2p_agents --test-enable --test-tags /c2p_agents --stop-after-init
```

Selection logic per agent, including boundary cases (exactly 21 days vs. 20,
draft vs. posted, won and archived records), dry-run behaviour, and idempotency.

## Odoo 19 notes

- `ir.cron` `_inherits` from `ir.actions.server` — the cron and its "server
  action" are one record.
- `res.users.group_ids`, not `groups_id` (used in the tests).
- No `base.automation` is used, so `action_server_ids` does not arise here.
- The server-action sandbox forbade `import` and pre-injected `datetime`. Module
  code has no such restriction — `crm_lead.py` imports `timedelta` normally.

## Known placeholder

The scoring weights in `models/crm_lead.py` (`SOURCE_SCORES`, `COUNTRY_SCORES`,
`REVENUE_BANDS`, `PRIORITY_BANDS` and the flat constants) are a reasonable
GCC-weighted default, **not** a port of the original rules — the original `code`
fields were empty, so there was nothing to read them from. They are plain
module-level tables specifically so that reconciling them against the intended
logic is a diff of a table rather than a rewrite of a method. The tests assert
the arithmetic and the band boundaries, so changing a weight shows up as a
failing test with the expected number in it.
