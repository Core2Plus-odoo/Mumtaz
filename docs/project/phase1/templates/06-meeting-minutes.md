# Minutes of Meeting

> **TWO VERSIONS: an internal record, and a reviewed client-safe version.
> Only the reviewed version is circulated outside C2P.**

| Document ID | C2P-MOM-`<PROJECT-REF>`-`<NN>` |
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

Drafted from `c2p.meeting` and `c2p.meeting.action`. Approved action items
convert to `project.task` records **once** — the conversion is guarded by a
database unique constraint, so repeating it cannot create a second task.

## Meeting

| | |
|---|---|
| Subject | `<SUBJECT>` |
| Date and time | `<YYYY-MM-DD HH:MM>`, `<DURATION>` |
| Location or link | `<DETAIL>` |
| Chair | `<NAME>` |
| Minute taker | `<NAME>` |
| Project / milestone | `<PROJECT-REF>` / `<MILESTONE>` |

## Attendees

| Name | Role | Organisation | Present |
|---|---|---|---|
| `<NAME>` | `<ROLE>` | `<ORG>` | `<Yes / Apologies>` |

## Agenda

| # | Item |
|---|---|
| 1 | `<ITEM>` |

## Discussion

### `<AGENDA ITEM>`
`<WHAT WAS DISCUSSED. SUMMARISE POSITIONS, NOT TRANSCRIPT. IF A DISAGREEMENT WAS
NOT RESOLVED, SAY SO AND RECORD BOTH POSITIONS — MINUTES THAT SMOOTH OVER A
DISAGREEMENT CREATE A WORSE ONE LATER.>`

## Decisions

| # | Decision | Made by | Rationale | Affects scope/price/date? |
|---|---|---|---|---|
| D1 | `<DECISION>` | `<NAME>` | `<WHY>` | `<No / Yes — raise CR-<NN>>` |

> A decision that changes scope, price or a committed date does not take effect
> here. It requires an approved change request.

## Actions

| Ref | Action | Owner | Due | Status |
|---|---|---|---|---|
| `<MOM-REF>`-A1 | `<ACTION>` | `<NAME>` | `<YYYY-MM-DD>` | `<Draft / Proposed / Approved / Converted>` |

Each action carries a durable reference of its own and keeps it for life, so it
can be cited in an email months later and still be found.

## Open issues carried forward

| Ref | Issue | Owner | Raised | Target |
|---|---|---|---|---|
| `<RAID-REF>` | `<ISSUE>` | `<NAME>` | `<YYYY-MM-DD>` | `<YYYY-MM-DD>` |

## Next meeting

| | |
|---|---|
| Date and time | `<YYYY-MM-DD HH:MM>` |
| Provisional agenda | `<ITEMS>` |

---

## Client-safe version — reviewer checklist

Before circulating outside C2P:

- [ ] Internal commercial figures, margins and subcontractor rates removed
- [ ] Internal performance or resourcing discussion removed
- [ ] Subcontractor names removed unless permitted
- [ ] Unresolved internal disagreement summarised as a C2P position, not a debate
- [ ] Every action has an owner and a date
- [ ] Reviewed by `<NAME, ROLE>` on `<YYYY-MM-DD>`
