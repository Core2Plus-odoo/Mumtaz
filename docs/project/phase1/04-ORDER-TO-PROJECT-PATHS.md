# 04. How a confirmed sale order creates projects in Mumtaz_C2P

Read-only report, 26 Nov 2026. Repository `Core2Plus-odoo/Mumtaz`, `main` at `2af0185`.
Status: **draft for approval. Nothing was built, installed, deployed or changed.**

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
- **Correction to my 25 Nov reading.** I said no rule 11 clone exists on live because only project 9 matched an order-number name. That query assumed order names like `S00131`. Project names on live carry references such as `C2P-…-2709-00…`, so rule 11 clones named after other order numbers would have been missed. **Whether rule 11 ever cloned for the four recent deals is [UNKNOWN].**
- Numbering: your list items 2 and 3 are database automation rules **11** and **19**.

## Summary

1. A won deal can pass through **three** project-creating paths, plus a fourth tool that creates bare projects. Only path 3 creates the Solutions project. **[VERIFIED by code reading; live behaviour REPORTED]**
2. The Solutions delivery project is created only by server action 919, and the only caller found is action 766 (rule 19). A quotation confirmed by hand, or any order not coming from a won lead, **gets no Solutions project**. **[VERIFIED by code, REPORTED for the callers]**
3. The Consultants and Solutions projects are linked by two **custom database fields** (`x_billing_project_id`, `x_delivery_project_id`) that exist in no repository file, not by the tracker's `c2p_counterpart_id`. **[VERIFIED absent from repo]**
4. The accepted proposal has **no record of its own**: it is the confirmed `sale.order`. There is no acceptance state and no project link in `c2p_proposal`. **[VERIFIED]**
5. The duplicate-cleanup job deletes (`unlink`) projects; it does not archive. **[REPORTED code]**
6. Hard-coded ids (templates 26, 28, 581–587; companies 1 and 4; users 2, 20, 26) sit inside the live actions. **[REPORTED]**

## 1. Map of the paths

| # | Path | Trigger | Creates | Company | Links the two projects? |
|---|---|---|---|---|---|
| 1 | Product 97 "Odoo Implementation — Milestone…", tracking `project_only` (standard `sale_project`) | Order confirmation | Consultants "billing" project | The order's company | No |
| 2 | Rule 11 → action 747 "Clone project template(s) on order confirmation" | `sale.order` create or write | Copy of a template picked by product-name keyword | The template's company [UNKNOWN] | No |
| 3 | Rule 19 → action 766 → action 919 | `crm.lead` create or write, stage is Won | Confirms the quotation (path 1 fires), then the Solutions project | Consultants (company 1) and Solutions (company 4) | Yes, two custom fields |
| 4 | Delivery API write-back (`sync.py:51-57`) | "project" stage in the Agency OS | Bare project and tasks | Not set | No |

Not creators: `c2p_project_tracker` and `c2p_proposal` (sections C and E), `c2p_master_agent` (creates tasks only, `master_agent.py:213-219`). **[VERIFIED]**

## A. What rules 11 and 19 do

### A1. Rule 11 / action 747 (path 2)

| Item | Finding | Tag |
|---|---|---|
| Rule state, trigger, model | Active; `on_create_or_write` on `sale.order` | REPORTED |
| Domain / pre-filter / trigger fields | Not read | **UNKNOWN** (A1 query) |
| Guard | Skips unless `order.state == 'sale'`, `x_project_created` is false and the order has a customer (L13) | REPORTED |
| Writes | `sale.order.x_project_created = True` **before** copying (L15); chatter on the order (L33-34) | REPORTED |
| Template choice | Lower-cased product names matched to keywords: template **581** for "odoo erp", "odoo implementation", "odoo version upgrade"; 582–587 for other keyword sets; skips "retainer" and "booking fee" (L1-24) | REPORTED |
| Creation | `template.copy({'name': '<order> - <template name>', 'partner_id': customer})` (L31) | REPORTED |
| Company | Not passed, so the copy keeps the template's company | **UNKNOWN** (template 581's company) |
| Template flag | A plain copy of a template project **keeps `is_template = True`** (`project/models/project_project.py:477-478`). The rehearsal produced a template-flagged clone. | VERIFIED (stock); live not seen |
| Links the two projects | No: nothing is written that points at another project | REPORTED code |
| Re-confirmation | Stock Odoo refuses to confirm an order not in draft or sent (`sale/models/sale_order.py:1209-1213`). The rule also fires on any later write; the `x_project_created` flag (L13) stops a second clone. | VERIFIED + REPORTED |
| Project already exists | Not checked. Only the flag decides. A copied order that inherits the flag would never clone. | REPORTED code; flag definition UNKNOWN |
| Why the four recent deals show no S-numbered clone | Not established (see correction above) | **UNKNOWN** |

