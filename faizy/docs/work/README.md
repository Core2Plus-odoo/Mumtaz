# Staff work, checklists and KPIs (faizy_work)

Status: built and tested on a throwaway Odoo 19 database. **Not installed on production. Nothing sent, nothing activated.**
Brief: "MYFAIZY complete staff work execution, lead generation and KPI implementation" (23 Nov 2026) plus the addendum
"Mandatory ERP checklists, SOPs and quality gates".

## 1. What was found (audit)

| Question | Finding |
|---|---|
| Checklist mechanism in Odoo 19 CRM or Project? | None. Activities and plans exist, but no mandatory-step, evidence, review or versioning mechanism. |
| Second CRM, task or approval app needed? | No. Leads stay `crm.lead`, tasks stay `project.task`, orders stay `faizy.order`, drafts stay `faizy.ai.draft`. |
| Staff accounts on production | Already exist, no TOTP. Mashood has CRM "All Documents", Raza has "Own Documents Only" (asymmetric). |
| CRM on production | 50 leads in stage New, all owned by Umer. Project app not installed. |

Module ownership (after §27): `faizy_work` owns the checklist engine, CRM discipline and scorecards; `faizy_ai` owns the desks (My desk), lead routing and planned work. `faizy_core`, `faizy_ai`,
`faizy_pilot` are unchanged (extended by `_inherit` only). `faizy_work_project` is an auto-install bridge that adds the
same checklist to `project.task` once Project is installed; inert until then.

## 2. Roles and permissions

Both people are peers under Umer, on the existing groups. Faizy Agent now implies the CRM salesman group (no net change on
production). No admin rights. Mashood does not gain access to family or medical documents (tested). Raza gets no unrestricted
finance approval or deletion. Restricted checklist steps need a Manager who is not the checklist owner.
**Decision needed:** align Mashood to "Own Documents Only" like Raza (recommended), or give both All Documents.

## 3. Checklist engine

Template (versioned) -> checklist -> lines, attached to a CRM lead, FAIZY order, vendor, AI draft or standalone.
One accountable owner. Mandatory steps cannot be skipped. Gates are re-checked on the server (`verify`, `qualify`, `assign`,
`complete`, `approve`). User and time recorded on every tick. Evidence is a link to the existing record, a URL or a note.
Conditional steps (organisation, individual, purchase). Blocked state needs a reason and creates an escalation activity.
Reject and reopen keep history. Released templates are locked; "New version" keeps finished checklists on their wording.
Recurring checklists are idempotent (one per person per day or ISO week). Percentages never decide a KPI on their own.
Switch: `faizy.checklist_enforce` (on). Order checklists auto-start with `faizy.checklist_orders` (shipped off).

Library: 14 templates, 100 steps. Mashood 5 (qualified digital lead, customer inquiry, content quality, campaign
preparation, nurturing and retention). Raza 5 (qualified direct-sales lead, partnership development, vendor/worker
verification, order assignment/execution, service readiness and unit economics). Daily start, daily end, weekly review (cx, ops).
Recurring checklists go only to people explicitly assigned on the template; nobody is assigned yet.

## 4. Lead rules (existing CRM stages, none renamed)

Research Candidate, Verified, Contacted, Engaged -> New. Qualified -> stage 2. Trial/First Service -> stage 3.
Paying Customer -> stage 4 (needs a live subscription or a completed order). Dragging a card is mapped to a status move and
meets the same gates. A new lead cannot start above Research. Verification needs: owner, organisation name, evidence link,
legitimate contact basis (inquiry, opt-in, public business contact, referral), a next action, duplicate review.
Originator and owner are separate fields. No harvesting of private data.

## 5. KPI scorecards

Mashood 30/20/25/15/10 (qualified pipeline, conversion, customer experience, content quality, ERP discipline).
Raza 35/25/20/10/10 (direct-sales pipeline, conversion, delivery quality, partner and vendor readiness, ERP discipline).
Weekly pilot targets: Mashood 15 verified, 10 drafts. Raza 12 / 8 / 3 discovery (stretch). A component with too little data
shows "Insufficient data". A total appears only if at least 60 weight is measurable. Conversion waits for a two-week baseline
(`faizy.kpi_start`, unset) and 5 verified prospects. Conversion target 20% is provisional.

## 6. Routing

One switch, `faizy_ai.route_leads` (off by default). When on, an unowned lead goes to the leader of the sales team that owns its source (`crm.team.faizy_lead_sources`): Digital & customer leads (Mashood) for website, Facebook, Instagram, WhatsApp; Partners & referrals (Raza) for embassy, walk-in, other. `faizy.work_route_leads` no longer exists (§27).

## 7. 30-day plans

`30day-register-mashood.csv` (M-01..M-10) and `30day-register-raza.csv` (R-01..R-10), each with the full field set.
Start date assumed **Monday 30 Nov 2026**, to be confirmed by Umer. `faizy/odoo/tools/provision_staff.py` creates them as milestone tasks in each person's desk project, next to the daily
plan (idempotent; `--milestones none` to skip). `scripts/load_30day_plan.py` was retired in §27.

## 8. Tests

Clean database, all Faizy modules: 143 tests, 0 failed (31 in `faizy_work`, 1 bridge). flake8, `validate_modules.py`,
`check_portal_access.py`, `check_view_schemas.py` and the module registry check pass. Note: after the demo script has run
on a database, two older `faizy_ai` routing tests fail on that database because the demo adds overdue activities and users;
run the suite on a clean database. UI checked as Mashood, Raza and Umer (desktop and mobile screenshots).
Demo: `scripts/work_demo.py` runs one synthetic scenario per employee and shows refusals at the gates. No message was sent.

## 9. Not done, needs approval (handoff for Claude Code)

1. Merge the PR (Umer says "merge"), then a fresh explicit "deploy".
2. Install `faizy_work` on production (`-u`/`-i`, per the deploy sequence in `faizy/CLAUDE.md`).
3. Run `provision_staff.py` (installs nothing; Project comes with `faizy_ai` 19.0.1.5.0). Runbook: `faizy/docs/plans/STAFF_WORK_DEPLOY_RUNBOOK.md`.
4. Align Mashood's CRM rights; add TOTP to existing staff accounts.
5. Assign staff on the recurring templates; set `faizy.kpi_start` and the conversion target.
6. Switch on `faizy_ai.route_leads` (the tool does) and `faizy.checklist_orders` when approved.
7. Pricing stays hidden until Umer approves figures (`faizy.show_plan_prices`). SMTP setup (FD-06) is still open.
8. Raza's manual evidence-review check (R-05).

## 10. Training checklist

Open My desk (home), read today's plan, work from the record (not from this screen), tick steps with evidence, use
"Ready for Review" when finished, use Block with a reason when stuck. Messages to customers only 10:00-21:00 Karachi.
