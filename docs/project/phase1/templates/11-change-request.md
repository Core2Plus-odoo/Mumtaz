# Change Request and Impact Assessment

> **CLIENT-FACING. No scope, price or committed-date change takes effect
> without approval recorded here.**

| Document ID | C2P-CR-`<PROJECT-REF>`-`<NN>` |
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

Mirrors `c2p.change.request` (`reference`, `name`, `description`,
`requested_by_id`, `impact_days`, `impact_amount`, `currency_id`, `state`,
`approved_date`, `value_applied`).

## 1. The request

| | |
|---|---|
| Reference | `<CR-NN>` |
| Raised by | `<NAME, ORGANISATION>` |
| Raised on | `<YYYY-MM-DD>` |
| Source | `<MEETING REF / EMAIL / MOM ACTION REF>` |
| Summary | `<ONE LINE>` |
| Priority | `<Urgent / Normal / Low>` |

**What is being asked for**

`<THE REQUEST IN THE REQUESTER'S TERMS. DO NOT PRE-JUDGE IT HERE.>`

**Why**

`<THE BUSINESS REASON. A CHANGE WITH NO STATED REASON USUALLY DIES IN
ASSESSMENT, WHICH WASTES EVERYONE'S TIME.>`

## 2. Is this actually a change?

| Test | Finding |
|---|---|
| Is it in the charter's in-scope list? | `<Yes / No>` |
| Is it covered by a confirmed requirement? | `<Yes — REF / No>` |
| Is it in the charter's exclusions? | `<Yes / No>` |
| Is it a defect in something already accepted? | `<Yes — handle as a defect, not a change / No>` |

**Conclusion:** `<In scope — no CR needed / Out of scope — CR proceeds / Defect — routed to the defect log>`

> A defect in delivered work is not a change request. Classifying it as one to
> recover budget is how trust is lost.

## 3. Impact assessment

Completed by C2P Solutions before any commercial discussion.

| Dimension | Impact | Basis |
|---|---|---|
| Effort | `<N days>` by `<ROLES>` | `<HOW ESTIMATED>` |
| Schedule | `<+N days>` on `<MILESTONES>` | `<CRITICAL PATH EFFECT>` |
| Commercial | `<AMOUNT> <CURRENCY>` | `<RATE BASIS — INTERNAL DETAIL NOT SHOWN TO CLIENT>` |
| Other deliverables | `<WHAT ELSE MOVES>` | |
| Risk introduced | `<NEW OR INCREASED RISKS>` | |
| Resource availability | `<Available / Needs reallocation / Needs partner>` | |
| Do-nothing option | `<CONSEQUENCE OF DECLINING>` | |

**Alternatives considered**

| Option | Effort | Schedule | Cost | Recommendation |
|---|---|---|---|---|
| `<OPTION>` | `<N days>` | `<+N days>` | `<AMOUNT>` | `<Recommended / Not recommended — why>` |

## 4. Revised position if approved

| | Before | After |
|---|---|---|
| Contract value | `<AMOUNT>` | `<AMOUNT>` |
| `<MILESTONE>` baseline | `<YYYY-MM-DD>` | `<YYYY-MM-DD>` |
| Deliverables | `<COUNT / LIST>` | `<COUNT / LIST>` |

## 5. Approval

Work does not begin before both approvals are recorded.

| Role | Name | Decision | Signature | Date |
|---|---|---|---|---|
| C2P Consultants (commercial authority) | `<NAME>` | `<Approved / Rejected / Deferred>` | | |
| Client authorised approver | `<NAME>` | `<Approved / Rejected / Deferred>` | | |

| | |
|---|---|
| Rejection or deferral reason | `<REASON>` |
| Applied to plan on | `<YYYY-MM-DD>` by `<NAME>` |
| Baseline updated | `<Yes / No>` |
| Commercial value applied | `<Yes / No>` |
