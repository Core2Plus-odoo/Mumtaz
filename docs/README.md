# Documentation index

One folder per subject. Nothing sits loose at this level.

| Folder | What it covers | Start with |
| --- | --- | --- |
| `platform/` | Platform consolidation: architecture, product catalogue, control plane, AI, website, design system, roadmap, test plan, handoff | `platform/README.md`, then `platform/MUMTAZ_PROGRESS_AND_HANDOFF.md` |
| `infrastructure-audit/` | Read-only audit of servers, databases, security and the repository (21 Nov 2026), with the remediation backlog and the approval log | `infrastructure-audit/README.md` |
| `erp/` | The ERP programme: audit, capability matrix, standards, decision register, roadmap, backlog, release changelog | `erp/README.md` |
| `jawhar/` | Jawhar (jewellery edition): product blueprint, tenancy, design system, white-label | `jawhar/README.md` |
| `mumtaz-jewel/` | Jawhar engineering record: slices, test reports, and the stricter working rules in `CLAUDE.md` | `mumtaz-jewel/CLAUDE.md` |
| `mumtaz-website/` | The native Odoo website module for `mumtaz.digital` | `mumtaz-website/README.md` |
| `operations/` | Older platform operations notes (architecture, deployment, monitoring, VPS). Partly out of date; the audit supersedes them where they disagree | `operations/README.md` |
| `design/` | Design reference files that are not part of any running site | `design/README.md` |
| `archive/` | Superseded documents kept for reference | `archive/README.md` |

Documents that live beside the code they describe: `sites/<domain>/README.md`
(one per website), `c2p-delivery-system/docs/` (Agency OS, including its
build log), `faizy/docs/`, `deploy/jewel-staging/README.md`.

Decisions are recorded in one place: `erp/project/DECISION_REGISTER.md`
(ADR-, D- and P- series). Approvals for anything that touches a server are
logged in `infrastructure-audit/15_DECISIONS_AND_APPROVALS.md`.
