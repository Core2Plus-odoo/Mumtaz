# C2P ERP programme: documentation index

Governing standard: [`reference/ERP_MASTER_BLUEPRINT.md`](reference/ERP_MASTER_BLUEPRINT.md) (the C2P pack, copied unchanged; the pack's own `CLAUDE.md` is kept as `reference/ERP_PACK_CLAUDE.md` and is **not** installed over the repository's existing root `CLAUDE.md`, see decision D-004).
Everything below is **Gate G0/G1 (audit and architecture): planning only. No application code was changed to produce it.**

**Labels used everywhere:** `[V]` verified fact, with its evidence · `[P]` proposed design · `[A]` assumption to confirm · `[D]` decision needing owner approval · `NOT RUN` never converted to a pass.

| # | Deliverable (directive §9) | File |
| --- | --- | --- |
| 1 | Current-system technical and functional audit | [project/01_CURRENT_SYSTEM_AUDIT.md](project/01_CURRENT_SYSTEM_AUDIT.md) |
| 2 | ERP module and capability matrix | [project/02_CAPABILITY_MATRIX.md](project/02_CAPABILITY_MATRIX.md) |
| 3 | Module dependency and integration architecture | [architecture/MODULE_DEPENDENCY_MAP.md](architecture/MODULE_DEPENDENCY_MAP.md) |
| 4 | Data model, field dictionary, ER design | [architecture/DATA_MODEL.md](architecture/DATA_MODEL.md) + [DATA_DICTIONARY_AS_BUILT.csv](architecture/DATA_DICTIONARY_AS_BUILT.csv) |
| 5 | End-to-end process linkage matrix | [architecture/PROCESS_LINKAGE_MATRIX.md](architecture/PROCESS_LINKAGE_MATRIX.md) |
| 6 | Standard functionality vs customization | [architecture/STANDARD_VS_CUSTOM.md](architecture/STANDARD_VS_CUSTOM.md) |
| 7 | Development standards and conventions | [architecture/DEVELOPMENT_STANDARDS.md](architecture/DEVELOPMENT_STANDARDS.md) |
| 8 | Security, approval and audit framework | [architecture/SECURITY_APPROVAL_AUDIT_FRAMEWORK.md](architecture/SECURITY_APPROVAL_AUDIT_FRAMEWORK.md) |
| 9 | UI/UX design system and dashboard architecture | [architecture/UX_DESIGN_SYSTEM.md](architecture/UX_DESIGN_SYSTEM.md) |
| 10 | Roadmap with milestones and dependencies | [project/ROADMAP.md](project/ROADMAP.md) |
| 11 | Testing, reconciliation, migration and deployment strategy | [quality/TEST_RECON_MIGRATION_DEPLOY_STRATEGY.md](quality/TEST_RECON_MIGRATION_DEPLOY_STRATEGY.md) |
| 12 | Prioritized backlog with acceptance criteria | [project/BACKLOG.md](project/BACKLOG.md) + [REQUIREMENTS_REGISTER.csv](project/REQUIREMENTS_REGISTER.csv) |
| – | Decision register (directive §10) | [project/DECISION_REGISTER.md](project/DECISION_REGISTER.md) |
| – | Implementation status, traceability and change log | [project/STATUS_AND_CHANGELOG.md](project/STATUS_AND_CHANGELOG.md) |
| – | Charter (draft, unresolved items marked) | [project/PROJECT_CHARTER.md](project/PROJECT_CHARTER.md) |

Blank templates from the pack are in [`templates/`](templates/); the release checklist is [`quality/RELEASE_GATE_CHECKLIST.md`](quality/RELEASE_GATE_CHECKLIST.md).
The generated artefacts (dependency analysis, field dictionary, ER edges) were produced by scripts over the working tree on 2026-11-20; regenerate them rather than editing by hand.
