# Delivery team guide — three rules

For the C2P Solutions delivery team. One page, three rules. Everything the
Managing Partner sees about your projects is derived from these.

---

## 1. Assignee + deadline + milestone, before a task leaves Backlog

A task can sit in **Backlog** with nothing filled in. The moment you move it to
**To Do** or beyond, Odoo requires all three:

- **Assignee** — who is doing it
- **Deadline** — when it is due
- **Milestone** — which `M#` it serves

If any is missing you get an error naming exactly which. Fix them on the task,
or move it back to Backlog.

**Why:** the portfolio view reports progress per milestone and workload per
person. A task with no milestone is invisible to the client-facing view; a task
with no deadline can never be overdue, so it silently never gets chased.

Find anything that slipped through: **Project Tracker → Delivery → Data
hygiene**.

---

## 2. Waiting on Client needs a reason

Moving a task to **Waiting on Client** requires **Blocked Reason** — one line
on what the client owes you.

Two things happen automatically:

- The matching Consultants milestone turns **Blocked**, so the client's own
  delay is visible as the client's delay rather than ours.
- The clock starts. After 7 days the engagement goes Amber, after 14 Red.

**Why:** "waiting on the client" is the single most common reason a project
slips. Recorded with a reason and a date it is evidence; unrecorded it looks
like our delay.

Move it out of Waiting on Client as soon as the client responds — the clock
only stops when the stage changes.

---

## 3. One status update per project per week

One update per project, each week, before Friday midday.

Say what was achieved, what is next, and what you need **from the client**.
That last part is what gets escalated.

**Why:** it is the only input the portfolio view cannot derive from task data.
A missing update makes an engagement Amber by itself.

---

## What you will never see

Any money. Contract values, payments and the Solutions share are restricted to
the Managing Partner. You will see **why** a project is Amber or Red —
including "commercials missing" — but never an amount. That is by design, not a
permissions bug.

## What good looks like

- Nothing in **Data hygiene**
- Every Waiting on Client task has a reason and a recent date
- Every milestone has a deadline
- A status update filed each week

If all four hold, the portfolio view is accurate and nobody needs to ask you
for a status.
