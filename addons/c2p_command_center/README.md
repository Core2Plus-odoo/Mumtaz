# C2P Command Center

One page in Odoo that shows everything happening across C2P, for the Managing Partner.

| Section | What it shows | Click-through |
|---|---|---|
| Headline KPIs | Emails today, replies (14d), open pipeline, receivable, my overdue activities, AI work to review, delivery overdue, automation health | scrolls to the section |
| My activities | Your open To-Dos (overdue / today / planned) across every app | opens the record |
| Outreach engine | 14-day chart of first emails vs follow-ups and replies; queue, follow-ups due, failures, latest replies | queue / due / failed lists, the lead |
| Pipeline | Every deal past *Contacted*, by stage, with value, idle days and next step (stale ≥14 days, overdue next step) | the lead |
| Money | Receivable, paid this month, every unpaid customer invoice with days late, drafts | the invoice |
| AI agents | Review queue (with preview links), per-agent cards by stage, overdue, next due | the card / work board |
| Client delivery | Every *Delivery* / *Milestones* project: open, overdue, due in 7 days, last activity, RAG | the project's tasks |
| Content | Posts published in 30 days, drafts, latest posts, warning when nothing published for 7+ days | the post |
| Automation health | Every C2P / BD Engine / AI Agents scheduled action: last and next run, late or switched off | the scheduled action |

Read-only: it aggregates data that already exists. Auto-refreshes every 5 minutes.

## Access
Group **C2P Command Center** (the admin user is added on install). Add other users under
Settings › Users if they should see company-wide figures, including receivables.

## Install on core2plus.com (Mumtaz_C2P, VPS service `odoo4`)
The server loads this repo from `/opt/custom_addons/Mumtaz/addons` (see
`addons/c2p_project_tracker/scripts/backup_and_install.md`).

```bash
cd /opt/custom_addons/Mumtaz && git pull origin main
```

Then in Odoo: Apps › Update Apps List › search "C2P Command Center" › Activate.
(No restart is needed for a new module; restart `odoo4` only if it does not appear.)

Depends only on Community apps: crm, project, account, website_blog, mail.
