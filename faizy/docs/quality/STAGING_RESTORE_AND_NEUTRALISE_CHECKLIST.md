# FAIZY staging copy: restore and neutralise checklist (for Shafat)

Status: DRAFT, not executed by anyone. Written 22 Nov 2026 from the repo (production commit `310a346`) and a read-only look at the Hostinger panel. Nothing here has been run. Every command below is for the STAGING database only. Do not run any of it on `faizy_prod`.

Purpose: a copy of production where nothing can message a real customer, charge anyone, or email anyone, so the evidence gate and named logins can be tested. Production deploy is a separate decision by Umer and Shafat.

## 0. Facts found (read-only, Hostinger hPanel and repo)
- The VPS `srv1446185` (KVM 2, 2 CPU, 8 GB RAM, 100 GB disk, Ubuntu 24.04 with Odoo) is shared with the Mumtaz documentation setup. RAM was about 57% used, so a second Odoo on the same box can starve production. Decide: (a) separate machine, or (b) same box with hard limits, run outside customer hours.
- Backups: weekly auto-backup only. Existing: 16 Nov 2026 12:55 (37.12 GB) and 9 Nov 2026 11:36 (33.06 GB), restore time about 1 h 4 min. A Hostinger restore overwrites the VPS, so do NOT use the panel's Restore for staging. Take a database dump instead (step 1).
- Firewall rules: 0. Malware scanner: not installed. Daily backups: off.
- No staging or UAT Odoo is evidenced in the repo (`PROJECT_CHARTER.md` ASM-06). `faizy_ai` is not yet installed on `faizy_prod` according to its README.
- Costs: nothing here needs a paid service. A second VPS (option a) would; ask Umer before buying.

## 1. Build the copy
1. Fresh dump of production, read-only: `pg_dump -Fc faizy_prod > /secure/path/faizy_prod_YYYYMMDD.dump` (a dump does not change production). Record the time and the live queued-WhatsApp count: `SELECT state, count(*) FROM faizy_whatsapp_message GROUP BY 1;` Do not reuse the old 103/105 figure.
2. Restore into a NEW database whose name contains `staging`: `createdb faizy_staging && pg_restore -d faizy_staging ...`.
3. Filestore: copy the production filestore to a separate staging data dir. Do not point staging at the production filestore.
4. Separate Odoo config and systemd unit (`faizy-staging`), its own port bound to 127.0.0.1, `db_name = faizy_staging`, `list_db = False`, a new strong `admin_passwd`, `workers` low, memory limits set. Do not reuse the production `odoo.conf`.
5. Hostname containing `staging`, behind HTTPS and basic-auth or an IP allow-list, not linked from the public site. The acceptance script refuses any host without `staging`.
6. Before the first start, do step 2 below with Odoo STOPPED, so no cron fires with live credentials.

## 2. Neutralise (run on `faizy_staging` only, Odoo stopped)
Open the shell on the staging DB: `psql -d faizy_staging`, and first confirm: `SELECT current_database();` must print `faizy_staging`.

```sql
-- WhatsApp: provider off, credentials cleared
UPDATE res_company SET faizy_whatsapp_provider = 'none', faizy_whatsapp_meta_token = NULL,
  faizy_whatsapp_meta_phone_id = NULL, faizy_whatsapp_twilio_sid = NULL,
  faizy_whatsapp_twilio_token = NULL, faizy_whatsapp_twilio_from = NULL;
-- No queued message may ever be sent from this copy
UPDATE faizy_whatsapp_message SET state = 'failed' WHERE state = 'queued';
-- Inbound webhook secrets empty, so the copy cannot receive or verify live WhatsApp calls
DELETE FROM ir_config_parameter WHERE key IN ('faizy_ai.wa_verify_token', 'faizy_ai.wa_app_secret');
-- Crons off: WhatsApp queue, AI held-message release, AI nudges, recurring invoicing/orders, document reminders
UPDATE ir_cron SET active = false WHERE cron_name::text ILIKE '%whatsapp%' OR cron_name::text ILIKE '%Faizy AI%'
  OR cron_name::text ILIKE '%recurring%' OR cron_name::text ILIKE '%document expiry%';
-- Outgoing and incoming mail off
UPDATE ir_mail_server SET active = false;
UPDATE fetchmail_server SET active = false;   -- only if the fetchmail module is installed
-- Payment providers off (only if any exist)
UPDATE payment_provider SET state = 'disabled';   -- only if the payment module is installed
```
Syntax-checked on a throwaway local Odoo 19 database (the WhatsApp, cron and mail statements ran; the `faizy_ai` crons were not present there, so confirm them with the verify query). Notes: on Odoo 19 `ir_cron.cron_name` may be a JSON column; if the `ILIKE` fails, use `SELECT id, cron_name FROM ir_cron;` and update by id. Verify, do not assume: `SELECT cron_name, active FROM ir_cron;`.

