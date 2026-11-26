# 04. How a confirmed sale order creates projects in Mumtaz_C2P

Read-only report, 26 Nov 2026. Repository `Core2Plus-odoo/Mumtaz`, `main` at `2af0185`.
Status: **draft for approval. Nothing was built, installed, deployed or changed.**
Decisions D1 to D4 were made by the owner on 26 Nov 2026 and are recorded in sections G, H, I and J. The read-only queries of Appendix A were run by the owner on 26 Nov 2026 at 10:36 UTC; their results are folded into this report and tagged **[REPORTED 26 Nov]**. Approval to build is still open.

## How to read this report

Every statement is tagged.

| Tag | Meaning |
|---|---|
| **[VERIFIED]** | Read by me in this repository, in the stock Odoo 19 source, or reproduced in a local throwaway database with fictional data (called a "rehearsal"; it proves a mechanism, not live data). |
| **[REPORTED]** | Taken from the owner's own psql output pasted into this session on 25 Nov 2026 (14:58 and 18:00 UTC), or from the task statement. I did not read it myself and have not re-read it today. |
| **[UNKNOWN]** | Not seen anywhere. Appendix A has a read-only query that would settle it. |

Sources and limits:
- I have **no access to the VPS or the database**. "Code in the database" means the `ir_act_server.code` text the owner pasted. Line numbers below count that pasted text from 1.
- Stock Odoo 19 paths are quoted from a scratch checkout, not from this repository.
- Client names are left out on purpose: this repository is public. Projects are referred to by id.
- **Correction to my 25 Nov reading.** I said no rule 11 clone exists on live because only project 9 matched an order-number name. That query assumed order names like `S00131`. Project names on live carry references such as `C2P-…-2709-00…`, so rule 11 clones named after other order numbers would have been missed. **Resolved on 26 Nov: rule 11 creates nothing on live, because the templates it copies (581 to 587) do not exist in the database.**
- Numbering: your list items 2 and 3 are database automation rules **11** and **19**.

## Summary

