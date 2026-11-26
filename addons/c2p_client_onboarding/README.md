# C2P Client Onboarding

Client master record and onboarding checklist. Not installed anywhere.

**Reuses, does not replace:** the client is the existing `res.partner`; the
Consultants engagement is the existing portfolio `project.project`; the
Solutions project is its `c2p_counterpart_id`. This module creates no client,
engagement or project, and has no project-creation automation.

| Need | Where it lives |
|---|---|
| Client contacts and roles | `res.partner` children, `c2p_contact_role` |
| Approved scope | scope fields on the portfolio project, approved by a Portfolio Manager |
| Responsible C2P staff | `account_manager_id` and the Solutions project's manager |
| Onboarding checklist and status | `c2p.onboarding.check` on the portfolio project |
| Instance inventory | `c2p.client.instance` |
| Required documents | `c2p.client.document` |
| Access register | `c2p.client.access` — vault reference only |

**Credentials.** No field holds a password or key. `vault_ref` must be
`vault://collection/item`. Text fields refuse the obvious ways a secret gets
pasted (`password: …`, `token=…`, `user:pass@host`, a PEM key). That check is a
heuristic and cannot recognise an unlabelled password; the register has no
notes field and no chatter for that reason.

Tests: `odoo-bin -i c2p_client_onboarding --test-tags /c2p_client_onboarding`.