Then replace real personal data. The staging copy must contain no real customer names, phone numbers, CNIC or identity documents, addresses, receipts or prescriptions:
1. Partner, worker and family-member phone and mobile fields: replace with non-routable numbers (e.g. `+9200000000NN`). List every table that stores a phone with `\d` on `res_partner`, `faizy_worker`, `faizy_family_member`; do not guess the columns.
2. Customer names, emails, street addresses: replace with synthetic values.
3. `faizy_document` records and their attachments: delete the rows and the files from the staging filestore.
4. `proof_image` / `receipt_image` and any prescription attachments on `faizy_order` and `faizy_request`: delete the attachments.
5. Reset staging passwords: set a password-reset flow for `stg.*` users only; remove or deactivate real staff and real customer logins on staging (decision D10: real Mashood/Raza logins only after Umer's separate written approval).
6. Set the free-activity grant to 0: Settings, Faizy, "Free activity grant" (company field `faizy_free_activity_grant`), and set existing partners' `faizy_free_activities` to 0 (owner decision: the free-activity claim is withdrawn).

## 3. Safety checks before anyone logs in (all must be true)
- [ ] `SELECT current_database()` is `faizy_staging`; hostname contains `staging`.
- [ ] `res_company.faizy_whatsapp_provider = 'none'` and all token/sid columns NULL.
- [ ] `SELECT count(*) FROM faizy_whatsapp_message WHERE state = 'queued'` is 0.
- [ ] `ir_config_parameter` has no `faizy_ai.wa_*` rows; no ElevenLabs, Higgsfield or Meta keys anywhere in staging config.
- [ ] Every WhatsApp, AI and invoicing cron shows `active = false`; every outgoing mail server inactive.
- [ ] A test partner's email/phone is non-routable. Create a test order and confirm nothing leaves the box (check the mail and WhatsApp queues, not just the settings).
- [ ] Backup of the staging DB taken before the first test run; restore drill done once.
- [ ] Nothing on staging is ever copied back to production. Code reaches production only through git and the release gate.

## 4. Install the branch and test
```bash
cd /path/to/staging/src && git fetch && git checkout faizy/pilot-evidence-gate
/staging/venv/bin/python /staging/odoo/odoo-bin -c /staging/odoo.conf -d faizy_staging \
  -u faizy_core,faizy_pilot,faizy_website --stop-after-init && echo "upgrade exit: $?"
```
Create the synthetic users `stg.raza`, `stg.worker1`, `stg.worker2`, `stg.sponsorA`, `stg.sponsorB` (groups: `Faizy / Operations`; portal for the rest; `stg.worker1` linked through `faizy.worker.user_id`). Then run `staging_acceptance_tests_v2.py --baseline` first (gate tests are expected to show GAP on the old code), then without `--baseline` on the branch. Report the output unedited.

## 5. Rollback
Staging is disposable: drop `faizy_staging` and restore from the dump. Production is not touched by any step above.

## 6. Sign-off
Technical release: Shafat. Business and claims: Umer. Nothing is deployed to production, no payment is activated and no WhatsApp message is released without Umer's specific approval.
