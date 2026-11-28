# 07. Next build list

27 Nov 2026. Decided by the owner (Muhammad) on 27 Nov 2026. Every item that touches live needs its own staging
test and its own approval; nothing here is installed or applied until then.

## Decisions this list rests on

- **Option 1 (keeps D1).** The standard Sales Project flow creates the oversight project (Consultants).
  `c2p_order_projects` is the only creator of the delivery project (Solutions).
- **T01 product setup rule.** The standard template link ("Project Template") is the **Consultants oversight template**.
  The delivery template goes in the product's own **Delivery Project Template** field. The delivery template is never
  linked as the standard template.
- Order: history fix first, then the forecast API bypass, then the T01 templates. `c2p_task_change_reason` is last;
  Muhammad will send its code as text.

## The list, in order

| # | Item | Where | Needs a live change? | Status |
|---|---|---|---|---|
| 0 | **Guard: no delivery project when the order has another project line.** The module posts a note on the order instead. Setup rule written into the module description. 26 tests. | `c2p_order_projects` | No: the module is not installed yet | Built, in a pull request |
| 1 | **Milestone-history fix.** Create-only access to the history for the project user group (no write, no delete, no `sudo()`); the history rule also admits the paired delivery company, so Solutions members and leads can read paired-engagement history; rows can be created only through the tracker's own code path (an internal marker held in memory, not a context flag), so a forged API create or import is refused. Tests: date change and stage change by a member, a lead and a plain project user; edit and delete refused; an unrelated company sees nothing; forged create and import refused. | `c2p_project_tracker` | **Yes:** an upgrade on live (tracker 19.0.1.0.1 to 19.0.1.0.2). Own staging test and approval. | Built, in a pull request. 6 new tests; the tracker's 63 and the 200 across six C2P modules pass. Staging test and approval still to come. |
| 2 | **Forecast API bypass.** Close the skip key (`c2p_skip_change_reason`) and the internal key (`c2p_forecast_internal`) as sent over the API, using the same internal marker, so only the module's own code can use them. Genuine screen saves, the install, and system-level writes are unchanged. Trusted in-process callers need one helper that sets the marker. Tests: an API write with either key is refused; screen saves unaffected. | `c2p_milestone_forecast` | **Yes:** an upgrade on live (forecast 19.0.1.0.0 to 19.0.1.0.1). Own staging test and approval, together with item 1. | Built, in the same pull request as item 1. 21 module tests pass. Staging test and approval still to come. |
| 3 | **T01 oversight template (Consultants).** Five portfolio stages (Not Started, In Progress, Blocked, Client Review, Done) and gate tasks M1 Kickoff, M2 Client acceptance, M3 Closure. | A one-time admin action that creates it in the configured company; no database-specific ids | Yes, data on live; own approval | Not built |
| 4 | **T01 delivery template (Solutions).** Six stages (Backlog, To Do, In Progress, Waiting on Client, Review, Done), Task Dependencies on, gates G1, G2, G3, and seven tasks (below). Checklists are plain lists in the task descriptions; "Plan: D+n" and the role placeholder are the first line of each description, never in the title. | Same admin action | Yes, data on live; the Task Dependencies setting must be switched on first (approval) | Not built |
| 5 | **Guided setup (replaces the old items 5 and 7).** When the pair is made the module also: links M<n> to G<n> by number; sets the engagement type from the product (new product field); fills empty task deadlines from "Plan: D+n" in the first description line, counted from the order date, and gives each gate the latest date of its tasks; starts the onboarding checklist when that module is installed; and posts one note on the delivery project saying where to start and in what order. The team follows the defined T01 process and marks tasks done. 6 tests; 32 in all, 0 failed. | `c2p_order_projects` | No, with the module | Built, in the pull request |
| 6 | **Engagement-type list T01 to T05** replaces the tracker's five types and the proposal's seven domains; Shafat chooses T01 or T02 for each existing ERP engagement by hand. Consulting and Other get no template. | `c2p_project_tracker`, `c2p_proposal` | Yes: a conversion on live; own approval | Decided; not built |
| 7 | **Development requests from Odoo (owner request, 27 Nov 2026).** The outsourced team has no Claude access, so development work is requested, specified and tracked in Odoo projects and tasks; Claude does the work from those tasks. Shape to be decided. | A project template and a task flow | Yes, data on live; own approval | Proposed; waiting for the owner's answer |
| 8 | **`c2p_task_change_reason`.** Reviewed last, against `c2p_master_agent` (line 211 reassigns tasks as the logged-in user and would be refused) and the tracker's deadline sync. It very likely has the same skip-key gap as item 2. | New module | Yes | Waiting for the code as text from Muhammad |

## T01 delivery template content (item 4)

Gates are milestones: G1 holds R01, G2 holds R02 to R06, G3 holds R07. A task starts after the ones named. Roles are
placeholders, not people.

