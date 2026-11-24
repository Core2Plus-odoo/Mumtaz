# C2P Work Hub

**My Work Today** and the fifteen-second task update. Wave B, slice 1.

## What it does

One page per employee listing only their own open work, split into the
sections people actually act on — overdue, due today, due soon, not updated
recently, waiting for my review, blocked, waiting on someone else, with a
reviewer, no deadline, recently assigned — plus upcoming milestones, and a
single call that records an update without opening a form.

**Blocked and waiting are kept apart.** "Something is stopping this and here is
why" and "this sits with someone else" need different action, so they are
separate sections. A task can be in both.

**The manager review queue** is derived from the project's manager field plus a
review-named stage, and excludes the manager's own tasks — those are their work,
not their queue. It is deliberately *not* an approval record: formal approvals
are a separate model in a later wave, and a half version here would leave the
business with two answers.

## What it deliberately does not do

- **No second task model.** It reads standard `project.task`.
- **No second blocker field.** When `c2p_project_tracker` is installed it
  writes that module's `blocked_reason`; standalone it records the blocker in
  chatter and leaves the stage alone.
- **No second stage concept.** Stages are matched by lower-cased name, because
  each project owns its own `project.task.type` records and there is no shared
  id to hardcode.
- **No `sudo()`.** A personal work list must show exactly what its owner may
  see, so Odoo's record rules do the filtering.
- **No stored aggregate.** Every count is read at request time, so the page can
  never disagree with the records behind it.

## Two fields added

| Field | Why |
|---|---|
| `c2p_last_update` | `write_date` moves for any change, including a bulk edit, so it cannot answer "when did this task last get a real update". This is set only by a deliberate update, and it is what staleness is measured against. |
| `c2p_next_action` | The one thing that happens next. |

## Integration with c2p_project_tracker

The tracker's constraints guard on `project_id.c2p_layer == "delivery"`, so
ordinary projects are unaffected. On a delivery project:

- `_check_blocked_reason` refuses a Waiting-on-Client stage without a reason,
  so the quick update collects the blocker **in the same call** rather than
  moving the stage first and raising at the user.
- `_check_delivery_hygiene` requires an assignee, deadline and milestone to
  leave Backlog. A quick update that would break it surfaces the server's own
  message verbatim in the UI.
- Every write goes through `write()`, so the tracker's `waiting_since`
  bookkeeping, baseline capture and portfolio resync all keep working.

## Three milestone notions, one chosen

This repository defines a milestone in three places:

| Notion | Where |
|---|---|
| Standard `project.milestone` | Odoo's own model; `c2p_project_tracker`'s hygiene constraint requires delivery tasks to reference one |
| Portfolio milestone *tasks* | `project.task` named `M1 …`, matched by `MILESTONE_CODE_RE` and tracked by `c2p.milestone.history` |
| `delivery_milestone_id` / `current_milestone_id` | pairing a portfolio milestone task to its delivery counterpart |

The hub reads the **standard model**, because it is the one with enforced data
behind it and because reading the name-matched tasks here would make this a
fourth place that decides what a milestone is. Reconciling the three is an
architecture decision and is raised with the owner rather than settled here.

## Status

**NOT RUN.** 25 tests are written and the module has never been installed —
this session has no route to an Odoo instance. Install on staging and run:

```bash
odoo -d <staging_db> -i c2p_work_hub --test-enable --stop-after-init
```

Verified so far: Python compiles and passes pyflakes; the OWL JS parses with no
duplicate top-level declarations; all four XML files parse; SCSS braces balance.