### A2. Rule 19 / action 766, then 919 and 920 (path 3)

| Item | Finding | Tag |
|---|---|---|
| Rule state, trigger, model | Active; `on_create_or_write` on `crm.lead` | REPORTED |
| Domain / pre-filter | Not read | **UNKNOWN** (A1 query) |
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

### A3. Path 1 (product 97)

| Item | Finding | Tag |
|---|---|---|
| Tracking | `project_only` | REPORTED |
| Template link | Task statement says template 26 "TEMPLATE · Billing overview". The owner's query did not select it. Indirect support: action 766 renames projects named "TEMPLATE…" (L11-13), and stock Odoo names such a project `<order> - <template name>`. | REPORTED / **UNKNOWN** in the database |
| Behaviour | One project per order per template; a template flagged `is_template` is built with `action_create_from_template`, otherwise `copy` (`sale_project/models/sale_order_line.py:196-208`, one-per-order test at 358-375). Company is the order's company; the customer is the order's customer. | VERIFIED (stock) |

## B. Which path created projects 34, 35, 36, 37 and 23, 25, 27, 30

Evidence only. Creation dates (25 Oct to 16 Nov) are from the task statement; I have no dates, creators or chatter for these rows.

| Evidence | Tag |
|---|---|
| The pairs are 23↔36, 25↔35, 27↔34, 30↔37. Each Consultants project holds `x_delivery_project_id` pointing at its Solutions project; each Solutions project holds `x_billing_project_id` pointing back. Tracker layer is empty on all eight. | REPORTED (25 Nov 18:00 paste) |
| Of the seven action codes I read, only action **919** writes those two fields (L9, L14). The other 29 actions' code was not read, so exclusivity is **not proven**. | VERIFIED for 7 actions; UNKNOWN for the rest |
| The "who calls 919" query returned only action 766; 919 has no rule, no scheduled job and no menu button. | REPORTED |
| Naming: the delivery projects end "– Delivery", the suffix action 919 adds (L7). Billing project names look like lead names, which is what action 766 sets (L13). | REPORTED, consistent |
| **Conclusion (inference, not proof):** the Solutions projects 34–37 were created by action 919, reached through rule 19 / action 766; the Consultants projects 23, 25, 27, 30 were created by path 1 inside the quotation confirmation that 766 runs. A hand-run of action 919 from the technical menu cannot be excluded. | **UNKNOWN until query B1/B2** |
| Whether rule 11 also created anything for these deals | **UNKNOWN** (see correction) |

## C. Are c2p_meeting_actions and c2p_milestone_forecast installed?

| Module | Merged | Installed in Mumtaz_C2P | Tag |
|---|---|---|---|
| `c2p_meeting_actions` 19.0.1.0.0 | Yes, PR #171 | Reported installed 25 Nov about 09:33 UTC, with the tracker, work hub and client onboarding | REPORTED |
| `c2p_milestone_forecast` 19.0.1.0.0 | Yes, PR #205 | Reported installed 25 Nov about 08:47 UTC | REPORTED |

Both are installed according to the owner's own server output on 25 Nov. I deployed nothing today and did not re-check; state today is **UNKNOWN** (query C1). `c2p_project_tracker` creates no projects: its `create()` only mirrors the counterpart link (`project_project.py:166-176`), the install hook only classifies and pairs existing projects by hard-coded ids (`hooks.py:11-16`, `62-107`), and its hourly job writes milestone tasks only (`data/ir_cron.xml:10-12`). **[VERIFIED]**

## D. What the delivery API writes to Odoo

