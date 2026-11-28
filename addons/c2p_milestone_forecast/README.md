# C2P Milestone Forecast

Commitment date, forecast date and calculated health per milestone. Tested on
stock Odoo 19 only. Not installed anywhere.

- **Commitment date** is the standard milestone deadline.
- **Forecast date** is entered by the delivery owner.
- **Health** is calculated, never typed: green (forecast on or before the
  commitment), amber (1 to 5 calendar days late), red (more than 5), grey
  "No forecast". One limit for all projects.
- A project shows its **worst milestone**. A **reached** milestone keeps the
  colour it had when reached.
- Changing an existing commitment or forecast date needs a **reason**, stored
  in the same history entry as the tracked old and new values. Entering a date
  for the first time does not.

No approval step is built: anyone who can edit a milestone can change a
commitment date, with a reason. No automations, emails or access rules.

Bypasses: system (sudo) writes, module install (it runs as the superuser),
and trusted Python code inside `with skip_change_reason():` (import it from
`models/project_milestone.py`). No context key bypasses anything: a context is
chosen by the caller, so `c2p_skip_change_reason`, `install_mode` and the
others are refused over the API.

Tests: `odoo-bin -i c2p_milestone_forecast --test-tags /c2p_milestone_forecast`.
