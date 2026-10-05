# C2P Project Tracker

Portfolio and delivery tracking across the C2P consulting group, on Odoo 19
**Community**. No Enterprise dependency: `depends` is `project` and `mail` only.

## Why it exists

C2P runs a two-layer structure. **C2P Consultants FZC LLC** sells to the client
and tracks the engagement as milestones; **C2P Solutions** does the delivery in
a separate company, with its own tasks and native `project.milestone` records.
Nothing joined the two, so the Managing Partner had no portfolio view and the
delivery lead had no hygiene control.

This module adopts that structure rather than replacing it. It adds no new
project or task concept — it classifies the projects that exist, links the
pairs, and derives portfolio state from delivery state.

## Data model

```
project.project  (c2p_layer = portfolio)         project.project  (delivery)
  ├─ engagement: type, AM, contact, dates          company: C2P Solutions
  ├─ commercials: contract / received /          ┌─ c2p_counterpart_id ─┐
  │   outstanding / 60-40 split / margin         │  (reciprocal link)   │
  ├─ health: rag_status + rag_reasons,           └──────────────────────┘
  │   health_score, progress_pct                           │
  └─ project.task  (c2p_is_milestone)                      │
       ├─ c2p_code  "M1" ──── delivery_milestone_id ──→ project.milestone
       ├─ weight, baseline_deadline, slippage_days          │ is_reached
       ├─ billing_pct / amount / invoice_status             │ deadline
       └─ sync_locked                                       └─ project.task
                                                               ├─ stage_id
  c2p.milestone.history  (append-only, one row per change)     ├─ milestone_id
  c2p.raid.item          (risk/assumption/issue/dep/decision)  ├─ waiting_since
  c2p.change.request     (CR-###, moves contract value once)   └─ blocked_reason
```

Two structural facts drove the design, both from inspecting the live database:

- **Portfolio projects contain ordinary tasks as well as milestones** — project
  14 has 16 tasks for 8 milestones. So `c2p_is_milestone` requires the name to
  match `^M\d+`; being in a portfolio project is not sufficient.
- **Stages are per-project `project.task.type` records**, not shared. Every
  stage lookup is by name within the project; no stage id is hardcoded.

## The sync engine

`project.project._c2p_sync_portfolio_milestones()` runs on write of a delivery
task's `stage_id`, `milestone_id` or `date_deadline`, and hourly from
`cron_c2p_sync` as a safety net.

For each portfolio milestone with a matched delivery milestone, unless
`sync_locked`:

**Deadline** — the delivery milestone's `deadline` is copied across, and sets
`baseline_deadline` if that is still empty. A *missing* delivery deadline is
left alone rather than copied: blanking the portfolio date would destroy the
baseline that slippage is measured against.

**Stage**, first rule that matches wins:

| # | Condition | Portfolio stage |
|---|---|---|
| 1 | delivery milestone `is_reached` | Done |
| 2 | any linked task Waiting on Client | Blocked |
| 3 | at least one task, and all done | Client Review |
| 4 | any task done, in progress or in review | In Progress |
| 5 | otherwise | unchanged |

Every change writes a `c2p.milestone.history` row and posts an internal note
(`mail.mt_note`, no `partner_ids`) reading
`Auto-sync: Old → New (X done / Y open / Z waiting on client)`. **No email is
sent**, which matters because these projects have client followers.

## RAG rules

Thresholds are `ir.config_parameter` values under `c2p_project_tracker.*`,
falling back to the defaults below.

**Red** if any of: a milestone overdue by more than `red_milestone_overdue_days`
(7); a client blocker older than `red_blocker_days` (14); go-live slipped more
than `red_slippage_days` (21); no delivery activity for `red_inactive_days` (14)
while milestones are open.

**Amber** if any of: a milestone 1–7 days overdue; a blocker
`amber_blocker_days` (7) to 14 days old; no activity for `amber_inactive_days`
(7) to 14 days; an open milestone with no deadline; no milestones defined;
commercials missing; outstanding above half the contract while progress is past
50%.

**Green** otherwise. `health_score` starts at 100 and subtracts 20 per red
factor and 8 per amber, floored at 0. `rag_reasons` lists the factors, and is
readable by a Delivery Lead *without* the amounts behind them.

`rag_override` with `rag_override_reason` overrides the computed status, and the
reason appears first in the factor list.

### Configuration

```python
env["ir.config_parameter"].set_param(
    "c2p_project_tracker.red_blocker_days", "10")
```

Keys: `red_milestone_overdue_days`, `red_blocker_days`, `red_slippage_days`,
`red_inactive_days`, `amber_blocker_days`, `amber_inactive_days`.

## Security

Three groups under the **Project Tracker** privilege, each implying the one
below:

| Group | Delivery | Portfolio milestones | Commercials | Portfolio menu |
|---|---|---|---|---|
| Delivery Member | own company | — | no | no |
| Delivery Lead | full control | read | **no** | no |
| Portfolio Manager | full | full | yes | yes |

All twelve commercial fields carry `groups=`, so they are unreadable over RPC,
absent from `fields_get()`, and the Commercials page is hidden at page level
too. `test_security.py` asserts each of these.

Cross-company aggregation (a Consultants milestone reading Solutions tasks)
happens only in `_c2p_delivery_project()`, `_compute_delivery_activity()` and
`_c2p_oldest_blocker_days()`, which use `sudo()` for the read and return counts
and timestamps only — never task detail.

## Installing

See `scripts/backup_and_install.md`. In short: back up, restore onto a copy,
**disable that copy's crons and mail servers**, install there, run the tests,
verify by hand, and only then install on production.

`post_init_hook` classifies the existing projects, links the four pairs,
matches milestones by `M` code, seeds the known commercials with the 60%
default, runs a first sync, and assigns the groups. Everything is matched by
name and partner rather than trusted by id, and a miss is logged rather than
raised, so it is safe to run on a duplicate.

## Known state on first install

- All 24 delivery milestones currently have **no deadline** and are **not
  reached**, so the first sync propagates no dates and every engagement reads
  **Amber** on "open milestones have no deadline". That is the data, not a bug.
- Medicslab and GECHS have **no commercials**, so both are flagged
  `commercials_missing` — also an amber factor.
- Project 9 (`S00131 - Odoo ERP Implementation`) is archived and superseded by
  project 17; it is deliberately left unclassified and excluded.

## Not built

The two OWL dashboards, the QWeb PDFs and the weekly status report are not in
this version. On the status report: Odoo Community already ships **Project
Updates** (`project.update`, with `project.project.last_update_status`), which
covers a periodic status post with a RAG-style status and description. The
recommendation is to extend that rather than add a parallel model, so that
`last_update_status` and this module's RAG do not drift apart.