| Task | Role (placeholder) | After | Plan | Checklist | Evidence | Gate |
|---|---|---|---|---|---|---|
| R01 Initiation: Kickoff | Consultants Lead | none | D+2 | contact, apps, scope, access owner | brief, MoM | G1, Consultants |
| R02 Discovery: Confirm requirements | Functional | R01 | D+5 | critical flows, exclusions, data needs | requirements checklist | client approver |
| R03 Configure: Environment and setup | Solutions Lead | R02 | D+10 | environment verified, roles, standard setup | setup record | internal review |
| R04 Testing: Data and process tests | Functional + QA | R03 | D+14 | master data, end-to-end, exceptions | test results | QA |
| R05 Testing: User walkthrough | Functional | R04 | D+16 | demo, notes, open questions | walkthrough note | none |
| R06 Deploy: Acceptance and readiness | PM | R04, R05 | D+18 | defects, access, backup owner | readiness record | G2, Client |
| R07 Closure: Hypercare and handover | Support | R06 | D+25 | open issues, support owner | handover note | G3, Closure |

Handover documents for every type: delivered scope list, approvals list, open items, support arrangements, access list.

## What the 'Set up engagement' button reduces to (tested 27 Nov 2026, stock Odoo 19, fictional data)

With the module switched on and a T01 oversight template that carries the five stages and the three gate tasks:

| Already done by the module and the templates | Still to do |
|---|---|
| Both layers set (oversight is portfolio, delivery is delivery); counterpart set both ways | Link M1, M2, M3 to G1, G2, G3: the gate tasks are recognised as milestones but **not linked**, so they do not follow the delivery dates and the engagement shows amber ("3 open milestones have no deadline") |
| The five portfolio stages and the three gate tasks, copied from the template | Set the engagement type (the list today is ERP, Custom, Support, Consulting, Other; T01 to T05 is item 6) |
| After linking and dating the gates: gate dates follow, status goes green | Start the onboarding checklist: the existing action works and makes the 9 items |

So the button is **not** only "set type and layer": the layer is already set. It reduces to **linking the gates and setting the type**,
plus the existing onboarding action. Item 5 moves the gate linking into the module, after which only the type (and the onboarding start) is manual,
and the type can later come from the product.

## Outside the code list

- Cutover of `c2p_order_projects` and the edits to the live automations: after the staging runbook results are in
  (`05-ORDER-PROJECTS-CUTOVER.md`, `06-ORDER-PROJECTS-STAGING-RUNBOOK.md`).
- Server items: the failing 03:00 backup job (empty 20-byte files, `/opt/mumtaz/.env.production` missing; real backups are
  elsewhere; disabling it needs approval), `odoo3` database pinning, an off-server backup copy, the pending security updates and restart.

## Milestone-history fix: what changed (item 1)

- **The defect (reproduced first):** a Delivery Member who moved a task made the sync try to log history; the create was refused and the whole save failed. 5 of the 6 new tests failed on the old code.
- **Create-only access** for the project user group (no read, write or delete) on the history model.
- **Company rule:** a new stored field on each row, the paired delivery company, is admitted by the history rule. Solutions members can log and read the history of their own paired engagement, and nothing else. An unpaired engagement stays hidden; an unrelated company sees nothing.
- **Internal marker:** rows can be created only inside the tracker's own `log()`, using an in-process marker that cannot be sent over the API. A direct create, an import or an API call is refused for every user, managers included. The install and system code are exempt.
- **Behaviour change to know about:** Portfolio Managers can no longer create history rows by hand. Their write and delete access is unchanged; I have not touched it.
- **Staging:** the upgrade adds one column and fills it for existing rows. The staging runbook step is to upgrade the copy, read the row count and the new column, move a task as a Solutions member, then check the same on the copy before any live approval.

## Forecast API bypass fix: what changed (item 2)

- **The hole (read from the code):** the reason-for-change rule honoured four context keys (`c2p_skip_change_reason`, `install_mode`, `module`, and the internal `c2p_forecast_internal`). A context is chosen by whoever calls the API, so any login could move a commitment date with no reason, or write a milestone's health colour by hand, by sending one of those keys.
- **The fix:** no context key bypasses anything now. The switches are in-process variables that only Python code importing the module can set. Trusted bulk code uses `with skip_change_reason():`. The superuser (which also runs the install) stays exempt.
- **Tests:** 21 pass. New ones prove that each of the four keys is refused for a project manager, that the health cannot be set or forged at create through a key, that the in-process skip works and ends with its block.
- **Staging check for this one (read-only query on the copy and on live before approval):** search the live database's automations and server actions for the three key names. If any live automation sends one, it would start being refused. In this repository nothing does.

## Staging for items 1 and 2

One combined pass, with the steps in `08-TRACKER-FORECAST-STAGING-RUNBOOK.md`: three read-only queries on live, one `pg_dump`, then everything on a neutralised copy (upgrade with both modules' tests, data checks, and a 16-check scenario on fictional data). The scenario was rehearsed on a local stand-in; it has not run on live data.
