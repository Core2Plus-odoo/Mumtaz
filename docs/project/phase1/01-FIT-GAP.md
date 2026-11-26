# Fit-gap — the C2P client project operating system

Against the repository at `876f321`. Scoring is standard-first: **Standard**
(Odoo does it, use it) → **Configure** → **Reuse** (we already built it) →
**Extend** (small add-on) → **Build** (approved gap only).

---

## 1. The required data relationship, link by link

> CRM opportunity → signed scope/contract and sale order → Consultants client
> engagement → Solutions delivery project → contracted deliverables →
> milestones → tasks → evidence and approvals

| Link | Status | Evidence |
|---|---|---|
| Opportunity → sale order | **Standard + Reuse** | `crm`, `sale_management`; `c2p_proposal` extends `sale.order` and `crm.lead` with a branded proposal report **[VERIFIED]** |
| Sale order → engagement | **Reuse** | `project.project.c2p_sale_order_id` already exists **[VERIFIED]** |
| **Engagement ↔ delivery project** | **Reuse — already DB-enforced** | see §2 below **[VERIFIED]** |
| Contracted deliverables | **Build** | no deliverable record exists; see §4 |
| Milestones | **Reuse, after a decision** | three competing notions; see §5 **[DECISION]** |
| Tasks | **Standard + Reuse** | `project.task`; `c2p_work_hub` for the daily view **[VERIFIED]** |
| Evidence | **Extend** | `ir.attachment` exists; no evidence-per-deliverable link |
| Approvals | **Partial Reuse** | `c2p_meeting_actions` has an approval chain; no deliverable-acceptance record |

**The headline:** roughly two thirds of the required chain already exists. The
genuine gaps are three, not fifteen: **the onboarding gate**, **the contracted
deliverable + acceptance register**, and **the outsourced work package**.

---

## 2. The engagement ↔ delivery pairing already satisfies the brief

The brief asks for "one controlled pairing between relevant commercial and
delivery records" and an idempotent creation process where "repeating a trigger
cannot create a second engagement [or] delivery project".

That is already built, and the guarantee is at the database, not in Python
**[VERIFIED]** (`addons/c2p_project_tracker/models/project_project.py`):

```python
c2p_layer          = Selection([("portfolio", ...), ("delivery", ...)])
c2p_counterpart_id = Many2one("project.project")
c2p_sale_order_id  = Many2one("sale.order")

_counterpart_unique = models.Constraint("UNIQUE(c2p_counterpart_id)",
    "Two projects cannot share the same counterpart project.")

@api.constrains("c2p_counterpart_id", "c2p_layer")   # exactly one portfolio
def _check_counterpart_pairing(self): ...            # + one delivery per pair
```

**Reuse it. Do not build an engagement model.** The brief itself says the
Consultants engagement is "a lightweight oversight record or view, not a second
full task board" — which is exactly what the portfolio-layer project is. A new
model would be the second task board the brief forbids.

**One consequence worth stating:** the Consultants engagement is therefore a
*view and a set of fields on a `project.project`*, not a separate object. Its
"engagement reference" should be the portfolio project's own stable reference.

---

## 3. The task workflow does not match — and renaming stages would break things

The brief asks for: `Backlog → Ready → In Progress → Internal Review → Client
Review → Done`, with Blocked and Cancelled represented clearly.

What the code expects **[VERIFIED]** (`project_task.py:13-23`):

```python
DELIVERY_BACKLOG   = "backlog"
DELIVERY_WAITING   = "waiting on client"
DELIVERY_DONE      = "done"
DELIVERY_IN_FLIGHT = ("in progress", "review")

PORTFOLIO_NOT_STARTED   = "not started"
PORTFOLIO_IN_PROGRESS   = "in progress"
PORTFOLIO_BLOCKED       = "blocked"
PORTFOLIO_CLIENT_REVIEW = "client review"
PORTFOLIO_DONE          = "done"
```

**Stages are matched by lower-cased name, not by id** — deliberately, because
each project owns its own `project.task.type` records so there is no shared id
to reference. That makes stage names load-bearing code.

### The side effect, stated plainly

Splitting `Review` into `Internal Review` and `Client Review` means
`DELIVERY_IN_FLIGHT = ("in progress", "review")` **matches neither**. Odoo's
name matching here is equality, not substring. Consequences on the delivery
layer:

- tasks in review stop counting as in-flight,
- which changes `_compute_health`, so **RAG silently shifts** on every project,
- `_is_waiting_on_client()` stops firing if `Waiting on Client` is renamed,
  so `waiting_since` stops being maintained and `_check_blocked_reason` stops
  demanding a reason.

