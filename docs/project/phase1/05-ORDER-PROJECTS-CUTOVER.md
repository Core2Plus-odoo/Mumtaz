# 05. Order projects: cutover plan and proposed changes to the live automations

26 Nov 2026. Companion to `04-ORDER-TO-PROJECT-PATHS.md`. **Nothing here has been
applied.** The module `addons/c2p_order_projects` is built and tested on stock
Odoo 19; it is not installed on any database. Every change to a live automation
below is **proposed text** that needs the owner's approval and a staging run first.

## 1. The module

- Confirming an order with a project-creating product gives the order one oversight
  project (the one the standard Sales Project flow creates, tagged by this module)
  and one delivery project (created here from a template, in the delivery company).
  Both carry `c2p_source_order_id` and `c2p_project_role`; a database index allows
  one of each per order, archived projects included, templates excluded.
- Pairs them in the Project Tracker only when the delivery template has a Backlog stage.
- Fills `x_billing_project_id`, `x_delivery_project_id` and `x_billing_milestone_id`
  where they exist (Mumtaz_C2P only), as action 919 did.
- Adds no delivery project when the order has another project line, and posts a note instead (a second project line makes the standard flow create a second project, in the order's company).
- Never blocks a confirmation: an error is logged and noted on the order.
- Off until switched on. System parameters (Settings > Technical > Parameters):

| Parameter | Value |
|---|---|
| `c2p.order_projects.enabled` | `1` to switch on |
| `c2p.order_projects.delivery_company_id` | id of C2P Solutions (4 on Mumtaz_C2P) |
| `c2p.order_projects.default_delivery_template_id` | id of the default delivery template (28 on Mumtaz_C2P) |
| `c2p.order_projects.pair_in_tracker` | `0` to skip the tracker pairing (default `1`) |

A product can set its own delivery template (field "Delivery Project Template" on the
product form), which is how a T01 product will pick the T01 template.

**T01 product setup rule (decided 27 Nov 2026).** The standard template link ("Project Template") is the Consultants oversight template; the delivery template goes in the product's Delivery Project Template field. Never link the delivery template as the standard template: the standard flow would create the delivery project itself and there would be no oversight one.

**Known limit of the default template.** Template 28 has phase stages ("1. Discovery & BRD"
and so on) and no Backlog stage, so with it the pair is created but **not** paired in
the tracker, and a note says so. A template with a Backlog stage (such as the T01
template) pairs.

## 2. Proposed changes to the live automations (not applied)

Each change is written so that it can be reversed by pasting the old text back.

| # | Change | Why |
|---|---|---|
| 1 | Rule 11 / action 747 **off** (set the rule inactive) | It copies nothing today (templates 581 to 587 do not exist); switching it off only stops the `x_project_created` flag write |
| 2 | Action 766: delete the one line that runs action 919 (line 14 of the pasted text: `env['ir.actions.server'].sudo().browse(919).with_context(...).run()`), and delete the whole no-quotation branch (lines 24 to 44, from `marker = '[OPP:%s]' % lead.id` to the last `lead.message_post(...'Won without a quotation...')`). Everything else stays: it still confirms the single quotation (decision D4). | The module now creates the delivery project at confirmation; the branch made a project no order would ever key (decision D7) |
| 3 | Action 919: insert at the very top the guard below | 919 was run by hand twice per project on 16 Nov; once the module is on it must not run again |
| 4 | Actions 738 and 748: skip delivery projects (text below) | One kickoff and one portal to-do per deal, not two of each |
| 5 | Action 751 (weekly status task): exclude delivery projects (text below), decision D6 | One weekly task per deal |
| 6 | Job 40 / action 753 (duplicate cleanup) **off** once the key is live | It deletes permanently and the index makes it redundant |

**Decision D7 (26 Nov 2026): the no-quotation branch is retired.** Today a Won lead with no quotation gets the billing template (project 26) copied into Consultants with no order behind it. After the edit above, such a lead creates nothing and nobody is told, so the sales team must raise the quotation first. If a reminder is wanted, it is a separate small change.

**Guard for action 919** (insert as the first lines):

```python
if env['ir.config_parameter'].sudo().get_param('c2p.order_projects.enabled') in ('1', 'true', 'True'):
    raise UserError('Retired: projects are created when the order is confirmed (module c2p_order_projects).')
```

**Actions 738 and 748**: add as the first statement inside the `for` loop:

```python
    if record.c2p_project_role == 'delivery':
        continue
```
(in action 748 the loop variable is `project`, so write `project.c2p_project_role`).

**Action 751**: change the first line to

```python
projects = env['project.project'].search([('active','=',True), ('partner_id','!=',False), ('c2p_project_role','!=','delivery')])
```

The two to-do actions and 751 can only be edited after the module is installed, because
they read the new field.

## 3. Backfill of the existing pairs (not applied)

Only 27 and 34 can be keyed: project 27 has order 22. Projects 23, 25 and 30 have no
order line, so 23↔36, 25↔35 and 30↔37 stay as legacy pairs with the order key empty (the
index only applies where the key is set). Proposed one-off, after the module is installed:

```sql
UPDATE project_project SET c2p_source_order_id = 22, c2p_project_role = 'oversight' WHERE id = 27;
UPDATE project_project SET c2p_source_order_id = 22, c2p_project_role = 'delivery'  WHERE id = 34;
```

## 4. Order of steps, each with its own approval and rollback

| Step | Action | Rollback |
|---|---|---|
| 0 | Staging run on a locked copy of live (see section 5) | Delete the copy |
| 1 | Back up (dump and filestore), copy the module to `/opt/custom_addons/`, install with the feature **off**, restart | Uninstall; restore the dump if needed |
| 2 | Switch rule 11 off | Switch it on |
| 3 | Edit actions 738, 748, 751 (they read the new field) | Paste the old text |
| 4 | Set the four parameters; `enabled` last | Set `enabled` to `0` |
| 5 | Edit action 766 and insert the 919 guard | Paste the old text; remove the guard |
| 6 | Watch the first real order: one oversight, one delivery, one kickoff and one portal to-do | Set `enabled` to `0` |
| 7 | Backfill 27 and 34; switch job 40 off | Clear the two fields; switch job 40 on |

Steps 2 to 5 are in this order so that at no moment two creators are on.

## 5. Staging test

The test plan is section I of `04-ORDER-TO-PROJECT-PATHS.md` (new order, re-confirmed order,
archived project, duplicate confirmation, plus the checks added by decisions D2, D3 and D6).
The runbook for this module is `06-ORDER-PROJECTS-STAGING-RUNBOOK.md`: a locked copy of live with scheduled jobs and mail off,
fictional customers only, scripts that refuse any other database, deals that roll back, and the phases baseline, install,
off, on (old automations still active), edited (the proposed text changes applied to the copy) and a two-process race.

## 6. What is verified, what is not

- **Verified on stock Odoo 19** (fictional data): 22 tests, including all four plan cases, plus a
  separate run with the three `x_` fields present.
- **Not verified:** a copy of live data; the live automations after the edits above; the T01
  template and product (they do not exist yet; they follow after this).