| Item | Finding | Tag |
|---|---|---|
| Writes | `crm.lead` create (`odoo.py:82-86`, `main.py:833`), `sale.order` quotation create (`odoo.py:88-90`, `sync.py:44-46`), `project.project` create with a name only (`odoo.py:92-93`, `sync.py:53`), `project.task` create (`odoo.py:95-98`, `sync.py:54-56`), `res.partner` create (`odoo.py:109`), chatter post (`odoo.py:111-113`), `ir.attachment` create, and unlink of a same-named attachment first (`odoo.py:115-135`): `presales.json`, `proposal.json`, `project_plan.json`, `functional.json`, `developer.json` | VERIFIED |
| What it does not do | Never confirms an order; sets no company, template, customer or sale link on the project | VERIFIED |
| When it runs | Only for an engagement with an `odoo_db` set (`sync.py:22-23`) | VERIFIED |
| Idempotency | Ids are kept in the API's own SQLite store, not in Odoo (`sync.py:5-7`, `main.py:220-226`) | VERIFIED |
| Service | Unit `delivery-api` (`deploy/setup.sh:86-89`, `deploy/delivery-api.service.tmpl`) on `127.0.0.1:8800` (`deploy/finish.sh:11`) | VERIFIED as designed |
| **Is it running now?** | `CLAUDE.md` says the console is live at the delivery host. I cannot check the service. | **UNKNOWN** (query D1) |
| Which Odoo database it targets | Taken from each engagement or the `C2P_CRM_DB` setting | **UNKNOWN** |

None of projects 23–37 can be a delivery-API project: they carry the `x_` links the API never writes. **[VERIFIED reasoning]**

## E. The accepted proposal as the engagement key

| Item | Finding | Tag |
|---|---|---|
| What a proposal is | `c2p_proposal` extends `sale.order` with `c2p_*` fields (`sale_order.py:435-475`). The Proposal Maker wizard sets `c2p_is_proposal = True` (`proposal_wizard.py:406`). There is no proposal model of its own. | VERIFIED |
| Acceptance | No state or field in the module. Acceptance is the standard order confirmation (`state = 'sale'`); standard fields `signed_by` and `signed_on` exist (`sale/models/sale_order.py:131-133`) if portal signature is used. | VERIFIED (stock); use on live **UNKNOWN** |
| Link to a project | None. `c2p_proposal` depends only on `sale_management` and `crm` (`__manifest__.py:19`) and references no project model. | VERIFIED |
| Standard link order → project | `project.sale_line_id` and `project.sale_order_id` (related) from `sale_project` (`project_project.py:28, 35` in stock) | VERIFIED (stock) |
| Tracker link | Optional manual `c2p_sale_order_id`, visible to the commercial group only, used for received amounts (`c2p_project_tracker/models/project_project.py:102-105`) | VERIFIED |
| Were the four recent orders Proposal Maker orders? | Not known | **UNKNOWN** (query E1) |

So the engagement key can be **the `sale.order` id**, with `c2p_is_proposal` as the "this is a proposal" marker and `state = 'sale'` as "accepted".

## F. Duplicate risks

| Risk | Finding | Tag |
|---|---|---|
| Kickoff to-do (rule 2 → action 738) and portal to-do (rule 12 → action 748) fire on every `project.project` create | Names say "no auto-send" and "no auto-invite". They fire on **any** create, including template copies, so one deal can leave up to three pairs of to-dos (billing, delivery, any rule 11 clone). Whether the code skips templates or existing to-dos was not read. | trigger REPORTED; code **UNKNOWN** (query F1) |
| Duplicate Cleanup, action 753, scheduled job active | Searches **active** projects with a customer, groups them by (name, customer, company, template flag) and **`unlink()`s every project except the lowest id** (L1-9). Deletion is permanent and cascades to tasks. Different names across paths (`<order> - …`, `<lead name>`, `… – Delivery`) mean it does **not** catch cross-path duplicates; it removes exact same-name copies only. Archived projects are not searched. Interval: 10 minutes per the task statement. | code REPORTED; interval REPORTED, **UNKNOWN** in the database |
| Weekly Status Update Task Creation, action 751, scheduled job active | Touches projects and tasks and creates tasks (flags in the listing). Code, schedule and which projects it covers (templates? archived?) not read. | **UNKNOWN** (query F1) |
| Stage-change email, rule 10 → action 746 | Emails the client and project owner on every task stage change for tasks older than 10 minutes, with the task name in the body (age guard L5, body L11, mail L25-31). Not a creator; relevant to what template task titles may contain. | REPORTED code; rehearsal VERIFIED the body names the task |
| Handoff ownership flip, rule 3 → action 739 | Switches `x_owning_team` and the owner on a task change at a named stage. Not a creator. | REPORTED code |
| Re-use of hard-coded ids | Templates 26, 28, 581–587, company 4, users 2, 20, 26 inside the actions | REPORTED |

