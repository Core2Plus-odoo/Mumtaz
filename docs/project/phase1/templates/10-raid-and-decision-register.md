# RAID Log and Decision Register

> **INTERNAL master; a client-safe extract appears in the weekly status report.**

| Document ID | C2P-RAID-`<PROJECT-REF>`-01 |
| Version | `<0.1>` |
|---|---|
| Status | `<Draft / In Review / Approved / Superseded>` |
| Project reference | `<PROJECT-REF>` |
| Client | `<CLIENT LEGAL NAME>` |
| Date | `<YYYY-MM-DD>` |
| Author | `<NAME, ROLE>` |
| Reviewer | `<NAME, ROLE>` |
| Approved by / date | `<NAME>` / `<YYYY-MM-DD>` |

### Approval history
| Version | Date | Author | Reviewer | Approved by | Change |
|---|---|---|---|---|---|
| `<0.1>` | `<YYYY-MM-DD>` | `<NAME>` | `<NAME>` | — | Initial draft |

---

Mirrors `c2p.raid.item` (`item_type`, `impact`, `probability`, `score`, `state`,
`resolution`, `owner_id`, `raised_date`, `due_date`, `blocked_task_id`) so this
document renders data already captured rather than being a second place to type it.

## Risks

A risk has not happened yet. Score = impact × probability, computed, not judged.

| Ref | Risk | Impact | Prob. | Score | Mitigation | Contingency | Owner | Raised | Review by | State |
|---|---|---|---|---|---|---|---|---|---|---|
| R-01 | `<IF <CAUSE> THEN <EFFECT>>` | `<L/M/H>` | `<L/M/H>` | `<N>` | `<REDUCE LIKELIHOOD>` | `<IF IT HAPPENS ANYWAY>` | `<NAME>` | `<YYYY-MM-DD>` | `<YYYY-MM-DD>` | `<Open / Mitigated / Closed / Occurred>` |

> Write risks as "if X then Y". "Resourcing" is not a risk; "if the integration
> developer is unavailable in March then M3 slips by three weeks" is.

## Issues

An issue has already happened.

| Ref | Issue | Impact | Raised | Owner | Action | Target | State |
|---|---|---|---|---|---|---|---|
| I-01 | `<WHAT HAS GONE WRONG>` | `<L/M/H>` | `<YYYY-MM-DD>` | `<NAME>` | `<NEXT STEP>` | `<YYYY-MM-DD>` | `<Open / In progress / Resolved>` |

Any issue affecting a committed date or scope must appear in the next weekly
status report. Issues do not get managed quietly until they are fixed.

## Assumptions

| Ref | Assumption | Basis | If wrong | Owner | Validate by | State |
|---|---|---|---|---|---|---|
| A-01 | `<ASSUMPTION>` | `<WHY WE BELIEVE IT>` | `<CONSEQUENCE>` | `<NAME>` | `<YYYY-MM-DD>` | `<Unvalidated / Confirmed / Invalidated>` |

An unvalidated assumption with a large consequence is a risk. Promote it.

## Dependencies

| Ref | Dependency | On whom | Needed by | Blocks | Status |
|---|---|---|---|---|---|
| D-01 | `<ITEM>` | `<CLIENT / THIRD PARTY / INTERNAL>` | `<YYYY-MM-DD>` | `<MILESTONE OR TASK>` | `<Pending / Received / Late>` |

## Decision register

| Ref | Decision | Date | Made by | Forum | Options considered | Rationale | Reversible? | Scope/price/date impact |
|---|---|---|---|---|---|---|---|---|
| D-01 | `<WHAT WAS DECIDED>` | `<YYYY-MM-DD>` | `<NAME>` | `<MEETING REF>` | `<ALTERNATIVES REJECTED>` | `<WHY>` | `<Yes / No / Costly>` | `<None / CR-NN>` |

> Recording the rejected options is the point. In six months somebody will ask
> "why didn't we just…", and this is the answer.

## Review discipline

| Item type | Reviewed | By |
|---|---|---|
| Risks scoring High | Weekly | PM and account owner |
| All other risks | Fortnightly | PM |
| Open issues | Weekly | PM |
| Unvalidated assumptions | At each milestone | PM |
| Dependencies | Weekly | PM |
