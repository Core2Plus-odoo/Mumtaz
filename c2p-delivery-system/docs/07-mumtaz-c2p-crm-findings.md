# Mumtaz_C2P — CRM pipeline findings and proposed fixes

Produced from a read-only inspection on 2026-10-05 (Odoo 19.0-20260719,
41,182 leads, 2 won). Reproduce with:

```bash
python3 scripts/inspect_odoo_db.py Mumtaz_C2P            # whole database
python3 scripts/inspect_odoo_db.py Mumtaz_C2P --leads    # the lead pile
python3 scripts/inspect_odoo_db.py Mumtaz_C2P --diagnose # gate + automation
python3 scripts/inspect_odoo_db.py Mumtaz_C2P --action "BD Engine 1"
```

## Where this logic lives, and why that is the first problem

Both routines below are **`ir.actions.server` records stored in the database**,
not code in this repository. There are 25 such actions on `crm.lead`. They
carry the company's lead qualification, scoring, assignment and archival rules,
and they have no version history, no review, no tests and no way to roll back a
bad edit. Alongside `c2p_appointment` and `c2p_proposal` sitting untracked in the
production working tree, and `c2p_master_agent` installed with no source on the
addons path, the business logic of this database is substantially outside git.

Everything else in this document is a smaller problem than that.

The patches below are therefore written as replacement bodies to paste into the
existing actions — the pragmatic step — but the real fix is to move these into
a versioned module under `addons/`, where the repo's CI (flake8, manifest and
XML validation) can see them.

## 1. The archive sweep — 29,484 leads, no audit trail

`C2P — Archive bounced/dead-email leads (reversible)`, an active daily cron at
04:00, currently:

```python
dom=['|','|','|',('message_bounce','>',0),('tag_ids','in',[2237]),('tag_ids','in',[18]),('tag_ids','in',[2245])]
recs=model.search(dom+[('type','=','lead'),('stage_id.is_won','=',False)])
if recs:
    log('C2P cleanup: archiving %d bounced/invalid leads (was delete)' % len(recs))
    recs.write({'active': False})
```

**Its tag conditions are dead.** Tags `18`, `2237` and `2245` resolve to
`Email Invalid`, `Email Invalid — No MX (skip)` and `Email Invalid — Bad
Syntax`, and **all three are carried by zero leads** (counted with archived
records included). Three of the domain's four legs therefore match nothing, and
`message_bounce > 0` is the only live condition.

**RESOLVED, and not this cron.** The probes came back:
`message_bounce > 0` matches **8** leads, `Bounced AND archived` is **0**, and
`Archived but never bounced` is **29,484** — every archived lead. There is zero
overlap, so this cron archived none of them. Its tag legs match nothing and its
bounce leg matches 8 records, none archived.

What did it is still unidentified, but the shape is informative: of 41,182
leads, 27,603 have no email, and since only 2,382 of the 11,698 *active* ones
lack an email, roughly 25,200 of the 29,484 archived records (86%) are
email-less. Whatever ran selected on **missing email**, not on bounces. With
`write_uid` = the admin user on 29,337 of them, no lost reason on any, and no
automation whose domain fits, the likeliest explanation is a manual or ad-hoc
scripted bulk archive of email-less scrapes rather than a scheduled rule.

Also established: 29,337 of 29,484 archived leads have `write_uid` = the admin user
this cron runs as, and **not one has a lost reason** — consistent with
`write({'active': False})`, which archives without recording why. What is *not*
established is that this cron produced them: it would require ~29k leads with
`message_bounce > 0`, which would itself be a serious sender-reputation
problem. These consequences hold regardless:

- Nobody can tell afterwards which rule caught a given lead, or audit whether
  the sweep was right. 72% of all leads ever created are in this state.
