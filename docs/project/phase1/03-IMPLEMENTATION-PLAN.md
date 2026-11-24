# Staged implementation plan

No dates. Stage order is driven by dependency and by risk, and three of the
stages cannot be sized until the live audit answers the questions in
`00-README.md`. A plan with invented durations would read better and be worth
less.

Every stage lists its entry condition, what it delivers, and how it is proven.
Nothing in any stage touches production until it has run on a restored copy.

---

## Stage 0 — Close the open control. No dependencies.

Entry: none. This stage depends on nothing and should not wait for the audit.

| # | Item | Why now |
|---|---|---|
| 0.1 | Narrow `c2p_master_agent`'s ACL off `base.group_user` and gate `_execute_actions()` behind an explicit group check | Today, every internal employee can have an LLM reply create and assign `project.task` records, with no approval, no dry-run and no tests. It contradicts the control model this whole brief specifies |
| 0.2 | Decide whether the agent's action executor survives at all, or becomes propose-only | A propose-only agent loses nothing the brief asks for and removes the risk class entirely |
| 0.3 | Close the production exposure: firewall the Odoo application ports, rotate the default-strength admin credential | Reported in four prior sessions, unremediated. Every control below is theatre until this is done |

**Proof:** the ACL CSV shows a restricted group; a test asserts a non-member is
refused by the server; a firewall listing and a refused external connection.

---

## Stage 1 — The live audit. Blocks Stages 3 onward.

Entry: a dedicated read-only Odoo user exists.

Run, on the VPS:

```bash
cd /opt/mumtaz/c2p-delivery-system
export ODOO_URL=http://127.0.0.1:8069 ODOO_USER=<readonly-user>
read -rs ODOO_PASSWORD && export ODOO_PASSWORD
python3 scripts/inspect_odoo_db.py <DB> --pm-audit --json > /tmp/pm_audit.json
```

Read-only throughout: `search_read`, `search_count`, `read_group`, `fields_get`.
Nothing is written.

**Delivers:** answers to all eight live questions, committed as
`docs/project/INSTALLED_BASELINE.md`.

**The one that matters most** is the automation inventory. Phase 1 proved that
**no code creates a project**, so every creation path is standard
`sale_project` behaviour or a database automation. Until those are listed with
their triggers, any new onboarding action risks being the second thing that
creates a project — which is precisely the duplicate the brief is trying to
prevent.

**Proof:** the JSON, plus a written reconciliation of its findings against this
fit-gap, naming anything that contradicts it.

---

## Stage 2 — Decisions. Blocks Stages 3 and 4.

Entry: Stage 1 complete.

| Ref | Decision | Blocks |
|---|---|---|
| D-1 | Task stage naming: option A (rename live stages) or **B (keep names, add `Ready`)** — `01-FIT-GAP.md` §3 | the whole task workflow |
| D-2 | Which milestone notion is canonical — `01-FIT-GAP.md` §5 | deliverables, acceptance, baselines |
| D-3 | Retire the earlier "health stored on Solutions" decision, which the code and this brief both contradict | the engagement view |
| D-4 | R0–R7 gate definitions, which exist in no file in this repository | every release approval |
| D-5 | Does the delivery system keep write access to client production databases | automation design |

D-1 deserves a sentence of warning: because the tracker matches stages by
lower-cased name, option A is a behaviour change disguised as a rename. If it is
chosen, stages, constants and tests move in one release, rehearsed on a restored
copy.

---

## Stage 3 — The onboarding gate and the engagement view

Entry: Stages 1 and 2. **Reuses** the existing portfolio/delivery pairing; adds
no engagement model.

| # | Item |
|---|---|
| 3.1 | Onboarding readiness record: the checklist in `02-WORKFLOW.md` §3, with a named authorized approver |
| 3.2 | One idempotent `action_start_onboarding()` — creates or links the pair, generates milestones from recorded deliverables, creates handoff activities, **drafts** the welcome email and data request, schedules kickoff, creates the draft charter |
| 3.3 | Consultants engagement view over the portfolio project: client, owners, contract and scope version, dates, value, payment schedule, linked delivery project, milestone acceptance, risks, changes, next client action, stored RAG |
| 3.4 | Health provenance: calculation timestamp, input version, freshness, override expiry |

**Idempotency is a database guarantee, not a Python check.** The existing
`UNIQUE(c2p_counterpart_id)` covers the project pair; the same pattern —
a unique reference stamped on the created record — covers the welcome email, the
data request and the milestone set, exactly as `c2p_meeting_actions` already
does for task creation.

**Proof:** a test that runs the onboarding action twice, concurrently, and
asserts one engagement, one delivery project, one milestone set, one draft email.

---

## Stage 4 — Deliverables, milestones, acceptance

Entry: Stage 3, decision D-2.

