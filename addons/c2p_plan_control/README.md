# C2P Plan Control

One approved delivery plan, changed only on the record. Not installed anywhere.

- A contributor **proposes** a change with a reason. Changing a committed date,
  assignee, milestone or acceptance criteria directly is refused.
- The delivery owner **approves or rejects** in-scope changes. The record keeps
  who, when, why, previous value, new value, baseline and what it affects.
  The owner's own direct edits are logged automatically.
- A milestone date change keeps the **baseline** next to the forecast and
  creates an activity for the Consultants account owner.
- A **scope, price or contract** change is never applied here. It becomes one
  standard `c2p.change.request` on the paired Consultants engagement.

Adds `c2p.plan.change`, two fields on `project.task`/`project.milestone`. No
project or engagement model.

Tests: `odoo-bin -i c2p_plan_control --test-tags /c2p_plan_control`.