- Odoo's own lost-reason reporting is empty, so win/loss analysis is impossible.
- The tag ids are hardcoded magic numbers that now match nothing, so the rule
  silently does less than it reads as doing. Whether the tags were never
  applied, or were applied by something since removed, the ids are not a safe
  way to express this and the replacement below matches tags by name.

Proposed replacement — records the reason, and reads as what it is:

```python
# Tags that mean "do not contact". Resolved by name so the rule is readable
# and survives a tag being recreated with a new id.
DEAD_TAGS = ['Invalid Email', 'Bounced', 'Do Not Contact']
tag_ids = env['crm.tag'].search([('name', 'in', DEAD_TAGS)]).ids
dom = ['|', ('message_bounce', '>', 0), ('tag_ids', 'in', tag_ids)]
recs = model.search(dom + [('type', '=', 'lead'), ('stage_id.is_won', '=', False)])
if recs:
    reason = env['crm.lost.reason'].search(
        [('name', '=', 'Bounced / invalid email')], limit=1)
    if not reason:
        reason = env['crm.lost.reason'].create({'name': 'Bounced / invalid email'})
    log('C2P cleanup: marking %d bounced/invalid leads lost' % len(recs))
    # action_set_lost archives AND records the reason, so the sweep is auditable.
    recs.action_set_lost(lost_reason_id=reason.id)
```

Note this is a **behaviour change**: it writes `lost_reason_id` and moves the
records through Odoo's lost flow rather than flipping `active` silently. That is
the point, but it means the first run after the change should be done with the
cron disabled and the domain inspected by hand — the existing 29,484 are
already archived and will not be revisited.

## 2. `BD Engine 1` assigns every qualified lead to one hardcoded user

`C2P BD Engine 1: Qualify, score & assign leads` runs hourly over 150 leads and
contains:

```python
if status == 'queued':
    vals['user_id'] = 42
```

Every lead that qualifies goes to user id `42`. Leads that do not qualify go to
`REP.get(cc, 11)` — user `11` or `12`. That is the entire assignment policy, and
it explains the distribution precisely: Aisha Rahman 5,102, Raza 2,290, Omar
Al-Farsi 1,762 — three hardcoded ids holding the overwhelming majority of
41,182 leads, with nothing anywhere that considers capacity.

A correction to an earlier guess of mine: I attributed this skew to the
`crm_team_id` / `user_id` defaults on `lead.scraper.source`. Those exist and do
set an owner at creation, but this engine **overwrites** them an hour later, so
the hardcoded ids here are the operative cause.

There is already a `C2P: Assign lead round-robin` server action in the database,
unused by this path.

Proposed replacement for the assignment block — distribute across the
destination team instead of pinning one person:

```python
# Round-robin across the destination team's members. Falls back to the team
# lead, then to the previous hardcoded owner, so a team with no members set
# still assigns rather than silently leaving the lead unowned.
team = env['crm.team'].browse(vals.get('team_id') or 9)
pool = team.member_ids or team.user_id
if status == 'queued':
    vals['user_id'] = pool[n_q % len(pool)].id if pool else 42
    vals['x_bd_step'] = 1
    vals['x_bd_next'] = today
    seen.append(dom)
    n_q += 1
```

Capacity is the harder half and is not solved by round-robin alone: at ~473
leads a day arriving, any distribution still exceeds what the team can work.
That needs a cap on how many open leads a rep may hold, which is a policy
decision rather than a code one.

## 3. A full-table scan per lead, hourly

Inside the per-lead loop:

```python
elif dom not in FREE and (dom in seen or env['crm.lead'].search_count([('email_from', '=ilike', '%@' + dom), ('x_bd_status', 'in', ['queued', 'active', 'replied', 'interested'])])):
    status = 'skipped_dup'
```

`=ilike '%@domain'` has a leading wildcard, so no index can serve it: each call
is a sequential scan of `crm.lead`, now 41,182 rows. That is up to 150 scans per
run, every hour, plus a `mail.blacklist` lookup per lead. Hoist it into one
aggregate before the loop:

