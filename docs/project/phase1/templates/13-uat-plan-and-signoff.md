# UAT Plan, Test Evidence, Defect Log and Sign-off

> **CLIENT-FACING. Applies where the deliverable is testable software or a
> configured system. Omit for advisory-only engagements.**

| Document ID | C2P-UAT-`<PROJECT-REF>`-01 |
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

## Part 1 — UAT plan

### Scope and purpose

UAT confirms the system does what the **confirmed requirements** say, in the
client's own processes, with the client's own people. It is not the place to
discover new requirements; those become change requests.

| | |
|---|---|
| In scope | `<REQUIREMENT REFS / MODULES>` |
| Out of scope | `<WHAT WILL NOT BE TESTED, AND WHY>` |
| Environment | `<URL / NAME>` — `<Staging / Pre-production>` |
| Data | `<Anonymised copy / Synthetic / Client-provided test set>` |
| Window | `<YYYY-MM-DD>` to `<YYYY-MM-DD>` |

### Entry criteria — all must be true before UAT opens

| # | Criterion | Met |
|---|---|---|
| 1 | Internal QA passed on every deliverable in scope | `<Yes / No>` |
| 2 | Test environment available and stable | `<Yes / No>` |
| 3 | Test data loaded and verified | `<Yes / No>` |
| 4 | Testers identified, trained and have access | `<Yes / No>` |
| 5 | Test cases reviewed by the client | `<Yes / No>` |
| 6 | Defect triage process agreed | `<Yes / No>` |

Opening UAT with entry criteria unmet produces defects that are really
environment problems, and a client who loses confidence in the build.

### Exit criteria

| # | Criterion | Target |
|---|---|---|
| 1 | Critical defects open | 0 |
| 2 | High defects open | `<0>` |
| 3 | Medium defects | `<AGREED NUMBER, WITH A PLAN FOR EACH>` |
| 4 | Test cases executed | `<100%>` of Must-priority |
| 5 | Test cases passed | `<AGREED %>` |

### Testers

| Name | Role | Processes | Trained on | Access confirmed |
|---|---|---|---|---|
| `<NAME>` | `<ROLE>` | `<PROCESSES>` | `<YYYY-MM-DD>` | `<Yes / No>` |

### Defect severity

| Severity | Definition | Response | Fix target |
|---|---|---|---|
| Critical | Blocks a core process; no workaround | Same working day | `<N days>` |
| High | Major function impaired; workaround painful | `<N working days>` | `<N days>` |
| Medium | Function impaired; acceptable workaround | `<N working days>` | Before go-live or agreed later |
| Low | Cosmetic or minor inconvenience | Logged | Backlog |

---

## Part 2 — test cases and evidence

| Case | Requirement | Process | Steps | Expected | Actual | Result | Tester | Date | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| TC-001 | `<R-REF>` | `<PROCESS>` | `<1. … 2. …>` | `<EXPECTED>` | `<OBSERVED>` | `<Pass / Fail / Blocked / Not run>` | `<NAME>` | `<YYYY-MM-DD>` | `<REF>` |

**Result is recorded as observed.** A case that was not run is `Not run`, never
assumed to pass.

### Execution summary

| | Count |
|---|---|
| Total cases | `<N>` |
| Passed | `<N>` |
| Failed | `<N>` |
| Blocked | `<N>` |
| Not run | `<N>` |

---

## Part 3 — defect log

| Ref | Title | Severity | Raised by | Raised | Case | Status | Owner | Root cause | Fixed in | Retested | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D-001 | `<TITLE>` | `<Critical / High / Medium / Low>` | `<NAME>` | `<YYYY-MM-DD>` | `<TC-REF>` | `<Open / In progress / Fixed / Retest / Closed / Rejected>` | `<NAME>` | `<CAUSE>` | `<BUILD / DATE>` | `<YYYY-MM-DD>` | `<Pass / Fail>` |

### Classification disputes

Where C2P and the client disagree on whether an item is a defect or a change:

| Ref | Client view | C2P view | Resolution | Decided by | Date |
|---|---|---|---|---|---|
| `<D-REF>` | `<Defect>` | `<Change — not a confirmed requirement>` | `<OUTCOME>` | `<NAME>` | `<YYYY-MM-DD>` |

---

## Part 4 — sign-off

| | |
|---|---|
| Cases executed | `<N>` of `<N>` |
| Pass rate | `<%>` |
| Critical open | `<N>` |
| High open | `<N>` |
| Medium open | `<N>` — with a plan for each |
| Exit criteria met | `<Yes / No — detail>` |

### Open items accepted into go-live

| Ref | Severity | Why acceptable | Plan | Agreed by |
|---|---|---|---|---|
| `<D-REF>` | `<Medium>` | `<WORKAROUND, AND WHO IS AFFECTED>` | `<WHEN IT WILL BE FIXED>` | `<NAME>` |

| Role | Name | Decision | Signature | Date |
|---|---|---|---|---|
| Client UAT lead | `<NAME>` | `<Passed / Passed with conditions / Failed>` | | |
| Client sponsor | `<NAME>` | `<Approved for go-live / Not approved>` | | |
| C2P Solutions PM | `<NAME>` | Confirmed | | |
| C2P Consultants | `<NAME>` | Acknowledged | | |