| # | Item |
|---|---|
| 4.1 | `c2p.deliverable`: description, acceptance criteria and method, baseline/forecast, internal reviewer, client approver, milestone, tasks, evidence, commercial linkage, status |
| 4.2 | Milestones generated from deliverables, tailorable by the PM before baseline approval |
| 4.3 | Reusable task packs: ERP, custom development, website/ecommerce, AI/automation, consulting — editable before baseline |
| 4.4 | Acceptance record with four outcomes: accepted / with comments / partial / rejected–rework |
| 4.5 | Billing eligibility as a reviewable flag. No invoice action, ever |

**Proof:** tests that a milestone with all tasks Done is **not** accepted; that
acceptance requires a named client approver; that billing eligibility is a flag
and posts nothing; that an outsourced contributor cannot approve their own
deliverable.

---

## Stage 5 — Outsourced work packages

Entry: Stage 4.

Scope, deliverables, acceptance criteria, dates, **restricted** commercial
terms, time-bounded access, NDA and security requirements, owner, review cycle,
escalation contact, revision and defect tracking, performance record.

**Proof — all negative tests, because this is a confidentiality boundary:** a
partner user cannot read another work package, cannot read commercial terms
outside their own, cannot read internal discussion, cannot reach another client,
holds no administrator right, has no cross-company visibility, and loses access
when the period expires.

---

## Stage 6 — Documents

Entry: Stage 4. Templates are written and in `templates/`.

| # | Item |
|---|---|
| 6.1 | Render the pack as QWeb reports **inheriting `c2p_proposal`'s layout and fonts**, so the client sees one identity |
| 6.2 | Document register on the engagement: ID, version, status, approval history, authoritative copy |
| 6.3 | Draft-from-data, prompting the PM for what is missing rather than filling it in |
| 6.4 | Client-safe variants where the template defines one (minutes, closure) |
| 6.5 | Configurable data-request workbook built from the project type's tabs |

**Proof:** render each document from a seeded sample project; assert no `<...>`
placeholder survives into an approved document; assert the client-safe minutes
contain no restricted field.

---

## Stage 7 — Automations

Entry: Stage 1 (the inventory), Stages 3–6.

Register first, then build. Every entry carries trigger, conditions, actor,
output, duplicate guard, exception path, audit log.

Onboarding preparation · missing-data reminders to the **named tab owner** ·
kickoff and MoM action capture · task due and blocked alerts · weekly PM update
request · milestone approaching and late · QA handoff · client acceptance
request · approved-milestone notice to Consultants for billing review · change
approval · closure.

Three rules: internal notifications and external messages are different things;
**every external message is a draft until an authorized Consultants user
approves and sends it**; and no automation posts an invoice or records client
acceptance.

**Proof:** replay each trigger twice and assert single effect; assert no
automation can send externally; reconcile the register against the live
inventory so no second automation exists for a process already handled.

---

## Stage 8 — Dashboards

Entry: Stage 7.

Consultants: portfolio health, contracted vs accepted milestones, forecast
delay, decisions awaiting client, open change requests, upcoming billing
eligibility, client communication and next action.

Solutions: tasks due and overdue, blocked work, milestone forecast, owner
capacity, subcontractor performance, QA failures, defects, missing evidence,
MoM actions.

Both read the **same stored RAG**. Every red and amber states why, names an
owner and gives the next action — a colour without those three is ignored within
a fortnight.

**Proof:** a test that each tile's value equals the result of its own
drill-down domain. That single test prevents the entire class of bug where a
dashboard quietly stops agreeing with the records.

---

## Stage 9 — End-to-end demonstration

Entry: Stages 3–8 on staging.

One sample project, synthetic data only, from signed scope through onboarding,
task delivery, QA, client acceptance and closure. Reported with: record IDs,
automation traces, test command and verbatim output, limitations, and anything
that behaved differently from this plan.

---

## Stage 10 — Production readiness

Backup and verified **restore** first — the repository has a nightly backup job
and no evidence a restore has ever been attempted, which makes every other
recovery control an assumption. Then security tests against multiple real roles
rather than the administrator, data-quality review, reconciliation, UAT, the
deployment and rollback runbook, training, hypercare.

Rollout follows the R0–R7 framework. Those gates are **decision D-4** — their
definitions are in no file in this repository, and nothing here infers them.

---

## Standing constraints

- Preserve live projects, sales orders, invoices, messages and historical task
  data.
- Do not alter posted accounting, and do not touch the existing intercompany
  invoice rule as part of this work.
- Reuse `project.project`, `project.task`, `project.milestone`. No competing
  project or task record.
- No production write, module install, permission change, CRM cleanup, outreach,
  schedule change or deployment without the applicable approval.
- Tests are reported as run with their output, or as **NOT RUN** with the
  reason. There is no third option.
