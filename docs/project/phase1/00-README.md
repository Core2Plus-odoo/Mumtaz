# Phase 1 — Verified current state, fit-gap, workflow, templates, plan

**Scope:** read-only. No code edited, no Odoo configured, no email sent, nothing
deployed. Produced against the repository at the merge commit `876f321`
(branch `claude/gifted-turing-jjdsb2`, `main` merged in on 24 Nov 2026).

## Evidence markers used throughout

| Marker | Meaning |
|---|---|
| **[VERIFIED]** | Read from the repository at `876f321` by a command recorded inline. Reproducible. |
| **[LIVE-UNKNOWN]** | Cannot be established from source. Needs the running database. Listed in §Live questions below. |
| **[PROPOSED]** | A design choice of mine. Not approved, not built. |
| **[DECISION]** | Needs an authorized person. Blocks what it says it blocks. |

## Contents

| Deliverable | Document |
|---|---|
| Fit-gap | [`01-FIT-GAP.md`](01-FIT-GAP.md) |
| Daily workflow, stages, gates, roles | [`02-WORKFLOW.md`](02-WORKFLOW.md) |
| Document pack (15 templates) | [`templates/`](templates/) |
| Staged implementation plan | [`03-IMPLEMENTATION-PLAN.md`](03-IMPLEMENTATION-PLAN.md) |

## What this Phase 1 can and cannot claim

**It can claim** what the code does, because it reads the code. The headline
result of that reading is narrow and useful:

> **No production code in any of the 60 modules creates a `project.project`.**
> The only matches are test fixtures. And no module declares a dependency on
> `sale_project`, `sale_timesheet` or `hr_timesheet`.

So every project-creation path in this estate is either Odoo's standard
`sale_project` behaviour driven by `service_tracking` on the product, or a
**database-resident automation** — `base.automation`, `ir.actions.server`,
`ir.cron` — which is a record, not a file, and therefore invisible to any
amount of code reading.

**It cannot claim** what is installed, configured or running. This container has
no route to the database:

```
187.77.128.199:22    → refused
187.77.128.199:8069  → refused
erp.mumtaz.digital   → CONNECT 403 at the agent proxy
```

## Live questions — the complete list

These are the only things Phase 1 could not settle. The existing read-only
inspector answers all of them in one pass
(`c2p-delivery-system/scripts/inspect_odoo_db.py --pm-audit --json`), run on the
VPS as a dedicated read-only Odoo user.

1. Which of the 60 modules are **installed**, in which database. **[LIVE-UNKNOWN]**
2. Is `sale_project` installed, and what is the `service_tracking` distribution
   across service products? This decides whether a confirmed order already
   creates a project. **[LIVE-UNKNOWN]**
3. Every `base.automation`, `ir.actions.server` and `ir.cron` touching
   `crm.lead`, `sale.order`, `project.project` or `account.move` — with its
   trigger and code. **This is where duplicate project creation lives.** **[LIVE-UNKNOWN]**
4. Actual `project.task.type` stage names per project, since the tracker matches
   stages by name (see `01-FIT-GAP.md` §3). **[LIVE-UNKNOWN]**
5. Whether `c2p_master_agent` is installed and who is in `base.group_user`. **[LIVE-UNKNOWN]**
6. Existing `project.project` records, their `c2p_layer` values and whether any
   counterpart pairs exist. **[LIVE-UNKNOWN]**
7. Existing email templates and which are used by automations. **[LIVE-UNKNOWN]**
8. The R0–R7 acceptance-gate definitions, which exist in no file in this
   repository. **[DECISION]**

Nothing in the implementation plan past Stage 0 should start before 1–3 are
answered, because each could mean the work collides with something already
running.
