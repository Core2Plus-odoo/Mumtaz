# ERP Development Rules for Claude Code

This repository follows `docs/ERP_MASTER_BLUEPRINT.md`. **This file is the short execution contract; the blueprint, project ADRs, and module specifications contain the detailed rules.**

## First actions in every session
1. Read this file, `docs/ERP_MASTER_BLUEPRINT.md` sections relevant to the task, and `docs/project/` if it exists.
2. Inspect current code, actual framework/version, installed modules, tests, migration history and source-of-truth configuration. Do not assume a greenfield repo.
3. Determine whether this is Odoo development, a custom ERP, or an ERP-connected application. Never blend incompatible patterns silently.
4. Check prior work and dependency contracts before creating new modules or fields.
5. State missing high-impact assumptions, unsafe operations and required decisions without fabricating business policy.

## Product doctrine
- Build **end-to-end business process integrity** before isolated screens.
- Use **standard first**: native -> configure -> supported integrate -> small extension -> broader build only with approved gap.
- Deliver one testable vertical slice at a time, with upstream and downstream links.
- Treat accounting, tax, inventory valuation, payroll and company separation as high-integrity domains.
- Never silently extend scope or claim an optional capability is implemented.

## Mandatory design for every story
- Requirement ID, owner, role, preconditions and acceptance criteria.
- Domain entity, attributes, types, constraints, company/tenant ownership and indexes.
- Parent/child relationships, cardinality, source IDs and reference integrity.
- Workflow states, allowed transitions, approval and exception paths.
- Impact on inventory, finance, taxes, project costs, integrations and BI.
- Access checks on the server, sensitive fields and audit events.
- UI list/form/detail, notifications, empty/error/mobile states.
- Unit, integration, permission and end-to-end tests, plus migration/rollback if affected.

## Engineering guardrails
- Use fixed-point decimal money, documented currency rounding, and explicit rate context.
- Keep source document -> fulfillment -> invoice -> payment -> journal links traceable at line level.
- Do not assume every order maps to exactly one invoice or every bill maps to one receipt.
- Do not use display names or document numbers alone as migration identity.
- Enforce tenant/company isolation and permission checks in backend/domain layer.
- Do not bypass official framework accounting, ORM, security, stock or upgrade mechanisms.
- No direct alteration/deletion of posted financial history to make data reconcile.
- Posted-record correction must use the platform's approved reversal/credit/adjustment workflows.
- Implement duplicate-safe commands, idempotent integrations, retry-safe jobs, and concurrency controls.
- Preserve existing behavior unless explicitly approved and regression-tested.
- Use fake/synthetic data for demos and automated tests; never leak private or live customer data.
- Never commit secrets, change production, delete data, or deploy without authorization.

## Claude Code process
1. **Inspect:** repo + relevant docs and test suite.
2. **Map impact:** domain, fields, workflows, linkages, security, GL/stock, integrations, UI and reports.
3. **Plan:** smallest complete slice, file changes, migration, tests, rollout and rollback.
4. **Build:** reuse standards, avoid duplicate models, implement validations and rights server-side.
5. **Verify:** run actual tests and record results. Use `NOT RUN` honestly when blocked.
6. **Document:** update module spec, field dictionary, ADR/decision log, test matrix and changelog.
7. **Report:** task/impact, changes, tests/results, reconciliation, risks/assumptions, next approval/action.

## Mandatory response
```
TASK: <ID / business outcome>
REPOSITORY STATUS: <evidence from inspected code>
IMPACT: <upstream/downstream, finance, inventory, permissions>
PLAN: <slice, files, migration, tests>
IMPLEMENTED: <exact files and behavior actually changed>
VERIFIED: <test commands/results or NOT RUN>
RECONCILIATION: <actual results, variance or N/A>
DECISIONS/BLOCKERS: <remaining owner decisions>
NEXT ACTION: <smallest unblocked step>
```

## Odoo-specific (if detected)
- Verify exact Odoo version/edition and installed modules. Follow documentation for that version.
- Prefer native models, standard flows, declared `__manifest__.py` dependencies and supported ORM extensions.
- Use groups, `ir.model.access`, record rules and applicable company consistency mechanisms.
- Do not casually use `sudo()`, direct SQL or core forks.
- Test module installation, update and role/company scenarios on a disposable database.
- Treat confirmed orders, posted invoices, journals, inventory valuations and migrations as data-integrity operations.

## Definition of done
A module is NOT complete until the entire specified process works; referenced records reconcile; role/company security passes; financial and stock effects match configuration; exception paths are tested; reports drill down; change is documented; and the business owner accepts evidence. A working demo alone is not sufficient.
