# C2P Agents

Seven nightly agents for `Mumtaz_C2P`, as a versioned module instead of Python
in `ir.actions.server.code`. The first four are the port; the rest were added
after.

| Agent | Model | Method | What it does |
|---|---|---|---|
| Lead scoring | `crm.lead` | `_cron_score_leads` | Sets `priority` from source, country, business email, expected revenue, phone and named contact |
| Stale opportunities | `crm.lead` | `_cron_flag_stale_opportunities` | To-Do on high-priority opportunities quiet for 21+ days |
| Proposal follow-up | `crm.lead` | `_cron_followup_proposals` | Call on leads 7+ days in a proposal stage |
| Invoice chaser | `account.move` | `_cron_chase_overdue_invoices` | Call on the owner of an overdue posted customer invoice |
| Email validation | `crm.lead` | `_cron_validate_emails` | Checks addresses before outreach; routes to WhatsApp when email is unusable |
| Owner assignment | `crm.lead` | `_cron_assign_owners` | Every open lead gets a salesperson, balanced by current open-lead load |
| Guaranteed next step | `crm.lead` | `_cron_ensure_next_step` | Every owned lead with nothing scheduled gets a To-Do |

## Why it exists

The first four previously ran as Python stored in database fields, and all four
were found silently empty — running every night, executing nothing, reporting
success. Code in a database field cannot be reviewed, diffed, tested or rolled
back, and a cron that does nothing looks exactly like a cron that works.

## Safety model

The module **installs inert**. `c2p_agents.dry_run` defaults to `True`: the
crons are active and run on schedule, they select records and report what they
would have done, and they write nothing. Setting the parameter to `False` arms
them.

Every run writes a `c2p.agent.run` row recording the agent, the timestamp, how
many records were scanned and how many were acted on. **Settings → Technical →
C2P Agent Runs**, admin-only, with an *Acted on Nothing* filter. This is the
check the previous setup did not have.

A run that *crashes* needs no help from the log: Odoo marks the cron as failed
and records the traceback. What the log catches is the quiet failure — the run
that completes cleanly and touches nothing, which is what went unnoticed before.

Each method takes `limit` (a conservative module constant) and `dry_run` (an
explicit argument overrides the system parameter).

```python
# Read-only, safe on production, returns a summary dict:
env["crm.lead"]._cron_flag_stale_opportunities(limit=10, dry_run=True)
```

## Configuration

**One knob: `c2p_agents.dry_run`.** Thresholds (`STALE_DAYS = 21`,
`PROPOSAL_DAYS = 7`) and per-run limits are module constants in `models/`.

That is deliberate. A value stored in `ir.config_parameter` is the same class of
thing as Python stored in `ir.actions.server` — it governs behaviour and lives
somewhere it cannot be diffed, reviewed or reverted. Changing `STALE_DAYS` should
be a commit. `dry_run` is the exception because flipping it is an operational
act, not a change of rules.

Nothing resolves a database ID. Activity types come from
`mail.mail_activity_data_todo` and `mail.mail_activity_data_call` by XML ID,
countries from `res.country.code`, sources by name. Proposal stages are matched
by name at run time against `PROPOSAL_STAGE_HINTS` (`propos`, `quot`, `offer`) —
no extra field, no extra view, nothing added to the CRM UI.

The cost of that: rename a stage out of those hints and it stops being selected.
So a run matching **no** stage records why in its note rather than reporting a
zero that reads like a quiet week. `test_renaming_a_stage_out_of_the_hints_is_reported_not_silent`
pins that behaviour.

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

## Coverage — "no lead falls through"

Three of the seven agents exist to guarantee completeness rather than to react
to a situation, and they share one design rule: **select exactly the records in
the bad state**, never a rolling window. An agent whose domain is "unassigned"
or "never scored" drains its backlog at `limit` a night and then handles only
the day's intake. An agent ordered by `write_date desc` under a limit will
circle the same recently-edited records forever and never reach the rest — which
is what `_cron_score_leads` did until `c2p_scored_on` was added, and why that
field exists.

Each of the three reports its remaining backlog in the run note, so you can see
the queue shrinking rather than guess.

Two cautions on `_cron_ensure_next_step`: it observes a three-day grace period,
because a lead that arrived this morning is not neglected, and it runs under a
low limit on purpose. On a database with thousands of untouched leads it would
otherwise create thousands of activities on its first night, which is a worse
outcome than the silence it replaces. Watch the backlog figure and raise the
limit deliberately.

## Email validation

`models/email_validation.py`, three layers, cheapest first, short-circuiting:

1. **Syntax** — Odoo's own `email_normalize`. Free, instant, catches typos.
2. **Domain class** — free provider → `risky`; disposable mailbox → `invalid`.
3. **Resolution** — MX lookup via dnspython where installed, otherwise "does the
   domain resolve at all". The verdict detail always says which check ran, so a
   result is never ambiguous about how much it proved.

Verdicts are three-valued on purpose. **`risky` is not `invalid`** — a gmail
address is perfectly deliverable, it just tells you the lead is a person rather
than a company, and only `invalid` suppresses a send.

Results land on the lead as `c2p_email_validity`, `c2p_email_validity_detail` and
`c2p_email_checked_on`. The agent only picks up leads still marked `unknown`, so
it clears the backlog once and then handles the day's intake. To re-check
everything: `leads.write({"c2p_email_validity": "unknown"})`.

**WhatsApp fallback.** `c2p_outreach_channel` is a stored computed field —
`email` when the address is usable, `whatsapp` when it is not and a number is on
file, `none` when neither. Stored so you can filter a send list on it.

**Mailbox-level verification is not implemented.** Layers 1-3 prove an address
is well-formed and its domain accepts mail; they cannot prove the mailbox
exists. That needs a paid service, and `verify_mailbox()` is the documented
place to wire one in — left as a raise rather than a guess, because the
providers' APIs differ enough that picking wrong means dead code with a
credential handler attached.

Two operational notes: dry run still performs DNS lookups (that is what makes
the reported verdicts real — dry run means nothing is written to *your*
database, not that there is no outbound traffic), and one lookup is made per
domain per batch rather than per lead.

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