## G. Proposal: one creation path keyed to the accepted proposal (not built)

**Key.** The accepted proposal is the confirmed `sale.order`. Add one unique link on `project.project`: `c2p_source_order_id` (many2one to `sale.order`) and `c2p_project_role` (`oversight` or `delivery`), with a database unique index on the pair where the order is set. The pair is unique **including archived rows**, so an archived project still counts as "exists". Templates are never matched or created against an order.

**Where.** A small addon in this repository (for example `c2p_order_projects`, depending on `sale_project` and `c2p_project_tracker`), replacing the three live database actions with versioned, tested code. It overrides `sale.order._action_confirm` after the standard step, so manual confirmation, CRM won, portal acceptance and the API all pass through one place.

**What it does on confirmation**, in one transaction, only for orders that carry the proposal marker or an engagement-type product (a setting):
1. Finds the oversight and delivery projects for this order by the unique key. If both exist (archived or not), it does nothing.
2. Creates the missing one from its template with the standard template mechanism (`action_create_from_template`), in the correct company looked up by setting, not by id 1 or 4.
3. Sets the customer, the order line link, the tracker layers (portfolio and delivery) and `c2p_counterpart_id`.
4. Also fills `x_billing_project_id`, `x_delivery_project_id` and mirrors milestones with `x_billing_milestone_id`, so rule 30 / action 920 keeps working during the transition.
5. Posts one chatter note on the order.

**Decision D1 (needs you).** Who creates the Consultants oversight project?
- **Option A, recommended:** the standard `sale_project` keeps creating it, because it also carries the order-line link that milestone invoicing needs; the new code adds the Solutions project and the pairing in the same confirmation. For the user it is one path (confirm the order) and one transaction.
- **Option B:** the new code creates both and product tracking is set to "no". One creator, but milestone invoicing must be re-tested before any product is switched.

**Decision D2 (needs you).** Archived project: I propose it still blocks creation (the order already has one; an administrator unarchives it). The alternative, ignoring archived projects, would create a second project.

## H. Which existing paths to switch off, and in what order

Nothing is switched off until the new path passes the staging plan. At no point should two creators be on.

| Order | Change | Why this position |
|---|---|---|
| 0 | Install the new addon on live with its setting **off** | No behaviour change |
| 1 | Rule 11 / action 747 **off** | Keyword clones; evidence it adds anything is missing; independent of the others |
| 2 | In action 766 remove the call to 919 (L14) and the no-quotation branch (L24-44). Keep the "won → confirm the single quotation" step if the business still wants it. | After this, 919 has no caller |
| 3 | Product 97 and any T0x product: unchanged under Option A; tracking "no" under Option B | Only under Option B |
| 4 | Switch the new path **on** | Single creator from here |
| 5 | Rules 2 and 12 (kickoff and portal to-dos): add "not a template" and "one per project" conditions | Stops duplicate to-dos |
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
| 7. To-do automations | Count kickoff and portal to-dos per project | One each; none on templates |
| 8. Access | A Consultants-only salesperson confirms the order | Works; the pair appears for the right companies |
| 9. Tracker | Hourly sync and the pairing | No error; engagement visible |
| 10. Out of scope, confirmed untouched | Intercompany 60% rule, posted accounting, user permissions | Unchanged |

## J. Decisions needed before any build

- D1: Option A or B (section G).
- D2: archived project blocks creation, or is ignored.
- D3: which orders qualify: proposal-flagged only, or any order with an engagement-type product.
- D4: keep the CRM "won → confirm the single quotation" behaviour, or retire it.
- D5: approval for the read-only queries in Appendix A.

## Appendix A. Read-only queries to settle the UNKNOWN items

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
