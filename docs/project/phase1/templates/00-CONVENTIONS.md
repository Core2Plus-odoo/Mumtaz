# Document pack conventions

Fifteen templates. Every one carries the same control header, so any document
can be identified, versioned and traced to an approver without opening it.

## The control header

```
| Document ID        | C2P-<TYPE>-<PROJECT-REF>-<NN>        |
| Version            | <0.1>                                |
| Status             | Draft / In Review / Approved / Superseded / Withdrawn |
| Project reference  | <PROJECT-REF>                        |
| Client             | <CLIENT LEGAL NAME>                  |
| Date               | <YYYY-MM-DD>                         |
| Author             | <NAME, ROLE>                         |
| Reviewer           | <NAME, ROLE>                         |
| Approved by / date | <NAME> / <YYYY-MM-DD>                |
```

Followed by an approval history table. The authoritative copy is the one
attached to the engagement with Status `Approved`; everything else is a draft or
is superseded.

## Document IDs

`C2P-<TYPE>-<PROJECT-REF>-<NN>` where TYPE is: `HOB` handoff brief,
`WEL` welcome, `MDR` master data request, `CHR` charter, `KOA` kickoff agenda,
`MOM` minutes, `REQ` requirements, `BDP` baseline plan, `WSR` weekly status,
`RAID` RAID log, `CR` change request, `DAF` deliverable acceptance,
`UAT` UAT pack, `HOC` handover and closure, `SWO` subcontractor work order.

## Rules that are not negotiable

1. **Placeholders stay placeholders.** `<LIKE THIS>`. Never substitute a
   plausible-looking client name, date, price or contact. An unfilled
   placeholder is a visible gap; an invented fact is a silent error that reaches
   a client.
2. **Draft from recorded data.** Each template names the Odoo record its fields
   come from. Where a fact is not recorded, the document prompts the PM for it
   rather than filling it in.
3. **Client-facing documents carry C2P Consultants** branding and name, and
   inherit the layout and fonts already used by `c2p_proposal` so the client
   sees one visual identity.
4. **Internal documents are marked internal** in the header and in the footer of
   every page, and are access-restricted.
5. **No commercial terms in any client-facing or subcontractor-visible
   document** beyond what that party is contractually entitled to see.
   Subcontractor rates never appear in a client document; client prices never
   appear in a subcontractor document.
6. **Partial and rejected are first-class outcomes.** Any acceptance or sign-off
   template that offers only yes/no will be filled in dishonestly.

## Where each template's data comes from

| Template | Source records |
|---|---|
| Handoff brief | `crm.lead`, `sale.order`, onboarding checklist, portfolio project |
| Welcome email | portfolio project, client contacts (`res.partner`) |
| Master data request | project type, deliverables |
| Charter | deliverables, milestones, RAID, governance fields |
| Kickoff agenda | charter, milestones |
| Minutes | `c2p.meeting`, `c2p.meeting.action` |
| Requirements record | discovery entries, deliverables |
| Baseline plan | `project.milestone`, baselines |
| Weekly status | milestones, RAG (`rag_status`, `rag_reasons`), tasks, RAID |
| RAID log | `c2p.raid.item` |
| Change request | `c2p.change.request` |
| Deliverable acceptance | deliverable, evidence attachments |
| UAT pack | test cases, defect records |
| Handover and closure | deliverables, acceptance records, support terms |
| Subcontractor work order | work package (**restricted**) |
