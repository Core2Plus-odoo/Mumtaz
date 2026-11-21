# ERP Release Gate Checklist

Mark each **PASS / FAIL / NOT RUN / N/A** with evidence. Never auto-convert NOT RUN into PASS.

| Gate | Verification | Status | Owner | Evidence |
|---|---|---|---|---|
| Scope | approved requirements, no hidden additions | | | |
| Code | review, lint/types, dependency scan | | | |
| Data model | migrations forward/back strategy, constraints | | | |
| Transactions | happy, partial, exception, reversal paths | | | |
| Integrity | AR/AP/GL; stock/valuation; cross-company links | | | |
| Security | least privilege, field roles, tenant/company tests | | | |
| Integrations | idempotent retry, DLQ/error handling, contract tests | | | |
| UX | role usability, drill-down, accessible/RTL where scoped | | | |
| Migration | source-target mapping/counts/amounts with signed variance | | | |
| Reliability | monitoring, backup and restore evidence | | | |
| Operations | deployment plan, rollback, on-call owner | | | |
| Business | UAT script signed and training delivered | | | |
| Production | formal go/no-go approval | | | |
