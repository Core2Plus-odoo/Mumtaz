# The daily workflow

The test of this design is not completeness, it is whether a delivery consultant
can keep it current in two minutes a day and a Consultants partner can trust
what they read on Monday morning. Everything below is shaped by that.

---

## 1. Who does what

| Party | Owns |
|---|---|
| **C2P Consultants FZC LLC** | The client relationship, scope, commercial record, all client-facing documents and email, approvals, invoicing decisions, portfolio oversight |
| **C2P Solutions** | Delivery: the project plan, tasks, milestones, dependencies, outsourced teams, QA, delivery evidence |
| **Subcontractor** | Only their own work package, only their permitted attachments |
| **Client** | Acceptance decisions, master data, their own action items |

Every client-facing document and email carries **C2P Consultants** branding and
name. Solutions and subcontractors appear internally as delivery parties.

---

## 2. The spine, end to end

```
Opportunity (crm.lead)
   │  proposal issued            c2p_proposal → branded PDF
   ▼
Sale order confirmed  ──────────────────────────────┐
   │                                                │
   ▼                                   NOT a trigger for onboarding
ONBOARDING GATE  ◄── an authorized person records the accepted contract
   │                 and ticks the readiness checklist (§3)
   │  one idempotent action
   ├──────────────► Portfolio project   (Consultants engagement view)
   │                      ▲  c2p_counterpart_id, UNIQUE
   └──────────────► Delivery project    (Solutions execution)
                          │
                          ├─ contracted deliverables  → milestones → tasks
                          ├─ work packages (outsourced)
                          └─ evidence, QA, acceptance
```

**The gate is the point.** A CRM Won stage is not a signed agreement, and a
confirmed sale order is not either — the brief says so and it is right. Nothing
is created, no email is drafted and no kickoff is scheduled until a named,
authorized person asserts that the contract is accepted.

---

## 3. The onboarding gate

Onboarding cannot start until an authorized user records the accepted contract
or approved order **and** every line below is either filled or explicitly marked
not-applicable with a reason:

| Check | Why it is a gate, not a nice-to-have |
|---|---|
| Correct **legal** client entity | The invoice and the contract must name the same entity; getting this wrong after go-live is painful |
| Named client contacts, with roles | Acceptance needs a named approver, not "the client" |
| Agreed scope **and exclusions** | Exclusions are what prevent the first change request becoming an argument |
| Contracted deliverables | The milestone set is generated from these, so a blank here means a generic plan |
| Acceptance method per deliverable | Decide how "done" is proved before doing the work |
| Schedule assumptions | A date without its assumption is a promise nobody can keep |
| Payment milestones | Billing eligibility is derived from these |
| Confidentiality and access requirements | Determines whether a subcontractor may see anything at all |
| Internal project owner (Solutions PM) | Unowned projects are how delivery drifts |

**On passing the gate, one action does all of this exactly once:**

1. Creates or links the portfolio and delivery projects (the pairing in
   `01-FIT-GAP.md` §2 makes a second pair impossible).
2. Generates milestones **from the recorded deliverables**, not a fixed list.
3. Creates the internal handoff activities for Consultants → Solutions.
4. **Prepares as drafts** the client welcome email and the master-data request.
5. Schedules the kickoff activity.
6. Creates a draft charter.

Items 4 and 6 are drafts. Nothing leaves the building until §6 happens.

---

## 4. The task workflow

Recommended shape — option **B** from `01-FIT-GAP.md` §3, which keeps the
existing stage names because the code matches stages by name:

```
Backlog → Ready → In Progress → Review → Waiting on Client → Done
                                   │
                                   └── Internal QA happens here, before
                                       anything is offered to the client
```

- **Blocked** is not a stage. It is a `blocked_reason` on the task, plus
  `Waiting on Client` when the blocker is the client. The existing hygiene
  constraint already refuses a Waiting-on-Client task with no reason, which is
  the behaviour you want and it is already enforced.
- **Cancelled** is the standard `project.task.state` value, not a stage. Stages
  are delivery phases; status is status. That is the approved decision and it
  is also simply clearer.

Every task carries: owner, due date, definition of done, dependencies, checklist
where useful, estimated effort, evidence link, and a reason when blocked. The
existing constraint already forces assignee + deadline + milestone before a task
may leave Backlog — which is the cheapest quality control in the system.

**Daily, for a delivery consultant:** open *My Work Today*, and for each task
either record progress, state the next action, or say what is blocking. One
screen, one save. That is the whole daily obligation.

---

## 5. Milestones and acceptance

Two separations that must never collapse:

1. **All tasks Done ≠ milestone reached.** Reaching a milestone is an internal
   assertion that the deliverable is ready to offer.
2. **Milestone reached ≠ client accepted ≠ billable.** Client acceptance is a
   recorded decision by a named client approver. Billing eligibility is a
   consequence of acceptance plus the payment schedule, and is a *flag for
   Consultants to review*, never an invoice action.

Acceptance outcomes are **accepted / accepted with comments / partially
accepted / rejected — rework required**. A two-state field would force people to
record a lie.

An outsourced contributor can never approve their own deliverable. Internal QA
by a Solutions reviewer happens before anything reaches the client.

---

## 6. External communication

Every client-facing message is **drafted by the system and sent by a person**.

| Step | Who |
|---|---|
| Draft prepared | automation |
| Recipients and content reviewed | authorized C2P Consultants user |
| Sent | that user |
| Recorded | who approved, who sent, when, to whom |

The same applies to inviting a portal user and to granting subcontractor access.
No automation sends an external email, invites a portal user, posts an invoice,
or records client acceptance.

---

## 7. Outsourced delivery

One work package per external team: scope, deliverables, acceptance criteria,
due dates, **commercial terms in a restricted area**, access period, NDA and
security requirements, owner, review cycle, escalation contact.

The subcontractor sees their assigned work and permitted attachments — nothing
else. Not other work packages, not rates, not internal discussion, not other
clients. Access is time-bounded and expires. Revisions, defects, delays and
acceptance are tracked against the package so that performance is a fact rather
than an impression.

No subcontractor receives administrator rights or cross-company visibility.

---

## 8. The weekly rhythm

| When | What | Who |
|---|---|---|
| Daily | Progress, blockers, next actions | Delivery team, via My Work Today |
| Daily | Blocked and overdue review | Solutions PM |
| Weekly | PM update request → status report drafted | Automation drafts, PM completes |
| Weekly | Status report reviewed and sent | Consultants |
| Per meeting | Minutes recorded, actions approved and converted to tasks once | PM records, approver approves |
| Per milestone | Internal QA → offer to client → acceptance recorded | Solutions then Consultants |
| Per change | Impact assessed, approved, then applied | Consultants approves |
| At close | Handover, support transition, final acceptance | Both |

---

## 9. RAG health, and why every amber has a name on it

RAG is computed and stored once, and both the Consultants engagement and the
Executive Command Centre read **the same stored value**. There is no second
calculation. The existing engine already stores `rag_status`, `rag_reasons` and
`health_score` with configurable thresholds and an audited override.

The rule that makes it useful: **every red or amber states why, who owns it, and
what happens next.** A colour with no reason is noise, and people learn to
ignore it within a fortnight.

What the engine still needs before it can be trusted for client reporting
(`01-FIT-GAP.md`): a calculation timestamp, the input version, a freshness
indicator, and an expiry on manual overrides. A RAG that may be three weeks
stale, with no way to tell, is worse than no RAG.
