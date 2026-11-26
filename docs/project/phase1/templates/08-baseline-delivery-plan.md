# Baseline Delivery Plan and Milestone Acceptance Register

> **CLIENT-FACING. The baseline is set once, at approval, and does not move.**

| Document ID | C2P-BDP-`<PROJECT-REF>`-01 |
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

## 1. Why the baseline does not move

Baseline dates are frozen at approval. Forecast dates move as reality moves. The
gap between them is the only honest measure of slippage, and it disappears the
moment the baseline is quietly rewritten. Changing a baseline requires an
approved change request.

## 2. Milestones

| # | Milestone | Deliverables | Baseline | Forecast | Variance (days) | Internal reviewer | Client approver | Payment trigger |
|---|---|---|---|---|---|---|---|---|
| M1 | `<NAME>` | `<REFS>` | `<YYYY-MM-DD>` | `<YYYY-MM-DD>` | `<+/-N>` | `<NAME>` | `<NAME>` | `<Yes / No>` |

## 3. Dependencies

| # | This | Depends on | Type | Owner | Slack (days) | On critical path |
|---|---|---|---|---|---|---|
| 1 | `<M2>` | `<M1 / CLIENT DATA / THIRD PARTY>` | `<Finish-to-start>` | `<NAME>` | `<N>` | `<Yes / No>` |

Critical path is derived from recorded task dates and dependencies. Where
durations have not been estimated, the path is stated as **incomplete** rather
than computed from assumed durations.

## 4. Milestone acceptance register

The two separations that must never collapse:

- all tasks Done **≠** milestone reached
- milestone reached **≠** client accepted **≠** billable

| Milestone | Tasks complete | Internal QA | Reached (date) | Offered to client | Acceptance outcome | Accepted by | Accepted on | Billing eligible | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| M1 | `<N/N>` | `<Pass / Fail / Pending>` | `<YYYY-MM-DD>` | `<YYYY-MM-DD>` | `<Accepted / Accepted with comments / Partially accepted / Rejected — rework>` | `<CLIENT NAME>` | `<YYYY-MM-DD>` | `<Yes — pending Consultants review / No>` | `<REF>` |

**Billing eligible** is a flag for C2P Consultants to review. It is never an
instruction to invoice and never posts anything.

## 5. Resource plan

| Role | Name or team | Milestones | Allocation | Confirmed? |
|---|---|---|---|---|
| `<ROLE>` | `<NAME / TEAM / PARTNER>` | `<M1, M2>` | `<DAYS OR %>` | `<Confirmed / Tentative>` |

Tentative allocations are shown as tentative on the client plan. A tentative
resource presented as confirmed is how a plan becomes fiction.

## 6. Baseline approval

| Role | Name | Signature | Date |
|---|---|---|---|
| C2P Solutions PM | `<NAME>` | | |
| C2P Consultants | `<NAME>` | | |
| Client sponsor | `<NAME>` | | |

## 7. Baseline changes

| # | CR ref | What changed | Old baseline | New baseline | Approved by | Date |
|---|---|---|---|---|---|---|
| 1 | `<CR-NN>` | `<DETAIL>` | `<YYYY-MM-DD>` | `<YYYY-MM-DD>` | `<NAME>` | `<YYYY-MM-DD>` |