1. **On paper three paths can create projects for one won deal; on live only two exist.** Path 2 (rule 11) is inert: it sets a flag and copies nothing, because templates 581 to 587 do not exist. **[REPORTED 26 Nov]**
2. **The full chain "won lead → confirm → Solutions project" has not run in its current form.** Only one order on live went through rule 19 (lead 56180, order S00022, project 27), and that was at 14:38 on 16 Nov, before action 919 and template 28 existed. **[REPORTED 26 Nov]**
3. **The Solutions projects 34 to 37 were made by hand-runs of action 919**, 14:50 to 15:04 on 16 Nov, two runs per billing project. Four earlier Solutions projects (ids 29, 31, 32, 33) no longer exist; who deleted them is unknown. **[REPORTED 26 Nov; deletion UNKNOWN]**
4. **Only one of the four Consultants projects came from an order.** Projects 23, 25 and 30 have no sale order line; only project 27 does (order 22). The earlier belief that all four came from the standard product path was wrong. **[REPORTED 26 Nov]**
5. **The Solutions project is only created by action 919, and the only caller in code is action 766 (rule 19, which fires only when a lead's stage is id 4).** A quotation confirmed by hand, or any order not coming from a won lead, gets no Solutions project. **[VERIFIED by code; filter REPORTED 26 Nov]**
6. **The two projects are linked by custom database fields** (`x_billing_project_id`, `x_delivery_project_id`) that exist in no repository file; the tracker's pairing and layers are empty. **[VERIFIED absent from repo]**
7. **The accepted proposal has no record of its own**: it is the confirmed `sale.order`. Only one Proposal Maker order exists on live. **[VERIFIED + REPORTED 26 Nov]**
8. **Each deal currently produces four to-dos for the owner** (a kickoff and a portal to-do on each of the two projects). **[REPORTED 26 Nov]**
9. **Hard-coded ids** (templates 26, 28, 581 to 587; companies 1 and 4; users 2, 20, 26) sit inside the live actions. **[REPORTED]**

## 1. Map of the paths

| # | Path | Trigger | Creates | Company | Links the two projects? |
|---|---|---|---|---|---|
| 1 | Product 97 "Odoo Implementation — Milestone…", tracking `project_only` (standard `sale_project`) | Order confirmation | Consultants "billing" project | The order's company | No |
| 2 | Rule 11 → action 747 "Clone project template(s) on order confirmation" | `sale.order` moves into confirmed | **Nothing on live**: it sets `x_project_created` and finds no template (ids 581 to 587 do not exist) | n/a | No |
| 3 | Rule 19 → action 766 → action 919 | `crm.lead` create or write, stage is Won | Confirms the quotation (path 1 fires), then the Solutions project | Consultants (company 1) and Solutions (company 4) | Yes, two custom fields |
| 4 | Delivery API write-back (`sync.py:51-57`) | "project" stage in the Agency OS | Bare project and tasks | Not set | No |

Not creators: `c2p_project_tracker` and `c2p_proposal` (sections C and E), `c2p_master_agent` (creates tasks only, `master_agent.py:213-219`). **[VERIFIED]**

## A. What rules 11 and 19 do

### A1. Rule 11 / action 747 (path 2)

| Item | Finding | Tag |
|---|---|---|
| Rule state, trigger, model | Active; `on_create_or_write` on `sale.order` | REPORTED |
| Filter and pre-filter | Filter `state = 'sale'`, pre-filter `state != 'sale'`: it fires once, when an order moves into confirmed | REPORTED 26 Nov |
| Guard | Skips unless `order.state == 'sale'`, `x_project_created` is false and the order has a customer (L13) | REPORTED |
| Writes | `sale.order.x_project_created = True` **before** copying (L15); chatter on the order (L33-34) | REPORTED |
| Template choice | Lower-cased product names matched to keywords: template **581** for "odoo erp", "odoo implementation", "odoo version upgrade"; 582–587 for other keyword sets; skips "retainer" and "booking fee" (L1-24) | REPORTED |
| Creation | `template.copy({'name': '<order> - <template name>', 'partner_id': customer})` (L31) | REPORTED |
| Templates | Projects 581 to 587 **do not exist** in Mumtaz_C2P (the lookup of ids 26, 28, 581 to 587 returned only 26 and 28, archived rows included). `template.exists()` is false (L28), so no copy is made and no chatter line is posted. The ids look copied from another database. | REPORTED 26 Nov |
| Template flag | A plain copy of a template project **keeps `is_template = True`** (`project/models/project_project.py:477-478`). The rehearsal produced a template-flagged clone. | VERIFIED (stock); live not seen |
| Links the two projects | No: nothing is written that points at another project | REPORTED code |
| Re-confirmation | Stock Odoo refuses to confirm an order not in draft or sent (`sale/models/sale_order.py:1209-1213`). The rule also fires on any later write; the `x_project_created` flag (L13) stops a second clone. | VERIFIED + REPORTED |
| Project already exists | Not checked. Only the flag decides. A copied order that inherits the flag would never clone. | REPORTED code; flag definition UNKNOWN |
| Effect on live | Only side effect: `x_project_created = True` on each confirmed order. No project is created. | REPORTED 26 Nov |

### A2. Rule 19 / action 766, then 919 and 920 (path 3)

| Item | Finding | Tag |
|---|---|---|
| Rule state, trigger, model | Active; `on_create_or_write` on `crm.lead` | REPORTED |
| Filter | `stage_id = 4`, no pre-filter: fires on every create or write of a lead in stage 4, not only on the first move | REPORTED 26 Nov |
| Gate | Acts only when `lead.stage_id.is_won` (L4) | REPORTED |
| Branch 1: exactly one open (draft or sent) quotation and none confirmed (L8-17) | Runs `action_confirm()` as sudo (L10), which fires path 1. Renames any resulting project whose name contains "TEMPLATE" to the lead name (L11-13). Runs **action 919** on the new projects (L14). Posts chatter on the lead (L16). | REPORTED |
| Branch 2: more than one open quotation (L18-21) | Schedules a to-do only; creates nothing | REPORTED |
| Branch 3: a confirmed order already exists (L22-23) | Skips | REPORTED |
| Branch 4: no quotation (L24-44) | Looks for `[OPP:<id>]` in project descriptions (L25), otherwise copies **template 26** with company 1 and user 26, description built from the lead text with money words removed (L37-43). **Does not run 919**, so no Solutions project. | REPORTED |
| Action 919 template and company | Copies **template 28** `with_company(4)` into company **4** (C2P Solutions) (L2, L6-9) | REPORTED |
| 919 name, partner, owner | `<billing project name> – Delivery`; partner of the billing project; owner of the billing project, or user 26 (L7-8) | REPORTED |
| 919 link | Writes `x_billing_project_id = billing id` on the new project (L9) and `x_delivery_project_id = new id` on the billing project (L14) | REPORTED |
| 919 milestones | Creates a milestone on the delivery project for every milestone of the billing project, with `x_billing_milestone_id` (L11-13) | REPORTED |
| Action 920 (rule 30) | When a delivery milestone is reached it marks the linked billing milestone reached and schedules an "Invoice milestone" to-do for user 2 | REPORTED |
| Re-run guard | 919 skips if the billing project already has a delivery link or is a template (L4); 766 skips once a confirmed order exists (L22) | REPORTED |
| **Gap** | If the single quotation is confirmed **by hand first**, 766 sees a confirmed order (L22) and 919 never runs. The billing project then has **no Solutions project**. | VERIFIED by code logic |
| **Gap: archived** | The no-quotation branch looks for the `[OPP:<id>]` marker with the default search, which ignores archived projects (L25). An archived project would not be found and a duplicate could be created. | VERIFIED by reading; not rehearsed |
| Tracker pairing | 919 sets the custom `x_` fields only. It sets no tracker layer and no `c2p_counterpart_id`. | REPORTED code |
| Has this chain run? | Only once, and in an older form: lead 56180 / order S00022 at 14:38 on 16 Nov, before template 28 (created 14:46) and action 919 existed. No later project with `x_` links exists. | REPORTED 26 Nov |

### A3. Path 1 (product 97)

| Item | Finding | Tag |
|---|---|---|
| Tracking | `project_only` | REPORTED 26 Nov |
| Template link | `project_template_id = {"1": 26}`: template **26** for company 1 only. Project 26 is "TEMPLATE · Billing overview (C2P Consultants)", company 1, template, active. Project 28 is "TEMPLATE · Odoo Implementation delivery (C2P Solutions)", company 4, template, active. | REPORTED 26 Nov |
| Behaviour | One project per order per template; a template flagged `is_template` is built with `action_create_from_template`, otherwise `copy` (`sale_project/models/sale_order_line.py:196-208`, one-per-order test at 358-375). Company is the order's company; the customer is the order's customer. | VERIFIED (stock) |

## B. Which path created projects 34, 35, 36, 37 and 23, 25, 27, 30

Evidence from the owner's queries of 26 Nov 10:36 UTC. All rows are **[REPORTED 26 Nov]**.

| Evidence | What it shows |
|---|---|
| Creator | Every project in the window, both templates and an AI-agents board included, was created by **user id 42**, not OdooBot. Who or what user 42 is: **UNKNOWN**. |
| Consultants projects | 23 (25 Oct), 24 (30 Oct, archived duplicate of 27's client), 25 (9 Nov), 27 (16 Nov 14:36), 30 (16 Nov 14:51). |
| Templates | Template 26 created 16 Nov 14:34; template 28 created 16 Nov 14:46. |
| Solutions projects | 34 (14:58), 35 (14:59), 36 (15:01), 37 (15:03), all 16 Nov. |
| Order link | Only project **27** has a sale order line (order 22, confirmed, a Proposal Maker order). Projects **23, 25 and 30 have none**, so they did not come from confirming an order. |
| Project 27 chain | 14:36 project created from the template; 14:38 chatter "Project created from template …" and, on the lead, "Won: quotation S00022 confirmed automatically" (rule 19, older form). |
| Action 919 runs | "Delivery project created in C2P Solutions" appears **twice for each of 27, 25, 23 and 30**: 14:50, 14:52, 14:54, 14:57 and again 14:59, 15:01, 15:03, 15:04. |
| Missing ids | Ids 29, 31, 32, 33 fall in the same window and do not exist now (the window query had no active filter). Consistent with a first set of four Solutions projects, later deleted. The second run could only happen because the first set's links were cleared. |

Conclusions:
- Solutions projects 34 to 37 were created by action 919 (**the only code that writes the `x_` links**), run **twice per billing project by hand or script as user 42**, not by an order confirmation. **[REPORTED; run mode inferred]**
- Consultants projects 23, 25 and 30 were not created by path 1 (no order line); how they were created is **UNKNOWN** (likely by user 42's script or a manual copy of template 26). Project 27 came through path 1 and rule 19.
- Who deleted ids 29, 31, 32 and 33, and when: **UNKNOWN**. The Duplicate Cleanup job keeps the **lowest** id of a group, so it would have removed the later ids, not these; it does not explain the pattern.

## C. Are c2p_meeting_actions and c2p_milestone_forecast installed?

| Module | Merged | Installed in Mumtaz_C2P | Tag |
|---|---|---|---|
| `c2p_meeting_actions` 19.0.1.0.0 | Yes, PR #171 | Installed, version 19.0.1.0.0 (owner's output, 26 Nov 10:36 UTC) | REPORTED 26 Nov |
| `c2p_milestone_forecast` 19.0.1.0.0 | Yes, PR #205 | Installed, version 19.0.1.0.0 (owner's output, 26 Nov 10:36 UTC) | REPORTED 26 Nov |

Both are installed. The same output shows `c2p_project_tracker` 19.0.1.0.1, `c2p_work_hub` 19.0.1.0.1, `c2p_client_onboarding` 19.0.1.1.0, `c2p_proposal` 19.0.17.0.0 and `sale_project` installed. I deployed nothing. `c2p_project_tracker` creates no projects: its `create()` only mirrors the counterpart link (`project_project.py:166-176`), the install hook only classifies and pairs existing projects by hard-coded ids (`hooks.py:11-16`, `62-107`), and its hourly job writes milestone tasks only (`data/ir_cron.xml:10-12`). **[VERIFIED]**

## D. What the delivery API writes to Odoo

| Item | Finding | Tag |
|---|---|---|
| Writes | `crm.lead` create (`odoo.py:82-86`, `main.py:833`), `sale.order` quotation create (`odoo.py:88-90`, `sync.py:44-46`), `project.project` create with a name only (`odoo.py:92-93`, `sync.py:53`), `project.task` create (`odoo.py:95-98`, `sync.py:54-56`), `res.partner` create (`odoo.py:109`), chatter post (`odoo.py:111-113`), `ir.attachment` create, and unlink of a same-named attachment first (`odoo.py:115-135`): `presales.json`, `proposal.json`, `project_plan.json`, `functional.json`, `developer.json` | VERIFIED |
| What it does not do | Never confirms an order; sets no company, template, customer or sale link on the project | VERIFIED |
| When it runs | Only for an engagement with an `odoo_db` set (`sync.py:22-23`) | VERIFIED |
| Idempotency | Ids are kept in the API's own SQLite store, not in Odoo (`sync.py:5-7`, `main.py:220-226`) | VERIFIED |
| Service | Unit `delivery-api` (`deploy/setup.sh:86-89`, `deploy/delivery-api.service.tmpl`) on `127.0.0.1:8800` (`deploy/finish.sh:11`) | VERIFIED as designed |
| Is it running? | `delivery-api` is active, listening on port 8800, and its health call answers OK (26 Nov 10:36 UTC) | REPORTED 26 Nov |
| Has it written to Mumtaz_C2P? | **No trace.** No attachment named `presales.json`, `proposal.json`, `project_plan.json`, `functional.json` or `developer.json` exists in the database. Whether it created a lead, quotation or project there cannot be told from this. | REPORTED 26 Nov |
| Which Odoo database it targets | Taken from each engagement or the `C2P_CRM_DB` setting | UNKNOWN |

None of projects 23–37 can be a delivery-API project: they carry the `x_` links the API never writes. **[VERIFIED reasoning]**

## E. The accepted proposal as the engagement key

| Item | Finding | Tag |
|---|---|---|
| What a proposal is | `c2p_proposal` extends `sale.order` with `c2p_*` fields (`sale_order.py:435-475`). The Proposal Maker wizard sets `c2p_is_proposal = True` (`proposal_wizard.py:406`). There is no proposal model of its own. | VERIFIED |
| Acceptance | No state or field in the module. Acceptance is the standard order confirmation (`state = 'sale'`); standard fields `signed_by` and `signed_on` exist (`sale/models/sale_order.py:131-133`) if portal signature is used. | VERIFIED (stock); use on live **UNKNOWN** |
| Link to a project | None. `c2p_proposal` depends only on `sale_management` and `crm` (`__manifest__.py:19`) and references no project model. | VERIFIED |
| Standard link order → project | `project.sale_line_id` and `project.sale_order_id` (related) from `sale_project` (`project_project.py:28, 35` in stock) | VERIFIED (stock) |
| Tracker link | Optional manual `c2p_sale_order_id`, visible to the commercial group only, used for received amounts (`c2p_project_tracker/models/project_project.py:102-105`) | VERIFIED |
| How many proposal orders exist? | **One**, confirmed: order 22, the order behind project 27. The other three billing projects have no order. | REPORTED 26 Nov |

So the engagement key can be **the `sale.order` id**, with `c2p_is_proposal` as the "this is a proposal" marker and `state = 'sale'` as "accepted".

## F. Duplicate risks

| Risk | Finding | Tag |
|---|---|---|
| Kickoff to-do (rule 2 → action 738) | Filter: customer set. Code: for every created project with a customer it schedules a "Send kickoff email" to-do for user 2. **No guard**, no template check. | REPORTED 26 Nov |
| Portal to-do (rule 12 → action 748) | Same filter. Guarded by a per-project flag `x_portal_notified`, so once per project. | REPORTED 26 Nov |
| Result on live | Each of projects 23, 25, 27, 30, 34, 35, 36 and 37 has exactly **2** to-dos, so one deal (billing and delivery project) gives the owner **4**, including the kickoff email to the same client twice. | REPORTED 26 Nov |
| Duplicate Cleanup (job 40, action 753) | Active, **every 10 minutes**. Searches active projects with a customer, groups by (name, customer, company, template flag) and **`unlink()`s all but the lowest id** (L1-9). Permanent, cascades to tasks. It catches only exact same-name copies, not cross-path duplicates. Archived projects are not searched. | REPORTED 26 Nov |
| Weekly Status Update (job 38, action 751) | Active, weekly, next run 27 Nov 17:36. For **every active project with a customer** (billing, delivery, engagements) it creates a "Weekly Status Update" task due in 2 days, in the project's first stage and assigned to the project owner, unless one was created in the last 6 days. | REPORTED 26 Nov |
| Other jobs | "Overdue Task Reminder" (job 39) is inactive; "Project Stage: Send rating" (job 27) is active daily | REPORTED 26 Nov |
| Stage-change email, rule 10 → action 746 | Emails the client and project owner on every task stage change for tasks older than 10 minutes, with the task name in the body (age guard L5, body L11, mail L25-31). Relevant to what template task titles may contain. | REPORTED code; rehearsal VERIFIED |
| Handoff ownership flip, rule 3 → action 739 | Switches `x_owning_team` and the owner on a task change at a named stage. Not a creator. | REPORTED code |
| Hard-coded ids | Templates 26, 28, 581 to 587, company 4, users 2, 20, 26 inside the actions | REPORTED |

## G. Proposal: one creation path keyed to the accepted proposal (not built)

**Key.** The accepted proposal is the confirmed `sale.order`. Add one unique link on `project.project`: `c2p_source_order_id` (many2one to `sale.order`) and `c2p_project_role` (`oversight` or `delivery`), with a database unique index on the pair where the order is set. The pair is unique **including archived rows**, so an archived project still counts as "exists". Templates are never matched or created against an order.

**Where.** A small addon in this repository (for example `c2p_order_projects`, depending on `sale_project` and `c2p_project_tracker`), replacing the three live database actions with versioned, tested code. It overrides `sale.order._action_confirm` after the standard step, so manual confirmation, CRM won, portal acceptance and the API all pass through one place.

**What it does on confirmation**, in one transaction, for **any confirmed order that contains a product whose service tracking creates a project** (`project_only` or `task_in_project`), proposal-flagged or not (decision D3):
1. Finds the oversight and delivery projects for this order by the unique key. If both exist (archived or not), it does nothing.
2. Creates the missing one from its template with the standard template mechanism (`action_create_from_template`), in the correct company looked up by setting, not by id 1 or 4.
3. Sets the customer, the order line link, the tracker layers (portfolio and delivery) and `c2p_counterpart_id`.
4. Also fills `x_billing_project_id`, `x_delivery_project_id` and mirrors milestones with `x_billing_milestone_id`, so rule 30 / action 920 keeps working during the transition.
5. Posts one chatter note on the order.
6. The kickoff and portal to-do rules (2 and 12) are changed to skip the delivery project (the new code sets the delivery role when it creates the project), so a deal gives one kickoff and one portal to-do, not two of each.
7. Existing pairs: only 27↔34 has an order (order 22) and can be keyed to it. 23↔36, 25↔35 and 30↔37 have no order; they stay as legacy pairs with the order key empty, and the unique index applies only where the key is set.

**Decision D1: DECIDED, Option A (26 Nov 2026).** Who creates the Consultants oversight project?
- **Option A, chosen:** the standard `sale_project` keeps creating it, because it also carries the order-line link that milestone invoicing needs; the new code adds the Solutions project and the pairing in the same confirmation. For the user it is one path (confirm the order) and one transaction.
- **Option B:** the new code creates both and product tracking is set to "no". One creator, but milestone invoicing must be re-tested before any product is switched.

**Decision D2: DECIDED (26 Nov 2026).** An archived project still blocks creation: the order already has one, and an administrator unarchives it. Ignoring archived projects would have created a second project.

**Decision D3: DECIDED (26 Nov 2026).** Any confirmed order with a project-creating product qualifies, not only Proposal Maker orders. The unique key stays the order, so one order still gives exactly one pair. Consequence: small or one-off orders with such a product are paired too, so test 11 below covers a non-proposal order.

**Decision D4: DECIDED (26 Nov 2026).** The CRM "won, confirm the single quotation" step stays. Project creation moves out of it: rule 19 only confirms, and confirming runs the new path.

## H. Which existing paths to switch off, and in what order

Nothing is switched off until the new path passes the staging plan. At no point should two creators be on.

| Order | Change | Why this position |
|---|---|---|
| 0 | Install the new addon on live with its setting **off** | No behaviour change |
| 1 | Rule 11 / action 747 **off** | It is inert today (its templates do not exist), so switching it off changes nothing except removing the `x_project_created` flag write |
| 2 | In action 766 remove the call to 919 (L14) and the no-quotation branch (L24-44). Keep the "won → confirm the single quotation" step (decision D4). | After this, 919 has no caller |
| 3 | Product 97 and any T0x product: unchanged (Option A chosen) | Not needed |
| 4 | Switch the new path **on** | Single creator from here |
| 5 | Rules 2 and 12 (kickoff and portal to-dos): skip delivery projects | Four to-dos per deal become two |
| 6 | Duplicate Cleanup 753 **off** once the unique key is live | It is destructive and redundant after the key |
| 7 | Rule 30 / action 920: keep until milestone linkage moves into the module | It depends on the `x_` links |

Rollback is the reverse order: switch the new path off, then re-enable the automations. The four existing pairs (23↔36, 25↔35, 27↔34, 30↔37) are backfilled separately, with approval.

## I. Staging test plan

Same safe copy as `T01-staging-runbook`: locked copy, scheduled jobs and mail off, fictional customers only, scripts that refuse to run on any other database. Automations are loaded as on live except the ones in section H as they are changed.

| Test | Steps | Expected |
|---|---|---|
| 1. New order | Fictional proposal order, confirm | Exactly one oversight and one delivery project; unique key, `x_` links and `c2p_counterpart_id` set both ways; layers set; customer on both; each project has its own template content; one kickoff and one portal to-do per project; no template clone; 0 emails; no invoice touched |
| 2. Re-confirmed order | (a) Confirm again; (b) cancel, set to quotation, confirm; (c) call the creation method twice | (a) stock refuses; (b) and (c) 0 new projects, a note that they exist |
| 3. Order with an archived project | Archive the delivery project, then confirm again / call the method; repeat with the oversight project; add a template project with the same order link | No new project (decision D2); the template is ignored; unarchive restores the pair |
| 4. Duplicate confirmation | Two sessions confirm the same order at the same moment; two different orders for one customer and product | One session wins and the other is a no-op with no error left in the log; the unique index holds; two orders give two separate pairs |
| 5. CRM won, one quotation | Won lead with one open quotation after step 2 of section H | One pair, no second path fires |
| 6. Cleanup simulation | Run the logic of action 753 as a count | Deletes nothing |
| 7. To-do automations | Count kickoff and portal to-dos for one deal | One kickoff and one portal to-do in total (oversight project only); none on templates or the delivery project |
| 8. Access | A Consultants-only salesperson confirms the order | Works; the pair appears for the right companies |
| 9. Tracker | Hourly sync and the pairing | No error; engagement visible |
| 10. Out of scope, confirmed untouched | Intercompany 60% rule, posted accounting, user permissions | Unchanged |
| 11. Non-proposal order (decision D3) | Confirm an order not made through the Proposal Maker that contains a project product; then one with no project product | The first gets one pair; the second creates nothing |
| 12. Archived project (decision D2) | As test 3, for both the Consultants and the Solutions project | Never a replacement |
| 13. Weekly job | Run the logic of action 751 as a count on the new pair | One task per project per week; no duplicates |

## J. Decisions

- D1: **decided**, Option A (the standard `sale_project` keeps creating the Consultants project).
- D2: **decided**, an archived project still blocks creation.
- D3: **decided**, any order with a project-creating product qualifies.
- D4: **decided**, keep the CRM "won, confirm the single quotation" step.
- D5: **done**, the Appendix A queries were run on 26 Nov (results above).
- D6: **open**, should the Weekly Status Update task (job 38) keep covering every active project, or only the oversight project? On a paired deal it now creates two tasks a week for the same client.
- Approval to build: **open**.

## Appendix A. Read-only queries (run by the owner on 26 Nov 2026, 10:36 UTC; kept for repeat use)

Run as root on the VPS. Each is `SELECT` only inside a read-only session, and output is filtered for credential-like words.

```bash
sudo -u postgres psql -d Mumtaz_C2P -At <<'SQL' | grep -viE 'passw|secret|token|api[_-]?key|bearer|authorization'
SET default_transaction_read_only = on;
\echo == A1 rule filters
SELECT 'rule ' || id || ' filter: ' || coalesce(filter_domain,'(none)') FROM base_automation WHERE id IN (2,11,12,19,30);
SELECT 'rule ' || id || ' pre-filter: ' || coalesce(filter_pre_domain,'(none)') FROM base_automation WHERE id IN (2,11,12,19,30);
\echo == A3 product 97 and template projects
SELECT 'product 97: tracking=' || service_tracking || ' template=' || coalesce(project_template_id::text,'-') || ' project=' || coalesce(project_id::text,'-') FROM product_template WHERE id = 97;
SELECT 'project ' || id || ' | ' || left(name::text,50) || ' | template=' || coalesce(is_template::text,'null') || ' | company=' || coalesce(company_id::text,'-') || ' | active=' || active FROM project_project WHERE id IN (26,28,581,582,583,584,585,586,587);
\echo == B1 projects created 25 Oct to 17 Nov
SELECT id || ' | ' || left(name::text,60) || ' | company=' || coalesce(company_id::text,'-') || ' | layer=' || coalesce(c2p_layer,'-') || ' | template=' || coalesce(is_template::text,'null') || ' | active=' || active || ' | created=' || to_char(create_date,'YYYY-MM-DD HH24:MI') || ' | by uid ' || create_uid
FROM project_project WHERE create_date >= '2026-10-25' AND create_date < '2026-11-18' ORDER BY id;
\echo == B2 chatter evidence
SELECT model || ' ' || res_id || ' | ' || to_char(date,'YYYY-MM-DD HH24:MI') || ' | ' || left(regexp_replace(body,'<[^>]+>','','g'),90)
FROM mail_message WHERE (body ILIKE '%Delivery project created in C2P Solutions%' OR body ILIKE '%Won: quotation%' OR body ILIKE '%Project(s) created:%' OR body ILIKE '%Project created from template%') AND date >= '2026-10-20' ORDER BY date;
\echo == B3 order behind each billing project
SELECT 'project ' || p.id || ' -> order ' || sol.order_id || ' state=' || so.state || ' proposal=' || coalesce(so.c2p_is_proposal::text,'null')
FROM project_project p JOIN sale_order_line sol ON sol.id = p.sale_line_id JOIN sale_order so ON so.id = sol.order_id WHERE p.id IN (23,25,27,30);
\echo == C1 modules
SELECT name || ' ' || state || ' ' || coalesce(latest_version,'-') FROM ir_module_module WHERE name IN ('c2p_project_tracker','c2p_work_hub','c2p_meeting_actions','c2p_client_onboarding','c2p_milestone_forecast','c2p_proposal','sale_project') ORDER BY 1;
\echo == E1 proposal orders
SELECT 'proposal orders: ' || count(*) || ', confirmed: ' || count(*) FILTER (WHERE state='sale') FROM sale_order WHERE c2p_is_proposal;
\echo == F1 scheduled jobs and to-do automations
SELECT 'cron ' || id || ' | ' || cron_name || ' | active=' || active || ' | every ' || interval_number || ' ' || interval_type || ' | next ' || to_char(nextcall,'YYYY-MM-DD HH24:MI') FROM ir_cron WHERE ir_actions_server_id IN (751,753,909,910) OR cron_name ILIKE '%project%';
SELECT E'\n===== ACTION ' || id || E' =====\n' || coalesce(code,'(no code)') FROM ir_act_server WHERE id IN (738,748,751) ORDER BY id;
\echo == F2 to-dos per project
SELECT 'project ' || res_id || ': ' || count(*) || ' to-dos' FROM mail_activity WHERE res_model = 'project.project' AND res_id IN (23,25,27,30,34,35,36,37) GROUP BY res_id ORDER BY res_id;
\echo == D2 delivery API write-back attachments
SELECT name || ' on ' || res_model || ': ' || count(*) || ', latest ' || to_char(max(create_date),'YYYY-MM-DD') FROM ir_attachment WHERE name IN ('presales.json','proposal.json','project_plan.json','functional.json','developer.json') GROUP BY name, res_model;
SQL
systemctl is-active delivery-api; ss -ltn | grep -c ':8800 '; curl -s -m 5 http://127.0.0.1:8800/health; echo
```