None of this raises an error. It just quietly produces different numbers.

### [PROPOSED] resolution

Two options, and I recommend the second:

| Option | What it costs |
|---|---|
| **A.** Rename live stages to the brief's names | Touches live `project.task.type` records; requires the constants and their tests to change in the same release; any missed name is a silent behaviour change |
| **B.** Keep the existing names, add only what is missing | `Ready` added between Backlog and In Progress; `Cancelled` represented by the standard `project.task.state` value rather than a stage; `Blocked` stays a `blocked_reason` + `Waiting on Client`, which is what the hygiene constraint already enforces |

**B** gets the brief's intent — a clear, consistent workflow with Blocked and
Cancelled visible — without making stage names a migration. It also respects the
approved decision that "existing Odoo task statuses remain canonical" and that
"project stages represent delivery phases, not duplicate task statuses".

If **A** is chosen it must be a single release that changes stages, constants
and tests together, run against a restored copy first. **[DECISION]**

---

## 4. Deliverables and acceptance — the real gap

Nothing in the estate represents a *contracted deliverable* or its *acceptance*.
`project.milestone` has `is_reached`; that is a delivery fact, not a client
decision, and the brief is explicit that a milestone must never be
client-accepted merely because its tasks are Done.

**[PROPOSED] Extend**, one small model:

- `c2p.deliverable` — description, acceptance criteria, acceptance method,
  baseline/forecast dates, internal reviewer, client approver, linked milestone,
  linked tasks, evidence attachments, commercial linkage, status.
- Acceptance outcomes must include **partial** and **rejected/rework**, not just
  accepted — the brief requires it and a two-state field would force people to
  lie.
- Billing eligibility is a *flag on acceptance*, never an invoice action. The
  brief and the earlier approved decisions both separate billing authorization
  from milestone completion.

## 5. Milestones — one decision needed before any build

Three notions exist **[VERIFIED]**:

| Notion | Where |
|---|---|
| Standard `project.milestone` | Odoo's model; the tracker's hygiene constraint *requires* delivery tasks to reference one |
| Portfolio milestone **tasks** | `project.task` named `M1 …`, matched by `MILESTONE_CODE_RE`, tracked by `c2p.milestone.history` |
| `delivery_milestone_id` / `current_milestone_id` | pairing a portfolio milestone task to its delivery counterpart |

The brief says milestones are delivery gates generated from actual contracted
deliverables. That fits **standard `project.milestone`** best, with
`c2p.deliverable` as its contractual parent. The portfolio milestone-task
convention then becomes a *presentation* of those milestones on the Consultants
side rather than a second source of truth. **[DECISION]** — it changes what
`c2p.milestone.history` baselines.

## 6. Documents

`c2p_proposal` already produces a branded client PDF: a `sale.order` extension,
one QWeb report, a proposal wizard, reference data, and embedded IBM Plex / Work
Sans / Liberation fonts **[VERIFIED]**. So the Consultants-branded document
machinery exists; the document pack should **inherit its layout and fonts**
rather than start a second visual identity.

Templates in [`templates/`](templates/) are deliberately written to mirror
existing record fields where a record already exists — for instance the change
request mirrors `c2p.change.request` (`reference`, `impact_days`,
`impact_amount`, `state`, `approved_date`) and the RAID log mirrors
`c2p.raid.item` (`item_type`, `impact`, `probability`, `score`, `state`,
`resolution`) **[VERIFIED]** — so a document is a rendering of data already
captured, not a parallel form somebody retypes.

## 7. Automations

**[VERIFIED]** No code path creates a project. **[LIVE-UNKNOWN]** What the
database automations do. Until question 3 in `00-README.md` is answered, the
automation register cannot be written, and any new automation risks being the
second one for a process already handled.

## 8. The control that cannot wait

`c2p_master_agent` **[VERIFIED]**: 272 lines, zero tests, grants
`base.group_user` full `read/write/create/unlink`, and `_execute_actions()`
parses an LLM reply and runs what it finds —

```python
if act.get("type") == "create_task":
    t = self.env["project.task"].create(vals)
```

— with no `has_group`, no `AccessError`, no approval and no dry-run anywhere in
the file. Its own source is annotated
`# sudo: REVIEW-05 imported from the server as found; reason not yet recorded`.

This contradicts the control model the brief specifies — external messages as
drafts, authorized approvers, no automatic acceptance. Narrowing that ACL is
Stage 0 of the implementation plan and depends on nothing else.
