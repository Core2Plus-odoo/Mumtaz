# faizy_ai - Faizy AI Team layer (Odoo 19, depends on faizy_core)

Tested on Odoo 19.0 against a stub of faizy_core built from the live faizy_prod schema
(faizy_core 19.0.1.19.0). 14 automated tests pass. NOT yet installed on faizy_prod.

## Install (staging first)
1. Copy the `faizy_ai` folder into the addons path of a STAGING copy of faizy_prod.
2. Apps > Update Apps List > install "Faizy AI Team" (or `-i faizy_ai`).
3. Settings > Users: create one user per AI agent, group "Faizy AI / Agent (API user)" only.
   Link each in Faizy AI > AI team (API user, Supervisor).
4. Put Mashood in "Faizy AI / Customer communications approver", Raza in "Faizy / Operations",
   Umer in "Faizy / Manager".
5. Inbound WhatsApp: set system parameters faizy_ai.wa_verify_token and faizy_ai.wa_app_secret,
   then give Meta the URL https://myfaizy.com/faizy_ai/whatsapp/webhook

## Rules enforced in code
- Agents can only create/edit drafts that are still waiting; they cannot write orders or messages.
- Customer messages: Mashood (or Manager) approves; orders: Operations (or Manager) approves.
- Approved customer message becomes a queued faizy.whatsapp.message only 10am-9pm Karachi
  (faizy_core's own cron then sends it); otherwise held and released by a 15-minute cron.
- Drafts cannot complete/cancel orders, send OTPs, or contain the old WhatsApp numbers.
- get_digest() on faizy.ai.draft gives Insights/CoS a read-only daily snapshot.

## Notes for review
- Tested on Odoo 19 against faizy_core 19.0.1.20.0 and faizy_website 19.0.1.18.0 from this repo
  (14 tests, including the webhook signature check). The repo validators (validate_modules,
  check_core_fields, check_view_schemas) pass.
- Cross-module read ACLs for faizy_core models are in security/core_access.xml, not the CSV.
- Approving an order_update draft runs faizy_core's own action (assign, start, confirm). Those
  actions queue faizy_core's standard WhatsApp notifications and, for confirm, meter the activity
  (paywall). That is the same as the approver pressing the button; it does not go through the
  10am-9pm hold, which applies to free-text customer message drafts only.
- Install order: faizy_core, faizy_website, then faizy_ai. Uninstalling faizy_ai leaves them intact.
