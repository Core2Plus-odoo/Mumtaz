# Subcontractor Work Order and QA Checklist

> **INTERNAL AND ACCESS-RESTRICTED. The subcontractor receives Parts 1–3
> only. Part 4 commercial terms are visible to C2P authorised users and the
> subcontractor. Part 5 is C2P-only and must never be sent.**

| Document ID | C2P-SWO-`<PROJECT-REF>`-`<NN>` |
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

## Part 1 — the work package

| | |
|---|---|
| Work order | `<SWO-NN>` |
| Delivery partner | `<PARTNER LEGAL NAME>` |
| Partner contact | `<NAME, EMAIL>` |
| C2P owner | `<NAME>`, C2P Solutions |
| Escalation contact | `<NAME, ROLE, CONTACT>` |
| Related project | `<PROJECT-REF>` — **internal reference only** |
| Period | `<YYYY-MM-DD>` to `<YYYY-MM-DD>` |

**Client identity disclosure:** `<Named / Anonymised as "the client" / Per NDA clause REF>`

Check the handoff brief §9 before naming the client to any external party.

## Part 2 — scope and deliverables

**In scope**

| # | Deliverable | Description | Acceptance criteria | Due |
|---|---|---|---|---|
| 1 | `<NAME>` | `<DETAIL>` | `<SPECIFIC, OBSERVABLE>` | `<YYYY-MM-DD>` |

**Out of scope**

| # | Exclusion |
|---|---|
| 1 | `<EXCLUSION>` |

**Standards the work must meet**

| # | Requirement |
|---|---|
| 1 | `<CODING / DESIGN / DOCUMENTATION STANDARD>` |
| 2 | Work must be testable against the acceptance criteria above |
| 3 | No direct contact with the client unless authorised in writing by C2P |

## Part 3 — review, QA and acceptance

| | |
|---|---|
| Submission method | `<DETAIL>` |
| Review cycle | `<N>` working days from submission |
| Revisions included | `<N>` rounds against the stated criteria |
| Internal QA reviewer | `<NAME>` — **must be a C2P employee** |

**The partner cannot accept their own work.** Internal QA by a C2P reviewer
happens before anything reaches the client, and acceptance is recorded by C2P.

| Submission | Date | QA outcome | Reviewer | Defects raised | Resubmitted | Accepted |
|---|---|---|---|---|---|---|
| 1 | `<YYYY-MM-DD>` | `<Pass / Rework>` | `<NAME>` | `<N>` | `<YYYY-MM-DD>` | `<YYYY-MM-DD>` |

### QA checklist — completed by the C2P reviewer

- [ ] Every acceptance criterion in Part 2 demonstrably met
- [ ] Meets the standards listed in Part 2
- [ ] No client-identifying data left in code, comments, fixtures or screenshots
- [ ] No credentials, keys or tokens committed anywhere
- [ ] Tested against the criteria, and the evidence is attached
- [ ] Documentation sufficient for C2P to maintain it without the partner
- [ ] No undisclosed third-party or licence dependency introduced
- [ ] Reviewer is a C2P employee and is not the author

## Part 4 — commercial terms

> **RESTRICTED. Visible to C2P authorised users and the partner only. These
> figures must never appear in any client-facing document.**

| | |
|---|---|
| Basis | `<Fixed price / Day rate / Milestone>` |
| Value | `<AMOUNT> <CURRENCY>` |
| Payment terms | `<DETAIL>` |
| Payment trigger | C2P acceptance of the deliverable, not submission |
| Expenses | `<Included / Pre-approved only>` |
| Liquidated damages or late terms | `<DETAIL / NONE>` |

## Part 5 — access, confidentiality and C2P-only notes

> **C2P ONLY. NOT FOR THE PARTNER.**

### Access granted

| System | Level | Granted | Expires | Granted by | Revoked | Confirmed by |
|---|---|---|---|---|---|---|
| `<SYSTEM>` | `<Least privilege needed>` | `<YYYY-MM-DD>` | `<YYYY-MM-DD>` | `<NAME>` | `<YYYY-MM-DD>` | `<NAME>` |

Rules, without exception: least privilege; time-bounded with an expiry date set
at the point of granting; **no administrator rights**; **no cross-company
visibility**; no access to other work packages, other clients, rates or internal
discussion; revocation confirmed in writing at package close.

### Confidentiality

| | |
|---|---|
| NDA reference and date | `<REF, YYYY-MM-DD>` |
| Data the partner may handle | `<DETAIL>` |
| Data the partner may **not** handle | `<DETAIL>` |
| Data return or destruction obligation | `<DETAIL>` |
| Confirmed complete | `<YYYY-MM-DD>` by `<NAME>` |

### Performance record

| Measure | Result | Note |
|---|---|---|
| Delivered on time | `<N of N>` | |
| QA pass at first submission | `<N of N>` | |
| Defects after acceptance | `<N>` | |
| Responsiveness | `<Good / Acceptable / Poor>` | |
| Use again | `<Yes / Yes with conditions / No>` | `<REASON>` |