```python
# One pass to collect domains already in flight, instead of a per-lead
# unindexable '%@domain' scan over the whole lead table.
engaged = set()
for r in env['crm.lead'].read_group(
        [('x_bd_status', 'in', ['queued', 'active', 'replied', 'interested']),
         ('email_from', '!=', False)],
        ['email_from'], ['email_from'], lazy=False):
    em = (r.get('email_from') or '').strip().lower()
    if '@' in em:
        engaged.add(em.split('@')[-1])
```

then in the loop:

```python
elif dom not in FREE and (dom in seen or dom in engaged):
    status = 'skipped_dup'
```

## 4. Smaller defects in the same action

- `TEAM = {'AE': 6, ...}` and `HOT_REPS = [11, 12]` are defined and never used.
  `TEAMR` and `REP` are redefined on every iteration inside the loop. Dead and
  duplicated code in a routine this consequential is how the hardcoded ids
  survived review.
- `title = (l.function or (l.name or '').split('—')[-1]).lower()` falls back to
  part of the lead *name* when `function` is empty. Lead names are
  `"Company (via Source)"`, so the C-level/director scoring that depends on
  `title` is matching against a company name for most records — the +25 and +12
  score bumps are largely noise.
- There is no error isolation: `l.write(vals)` is unguarded, so one bad record
  aborts the whole run and rolls back every lead processed before it. Wrap the
  body in `try/except` and `log()` the failure to make the run resilient.

## 5. Automation that is switched off

- **`Automation Rules: check and execute` is INACTIVE.** This is Odoo's own base
  cron that fires *time-based* automation rules, so every `on_time` rule in the
  database never runs. Anything built as a time-based rule is dead code today.
- Of 12 automation rules on `crm.lead`, 8 are inactive — including
  `C2P: Won -> delivery project`, `C2P: Qualified -> human BD`, both
  `Auto-route` rules, and `C2P: Auto-score new/updated leads`. The scoring and
  routing the engine implies is largely disabled.
- `Lead Nurture: Run Sequence Steps` and `Auto-Convert Qualified Leads` are both
  inactive with a `nextcall` still at 2026-07-11 — they have not run since the
  database was ~1 day old.

## 6. Open questions this inspection could not answer

- **What converts leads to opportunities.** `crm.lead.default_get(['type'])`
  returns `'lead'` for the admin user, so the Leads gate is on for *that* user.
  But the default is per-user — `'lead'` only if the creating user has
  `crm.group_use_lead` — so a scraper or engine running as a user outside that
  group would still create opportunities directly. Check the group's membership
  against the 41 active users, and the owner of the cron that creates leads.
  Note also that the archive sweep only touches `type = 'lead'`, which biases
  the surviving population towards opportunities regardless.
- **Which `source_id` values are set by what.** `mumtaz_lead_scraper`'s
  `crm_mapper._build_vals()` sets no `source_id` or `medium_id`, yet ~6,600
  leads carry named sources. Likely `c2p_master_agent`, whose source is not in
  the repo and could not be read.
- **Whether `x_bd_*` are Studio fields or module fields.** The whole-database
  report counts *manual models* (0) and so says "0 Studio customisations"; it
  does not count manual *fields*, which is what `x_bd_status`, `x_bd_score`,
  `x_bd_sector`, `x_bd_trigger`, `x_bd_step` and `x_bd_next` would be if added
  through Studio. That row should not be read as "no Studio usage".

## Suggested order

1. Resolve tags `18`, `2237`, `2245` — one command, and it decides whether the
   sweep is defensible as written.
2. Fix the hardcoded `user_id` (§2) and hoist the domain scan (§3). Both are
   contained, and together they address the two numbers that look worst.
3. Add the lost reason to the sweep (§1), with the cron disabled for one manual
   run first.
4. Get the three untracked modules and these 25 server actions into git.
