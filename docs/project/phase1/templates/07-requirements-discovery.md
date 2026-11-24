# Requirements and Discovery Record

> **CLIENT-FACING — requires written client confirmation before build begins.**

| Document ID | C2P-REQ-`<PROJECT-REF>`-01 |
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

## 1. How to read this document

Each requirement has a reference, a source, a priority and an acceptance test.
Confirming this document means agreeing that **these** requirements, at **these**
priorities, are what will be built — and that anything absent is out of scope
until a change request says otherwise.

Priorities use MoSCoW: **Must** (the project fails without it), **Should**
(important, has a workaround), **Could** (desirable if time allows), **Won't**
(explicitly not this phase — recorded so it is not forgotten).

## 2. Current state

| Area | How it works today | Pain | Evidence |
|---|---|---|---|
| `<AREA>` | `<CURRENT PROCESS>` | `<WHAT GOES WRONG, AND WHAT IT COSTS>` | `<INTERVIEW / OBSERVATION / DOCUMENT, DATE>` |

## 3. Requirements

| Ref | Requirement | Area | Priority | Source | Acceptance test | Deliverable |
|---|---|---|---|---|---|---|
| R-001 | `<AS A <ROLE> I NEED <CAPABILITY> SO THAT <OUTCOME>>` | `<AREA>` | `<Must>` | `<WHO ASKED, WHEN>` | `<HOW IT WILL BE PROVEN>` | `<DELIVERABLE REF>` |

> A requirement with no acceptance test is not a requirement, it is a hope. If
> the test cannot be written, the requirement is not yet understood.

## 4. Standard-first assessment

| Ref | Met by | Note |
|---|---|---|
| R-001 | `<Standard / Configuration / Supported integration / Small extension / Custom build>` | `<WHY, AND WHAT WAS RULED OUT>` |

Custom build requires a recorded justification. Reaching for configuration first
is not a compromise, it is what keeps the system upgradeable.

## 5. Integrations

| System | Direction | Objects | Trigger | Volume | Owner | Open questions |
|---|---|---|---|---|---|---|
| `<SYSTEM>` | `<Inbound / Outbound / Both>` | `<OBJECTS>` | `<EVENT / SCHEDULE>` | `<PER DAY>` | `<NAME>` | `<DETAIL>` |

## 6. Data migration

| Object | Source | Volume | History required | Match key | Owner | Risks |
|---|---|---|---|---|---|---|
| `<OBJECT>` | `<SYSTEM>` | `<COUNT>` | `<PERIOD>` | `<FIELD — NOT NAME ALONE WHERE COLLISIONS ARE POSSIBLE>` | `<NAME>` | `<DETAIL>` |

## 7. Constraints

| # | Constraint | Type | Consequence |
|---|---|---|---|
| 1 | `<CONSTRAINT>` | `<Technical / Legal / Commercial / Calendar>` | `<WHAT IT RULES OUT>` |

## 8. Out of scope, confirmed

| # | Item | Why | Revisit when |
|---|---|---|---|
| 1 | `<ITEM>` | `<REASON>` | `<CONDITION OR PHASE>` |

## 9. Open questions

| # | Question | Needed from | Needed by | Blocks |
|---|---|---|---|---|
| 1 | `<QUESTION>` | `<NAME>` | `<YYYY-MM-DD>` | `<REQUIREMENT REFS>` |

## 10. Client confirmation

By confirming, `<CLIENT LEGAL NAME>` agrees the requirements in §3 at the stated
priorities, and that items in §8 are excluded from this phase.

| Role | Name | Signature | Date |
|---|---|---|---|
| Client sponsor | `<NAME>` | | |
| Client process owner | `<NAME>` | | |
| C2P Consultants | `<NAME>` | | |
