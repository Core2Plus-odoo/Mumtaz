# C2P Meeting Actions

Minutes of meeting whose action items become `project.task` records **exactly
once**, however many times anyone clicks and whatever happens concurrently.

## The duplicate guard

The requirement is that duplicate task creation be impossible under
concurrency. That rules out a Python check-then-create, which two simultaneous
transactions both pass. The guard is therefore a database unique constraint:

```python
# models/project_task.py
c2p_meeting_action_ref = fields.Char(readonly=True, copy=False, index=True)
_meeting_action_ref_unique = models.Constraint(
    "UNIQUE(c2p_meeting_action_ref)",
    "A task already exists for that meeting action item.")
```

`action_create_task()` then has three layers, in order of how much each is
trusted:

1. **`task_id` already set** — return it. Covers the ordinary repeat click.
2. **A task already carries this reference** — adopt it. Covers a previous
   attempt that created the task but lost its `task_id` write to a rollback.
   A Python-only guard never notices this case and happily creates a second task.
3. **Otherwise create inside a savepoint and flush.** If a concurrent
   transaction won the race, the constraint raises a unique violation; the
   savepoint keeps the rest of the transaction usable, and the loser adopts the
   winner's task rather than creating a rival.

Two details that matter more than they look:

- **`copy=False`** on the reference. Duplicating a task must not carry the
  reference across, or the copy collides with its own original.
- **NULLs are distinct** under a PostgreSQL unique constraint, so ordinary
  tasks — nearly all of them — are unaffected.

## Durable identity

Meetings draw `MOM/<year>/<n>` from an `ir.sequence`. Actions derive
`<meeting reference>-A<n>`, numbered within the meeting, so a reference says
which minutes it came from and can be cited in an email or a client document
and still be found years later. Both are `UNIQUE`, so a collision is a database
error rather than a silent duplicate. A freed number is reused, never
duplicated.

## Approval

`draft → proposed → approved → converted`, with `rejected` as a terminus that
requires a reason. Approval authority is its own group,
`group_c2p_meeting_approver`, rather than reusing project manager — the people
who sign off an action item are not necessarily the people who administer
projects, and the authorisation model asks for requester and approver to be
separable.

Self-approval is **permitted but never silent**: it is written into the chatter
explicitly, so an audit sees it instead of inferring it from two fields.

This is deliberately *not* the formal approval record for milestones and billing
authorisation — that is a separate model in a later wave. Conflating them would
leave the business with two answers to the same question.

## Minutes as evidence

Confirming freezes the narrative fields — title, date, attendees, agenda,
discussion, decisions. Once a decision has been circulated, silently editing the
record of it is how minutes stop being evidence. Action items stay editable,
because following them up is the point. An approver can reopen, and the reopen
is logged.

## Visibility

Minutes routinely carry commercial and personnel discussion, so they are **not**
visible to every project user. A record rule limits them to the chair, the
attendees, the author and the project's manager; project managers see all
minutes in their allowed companies. Action items follow their minutes rather
than carrying separate logic, so there is one answer to "who may see this
meeting".

## Status

**NOT RUN.** 31 tests are written and the module has never been installed —
this session has no route to an Odoo instance. On staging:

```bash
odoo -d <staging_db> -i c2p_meeting_actions --test-enable --stop-after-init
```

Verified so far: `compileall` clean; flake8 clean with the exact CI versions;
every XML file parses; the manifest is a dict literal with every data path
resolving; no `attrs=`, `<tree>` or `states=`; no `sudo()`.

Note the one deliberate test limitation: a true two-process race cannot be
written reliably inside a `TransactionCase`, because the second cursor would not
see uncommitted data. `test_the_database_refuses_two_tasks_for_one_action`
asserts the constraint itself instead, which is the control that actually makes
the concurrent case safe.
