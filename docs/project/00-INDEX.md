# C2P / Mumtaz ERP — Wave 0 deliverable index

**Governing standard:** `docs/erp-standard/ERP_MASTER_BLUEPRINT.md` (C2P ERP Master
Blueprint v1.0, 20 Nov 2026), installed into this repository unmodified.

**Status:** Wave 0 (Audit and design). **No application code has been written or
changed for this directive.** Everything below is analysis of the repository as it
stands at commit `1ea980a` on branch `claude/gifted-turing-jjdsb2`.

## Evidence classes used throughout

Every statement in these documents carries one of four markers. This is the
blueprint's §21.2 requirement ("do not bury unknown assumptions") made mechanical.

| Marker | Meaning |
|---|---|
| **[FACT]** | Measured from this repository's source by a script or command recorded in the document. Reproducible. |
| **[DESIGN]** | A proposal by the architect. Not yet approved, not yet built. |
| **[ASSUMPTION]** | Taken as true to make progress. Must be confirmed; wrong-if-unconfirmed consequences stated. |
| **[DECISION]** | Requires the business owner. Listed in `DECISION_REGISTER.md` with an ID. Blocks the work that depends on it. |

## The twelve deliverables

| # | Deliverable | Document |
|---|---|---|
| 1 | Current-system technical and functional audit | [`01-AS-IS-AUDIT.md`](01-AS-IS-AUDIT.md) |
| 2 | ERP module and capability matrix | [`02-CAPABILITY-MATRIX.md`](02-CAPABILITY-MATRIX.md) |
| 3 | Module dependency and integration architecture | [`../architecture/MODULE_DEPENDENCY_MAP.md`](../architecture/MODULE_DEPENDENCY_MAP.md) |
| 4 | Data model, field dictionary and entity relationships | [`../architecture/ENTITY_RELATIONSHIPS.md`](../architecture/ENTITY_RELATIONSHIPS.md) + [`../architecture/DATA_DICTIONARY_AS_IS.csv`](../architecture/DATA_DICTIONARY_AS_IS.csv) |
| 5 | End-to-end business process linkage matrix | [`../architecture/PROCESS_LINKAGE_MATRIX.md`](../architecture/PROCESS_LINKAGE_MATRIX.md) |
| 6 | Standard functionality versus customization analysis | [`FIT_GAP_REGISTER.md`](FIT_GAP_REGISTER.md) |
| 7 | Development standards and coding conventions | [`../architecture/DEVELOPMENT_STANDARDS.md`](../architecture/DEVELOPMENT_STANDARDS.md) |
| 8 | Security, approval and audit framework | [`../architecture/SECURITY_MATRIX.md`](../architecture/SECURITY_MATRIX.md) |
| 9 | UI/UX design system and dashboard architecture | [`../architecture/UX_DESIGN_SYSTEM.md`](../architecture/UX_DESIGN_SYSTEM.md) |
| 10 | Development roadmap with milestones and dependencies | [`ROADMAP.md`](ROADMAP.md) |
| 11 | Testing, reconciliation, migration and deployment strategy | [`../quality/TEST_MIGRATION_DEPLOY_STRATEGY.md`](../quality/TEST_MIGRATION_DEPLOY_STRATEGY.md) |
| 12 | Prioritized implementation backlog with acceptance criteria | [`BACKLOG.md`](BACKLOG.md) |

Supporting: [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) (draft — the charter is the
one thing an architect must not invent), [`DECISION_REGISTER.md`](DECISION_REGISTER.md).

## The audit's single biggest limitation — read this first

**This analysis is static only.** It parses source code. It did **not** connect to
any running Odoo instance or database, because this container cannot reach the
production VPS at all:

```
$ timeout 8 bash -c 'cat < /dev/null > /dev/tcp/187.77.128.199/22'   → Connection refused
$ timeout 8 bash -c 'cat < /dev/null > /dev/tcp/187.77.128.199/8069' → Connection refused
```

Consequently nothing here states which modules are **installed**, which database
each serves, what data volumes exist, or whether any flow actually works at
runtime. Source code in `addons/` is what *could* be installed, not what *is*.
Closing that gap is `DEC-001` and it gates Waves 1–2.

The repository already carries live findings from earlier sessions, gathered by
running `c2p-delivery-system/scripts/inspect_odoo_db.py` on the VPS; where this
audit relies on those, it cites `c2p-delivery-system/docs/07-mumtaz-c2p-crm-findings.md`
and marks the claim **[FACT, prior session]** rather than re-asserting it as fresh.
