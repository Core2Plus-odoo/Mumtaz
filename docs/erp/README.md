# C2P Group ERP programme — engineering documentation

Governing standard: the **C2P ERP Master Development Blueprint** (pack of
20 Nov 2026), adopted for this repository on 20 Nov 2026. This folder is the
project instance of that standard, laid out as its §20 file contract asks.

Every statement in these documents carries one of four tags:

| Tag | Meaning |
| --- | --- |
| **[VERIFIED]** | Read from code, configuration, tests or a running system in this repository; the file is named |
| **[PROPOSED]** | A design or plan this programme recommends; not yet built |
| **[ASSUMPTION]** | Something taken as true without evidence; listed in the decision register for confirmation |
| **[DECISION]** | Needs a named owner's approval before work depends on it |

## Contents (the twelve first-assignment deliverables)

| # | Deliverable | File |
| --- | --- | --- |
| 1 | Current-system technical and functional audit | `00-AUDIT.md` |
| 2 | ERP module and capability matrix (AS-IS) | `01-CAPABILITY_MATRIX.md` |
| 3 | Module dependency and integration architecture | `architecture/MODULE_DEPENDENCY_MAP.md` |
| 4 | Data model, field dictionary, entity relationships | `architecture/DATA_MODEL.md`, `architecture/DATA_DICTIONARY.csv` |
| 5 | End-to-end business process linkage matrix | `architecture/PROCESS_LINKAGE_MATRIX.md` |
| 6 | Standard functionality versus customisation analysis | inside `01-CAPABILITY_MATRIX.md` (disposition column) and `project/FIT_GAP_REGISTER.md` |
| 7 | Development standards and coding conventions | `DEVELOPMENT_STANDARDS.md` |
| 8 | Security, approval and audit framework | `architecture/SECURITY_MATRIX.md`, `architecture/ACCOUNTING_POSTING_RULES.md` |
| 9 | UI/UX design system and dashboard architecture | `UX_DESIGN_SYSTEM.md` |
| 10 | Development roadmap with milestones and dependencies | `ROADMAP.md` |
| 11 | Testing, reconciliation, migration and deployment strategy | `quality/TEST_MIGRATION_DEPLOYMENT_STRATEGY.md` |
| 12 | Prioritised implementation backlog with acceptance criteria | `BACKLOG.md` |

Governance files: `project/PROJECT_CHARTER.md` (draft, gaps marked),
`project/DECISION_REGISTER.md` (ADR-001 to ADR-012 and project decisions),
`project/REQUIREMENTS_REGISTER.csv`, `project/TRACEABILITY_MATRIX.md`,
`quality/RELEASE_GATE_CHECKLIST.md`.

Module specifications are added under `modules/` one per slice as each is
started, using the pack's template; the first is
`modules/MODULE_SPEC_CRM-01.md` (versioned C2P CRM rules), written as the
first-sprint technical spec. The pack itself is versioned under `standard/`
(blueprint, templates, rules, kickoff prompt) so the governing text is in git.

## How the blueprint's rules apply here

The pack's `CLAUDE.md` is an execution contract. This repository already has
a root `CLAUDE.md` (C2P delivery system) and `docs/mumtaz-jewel/CLAUDE.md`
(Jawhar). The ERP rules are not pasted over them: `DEVELOPMENT_STANDARDS.md`
restates the pack's guardrails as this repository's conventions and the root
`CLAUDE.md` points to it. Where the three disagree, the stricter rule wins,
and the Jawhar rules on branches, deploys and compliance values stay in force
for the jewellery product.
