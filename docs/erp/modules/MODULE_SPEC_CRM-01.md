# Module Specification: CRM-01 `c2p_crm_rules` — versioned CRM logic for the C2P pipeline

**Classification:** Common
**Module owner / process owner:** Engineering / Sales lead (to name)
**Status:** Draft (first-sprint technical spec)
**Platform:** Odoo 19 Community
**Dependencies (inbound):** `crm`, `mail`, `base_automation`
**Downstream modules impacted:** `c2p_command_center` (reads lead stages), C2P delivery system (reads leads over XML-RPC)
**Out of scope:** lead scraping (`mumtaz_lead_scraper`), nurture campaigns, any change to won deals

## 1. Business mission and measurable result

The 25 `ir.actions.server` records on `crm.lead` in the live C2P database
(qualification, scoring, assignment, archival) become code: reviewed, tested,
reversible, with a dry-run. Measure: 0 business rules outside git; the
unexplained archival of 29,484 leads cannot recur because every archive
carries a reason and an actor.

## 2. Roles and access

| Role | View | Create | Edit draft | Approve | Execute | Reverse | Export |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Sales user | own/team leads | yes | yes | no | no | no | no |
| Sales manager | all | yes | yes | enable/disable a rule | run a rule in dry-run and live | restore archived with reason | logged |
| Admin | all | — | — | yes | yes | yes | logged |

## 3. Requirements

| Req ID | Role | Need | Priority | Acceptance | Status |
| --- | --- | --- | --- | --- | --- |
| CRM-REQ-001 | Sales manager | the four rule families run from code with the same outcomes as the database actions | Must | parity on 500 sampled leads, differences listed | Proposed |
| CRM-REQ-002 | Sales manager | every rule can be run in dry-run and shows what it would change | Must | dry-run writes nothing and returns a list of (lead, field, old, new) | Proposed |
| CRM-REQ-003 | Auditor | every archive carries a reason, an actor and a timestamp; restore is one action | Must | `lost_reason_id` and a chatter message on each archived lead | Proposed |
| CRM-REQ-004 | Admin | installing the module disables, not deletes, the database actions | Must | actions `active=False` with a note; uninstall re-enables | Proposed |

## 4. Journey and links

- Upstream: `crm.lead` created by import, website form (`mumtaz_api`), scraper or by hand.
- Rules (crons, daily): `qualify` (sets stage by field completeness and email validity), `score` (writes `x_c2p_score`), `assign` (user by territory/round-robin), `archive` (bounced or dead email → `active=False` with a lost reason).
- Downstream: stage changes drive the command centre and the delivery system's enquiry stage; no accounting or stock effect.
- Cardinality: one rule run → N lead changes, each logged in `c2p.crm.rule.log` (1:N).
- Reversal: restore from the log by run id; every write is reversible because old values are stored.

## 5. Entities

| Model | Scope | Fields and constraints | Parent/child | Audit |
| --- | --- | --- | --- | --- |
| `c2p.crm.rule` | company | `name`, `family` (qualify/score/assign/archive), `active`, `domain` (text, validated), `python_code` **not used**: logic is Python in the module, parameters only in the record (`params` JSON), `last_run_at`, `last_run_id` | has runs | tracking on `active`, `params` |
| `c2p.crm.rule.run` | company | `rule_id`, `mode` (dry/live), `started_at`, `by`, `count`, `state` | has logs | immutable |
| `c2p.crm.rule.log` | company | `run_id`, `lead_id`, `field`, `old`, `new`, `applied` | — | immutable |
| `crm.lead` (ext.) | company | `x_c2p_score` Integer, `x_c2p_archived_reason` Char | — | tracking |

Field rows go into `architecture/DATA_DICTIONARY.csv` before the PR.

## 6. State machine

| Rule run | Action | Actor | Guard | Effect | Target |
| --- | --- | --- | --- | --- | --- |
| — | run dry | Sales manager / cron | rule active | logs with `applied=False`; no lead written | done (dry) |
| — | run live | Sales manager / cron | rule active, dry-run exists for this version of params | writes leads, logs `applied=True` | done (live) |
| done (live) | restore | Sales manager | within retention | reverses logged writes in order | restored |

## 7. Rules and effects

No accounting, stock or project effect. Archive sets `active=False`,
`lost_reason_id`, posts a chatter message; never deletes. Assignment never
overrides a manual assignment made after the last run (guard on
`write_date` of `user_id`).

## 8. UI

Odoo native: list and form of rules with a "Run dry" and "Run live" button;
run and log lists with filters; a stat button on the rule for the last run.
No Jawhar screen.

## 9. Interfaces

| Interface | Direction | Trigger | Idempotency |
| --- | --- | --- | --- |
| crons (one per family) | internal | daily | a run with identical params on the same day is skipped |
| `ir.actions.server` disable | internal | install hook | by `xml_id`/name list recorded in `data/legacy_actions.xml` |

## 10. Negative and edge scenarios

Lead in another company; lead already won (never touched); lead manually
assigned after the run; bounced flag on a won lead; rule params invalid
(refused with a message); concurrent live runs (lock on the rule).

## 11. Tests (GIVEN / WHEN / THEN)

| Test ID | Scenario |
| --- | --- |
| CRM-TEST-001 | GIVEN 20 synthetic leads of mixed completeness WHEN `qualify` runs dry THEN no lead changes and the log lists the expected stage moves |
| CRM-TEST-002 | GIVEN the same WHEN run live THEN stages match the dry-run list exactly |
| CRM-TEST-003 | GIVEN 3 leads with `message_bounce > 0` and one won WHEN `archive` runs THEN 2 archived with a lost reason and a chatter message; the won lead untouched |
| CRM-TEST-004 | GIVEN a live run WHEN restored THEN every logged field returns to its old value |
| CRM-TEST-005 | GIVEN a sales user WHEN they call run live over RPC THEN access error |
| CRM-TEST-006 | GIVEN a lead of company B WHEN company A's rule runs THEN untouched |
| CRM-TEST-007 | GIVEN install on a database with the 25 named actions WHEN installed THEN the actions are inactive with a note; uninstall re-activates |
| CRM-PARITY-008 | GIVEN a staging copy of `Mumtaz_C2P` WHEN each family runs dry THEN the differences against the database actions' outcomes on 500 leads are listed and reviewed (manual gate, evidence attached) |

## 12. Acceptance

Sales lead accepts the parity report; engineering shows CI green on a fresh
database and on the staging copy; the live actions are switched off only
after that acceptance, by a named human, in a change recorded in
`quality/RELEASE_CHANGELOG.md`.
