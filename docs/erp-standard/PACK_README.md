# Claude Code ERP Development Pack

A C2P Group reusable, vendor-aware ERP software delivery standard.

## Contents

- `CLAUDE.md` — short project-root rules automatically loaded by Claude Code.
- `START_HERE_PROMPT.md` — copy/paste kickoff request for Claude Code.
- `docs/ERP_MASTER_BLUEPRINT.md` — comprehensive engineering/business blueprint.
- `docs/templates/MODULE_SPEC_TEMPLATE.md` — repeat per module.
- `docs/templates/ADR_TEMPLATE.md` — one per architecture decision.
- `docs/templates/INTEGRATION_CONTRACT_TEMPLATE.md` — every external/interface dependency.
- `docs/templates/TEST_AND_UAT_TEMPLATE.md` — requirement-by-requirement test evidence.
- `docs/templates/PROJECT_CHARTER_TEMPLATE.md` — confirm client context and scope.
- `docs/templates/DATA_DICTIONARY_TEMPLATE.csv` — field-level governance.
- `docs/templates/REQUIREMENTS_REGISTER_TEMPLATE.csv` — traceability starting point.
- `docs/templates/MIGRATION_RECONCILIATION_TEMPLATE.csv` — old/new mapping and differences.

## Installation into an ERP repository

1. Make a safe copy or branch of the existing repository.
2. Place `CLAUDE.md` at the repo root and copy `docs/` to repo `docs/`. Add `START_HERE_PROMPT.md` as a reference file if useful.
3. Launch Claude Code in that repository and paste the prompt from `START_HERE_PROMPT.md`.
4. First let Claude inspect and map the existing system. Approve the architecture/fit-gap before new code.
5. Create one `MODULE_SPEC_<ID>.md` for each module and implement in verified vertical slices.
6. Use the templates and stage-gates rather than telling Claude to generate the entire ERP in a single run.

**Caution:** This pack is methodology and design specifications. It is not an installed, configured, deployed or production-tested ERP application. Specific fiscal/local regulations, version compatibility, deployment approvals and real business rules require project validation.

## Priority

Platform & org -> security/masters -> financial spine -> operational end-to-end process -> industry extensions -> business intelligence -> governed AI.

## Additional reference files

- `docs/architecture/MODULE_DEPENDENCY_MAP.md` — Mermaid conceptual module map.
- `docs/architecture/ENTITY_RELATIONSHIPS.md` — Mermaid entity and linkage model.
- `docs/architecture/SECURITY_MATRIX_TEMPLATE.md` — RBAC, segregation-of-duties and company scope.
- `docs/architecture/ACCOUNTING_POSTING_RULES_TEMPLATE.md` — finance event and control-account design.
- `docs/quality/RELEASE_GATE_CHECKLIST.md` — release evidence checklist.
