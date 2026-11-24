# Client master record, onboarding and plan control — demonstration

Run on 24 Nov 2026 in an isolated development container. **Fictional data
only.** Nothing was installed on, deployed to or read from staging or
production.

| | |
|---|---|
| Odoo | 19.0 Community (`base 19.0.1.3`, `project 19.0.1.4`), PostgreSQL 16 |
| Modules | `c2p_project_tracker 19.0.1.0.1`, `c2p_work_hub 19.0.1.0.1`, `c2p_meeting_actions 19.0.1.0.0`, `c2p_client_onboarding 19.0.1.0.0`, `c2p_plan_control 19.0.1.0.0` |
| Tests | `0 failed, 0 error(s) of 160 tests` across the six C2P modules on a fresh database |
| Companies | C2P Consultants (demo), C2P Solutions (demo) |
| People | Layla (Consultants consultant), Shafat (delivery owner), Muhammad (portfolio owner), Omar (outsourced) — all invented |
| Clients | Northwind Trading, Contoso Foods — both invented |

How each step was performed: every state change was made **as the named user**,
through that user's own session and access rights. The quick task update, the
plan-change proposal, both of Shafat's decisions and the welcome-email draft
were clicked in the browser. The other changes were sent through the same
session's RPC endpoint, which runs the same server rules, to keep the script
reliable. Screens are unedited.

## The journey

| # | Screen | What it shows |
|---|---|---|
| 01 | `01-consultant-client-overview-before` | Existing client and engagement, nothing typed twice. Banner: "Start the onboarding checklist" |
| 02 | `02-engagement-scope-and-onboarding-checklist` | Scope approved by Muhammad; nine checks with owner, due date, what a gap blocks, evidence; 67% |
| 03 | `03-client-overview-next-action-banner` | Next required action names the open item, its owner, date and what it blocks |
| 04 | `04-access-register-vault-reference-only` | Access held by Shafat, vault reference, expiry. No secret |
| 05 | `05-welcome-email-draft-for-review` | Draft built from approved scope; recipient and text editable; nothing sent |
| 06 | `06-shafat-missing-client-data` | Open onboarding items that block kickoff or delivery, by client |
| 07–09 | `07…09-omar-…` | Outsourced contributor: own work only; quick update in one panel |
| 10a, 10 | `10a…`, `10-omar-proposes-date-change` | Proposal form prefilled from the task; submitted |
| 11–12 | `11…`, `12-shafat-approved-date-change-original-kept` | Shafat's queue; approved — previous value, new value, original baseline, reason, who and when |
| 13–14 | `13…`, `14-scope-change-sent-to-consultants` | Scope change cannot be approved by delivery; becomes one Consultants change request |
| 15–16 | `15-plan-change-audit-history`, `16-task-…` | Audit history; acceptance criteria and changes on the task |
| 17–18 | `17-minutes-decisions`, `18-minutes-action-linked-to-one-task` | Minutes; the action item linked to exactly one task after three conversion attempts |
| 19–20 | `19-shafat-…`, `20-shafat-delivery-dashboard` | Shafat's work and review queue; delivery dashboard |
| 21–22 | `21-omar-…`, `22-omar-my-proposed-changes` | Omar's views afterwards |
| 23–25 | `23-muhammad-portfolio-dashboard`, `24-…decisions-awaiting`, `25-client-list-…` | Portfolio owner's views |
| 26 | `26-consultant-client-overview-final` | The whole Client Overview on one page |

## What the system refused (verbatim)

- Consultant approving scope — *Only a Portfolio Manager can approve scope or confirm onboarding.*
- Ticking the confidentiality check without the NDA — *…the NDA / confidentiality document must be received, verified or marked not applicable.*
- Ticking deliverables with no evidence — *…write where the evidence is in the note.*
- A password typed as a vault reference — *A vault reference says where the credential is kept, in the form vault://collection/item. It is never the credential itself.*
- `password: …` typed into Purpose — *Purpose looks like it contains a password, key or token…*
- Omar reading the access register, instances, documents or checklist — access denied on all four.
- Omar changing a committed due date — *…is part of the approved plan. You cannot change its date, assignee, milestone or acceptance criteria directly: use Propose Plan Change…*
- Omar approving his own proposal — *Only the delivery owner can decide a plan change.*
- Shafat approving the scope change — *PC-0002 changes scope, price or a contractual commitment. The delivery owner cannot approve it: send it to Consultants.*
- Sending the same scope change twice — *PC-0002 has already been decided.* One change request exists.
- Layla approving the meeting action — *Only a meeting approver can approve or reject action items.*

Omar's session listed one project (Northwind delivery) and tasks from that
project only. Contoso was not visible to him.

## Clicks and fields for the common actions

Counted from the screen each user starts on.

| Action | Clicks | Fields typed |
|---|---|---|
| Quick task update (My Work Today) | 2 | 2 (what happened, next action) |
| Submit a task for review | 1 | 0 |
| Mark a checklist item done, fact already in Odoo | 1 | 0 |
| Mark a checklist item done, needs evidence | 2 | 1 |
| Mark a checklist item not applicable | 2 | 1 (reason) |
| Add an instance (on the Client Overview) | 2 + save | 6; Solutions project prefilled |
| Record an access with a vault reference | 2 + Grant | 5 |
| Propose a date change from a task | 3 | 2 (date, reason); task and current date prefilled |
| Decide a proposed change | 2 | 0 (a rejection needs 1: the note) |
| Send a scope change to Consultants | 2 | 0 |
| Draft the welcome email | 1 to draft, 1 to send | 0 |
| Minutes with one decision and one action | about 8 | 6 |

## Defects the demonstration found in code already on `main`, fixed here

1. **My Work Today hid every task** for any user with an upcoming milestone
   (`c2p_work_hub`, a `t-else` bound to the wrong `t-if`).
2. **The delivery dashboard never opened** for anyone (`c2p_project_tracker`,
   a getter named `load` replaced the `load()` method).

Neither is caught by the Python tests, because both are in the browser code.

## Still awkward

- Shafat's exceptions are on four screens (delivery dashboard, Proposed
  changes, Missing client data, review queue in My Work Today), not one.
- Muhammad's dashboard does not yet list the waiting change request or
  engagements ready to confirm; those are on "Decisions awaiting me". It has
  no "Shafat's next action" line.
- My Work Today repeats a task in every section it qualifies for, and shows
  Odoo's private "Welcome" to-do.
- Checklist and engagement columns truncate at normal widths.
- Marking a checklist item not applicable means typing the reason in the row
  and then pressing N/A; there is no prompt.
- Milestones on the Client Overview show only for projects the viewer can
  open. A Consultants user sees them once invited to the Solutions project.
- The plan-change form shows the date picker over the Reason field until it
  is dismissed.
- Only the welcome email is drafted. The other documents in
  `docs/project/phase1/templates/` are not generated yet.
- Deliverables, acceptance method and payment milestones have no records
  behind them yet, so those three checks rely on a written evidence note.
