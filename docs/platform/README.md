# Mumtaz Digital — platform consolidation

The working set for the **Master Platform Consolidation & Development
Directive** (21 Nov 2026). It sits above the documents that already govern
parts of the estate and does not replace them:

- `REPO_MAP.md`, `registry.yaml`, `sites/` — what is in the repository
- `docs/infrastructure-audit/` — servers, databases, security (read-only audit, 21 Nov 2026)
- `docs/erp/` — the ERP programme: audit, standards, decision register, roadmap, backlog
- `docs/jawhar/`, `docs/mumtaz-jewel/` — the Jawhar edition
- `docs/mumtaz-website/` — the native Odoo website module

**Start with `MUMTAZ_PROGRESS_AND_HANDOFF.md`**: what was done, what was
tested, what is still open.

## Status words

Every claim in this folder carries one of four words.

| Word | Meaning |
| --- | --- |
| **VERIFIED** | Read in code at the cited path, or run on a local Odoo 19 + PostgreSQL 16 rig on 21 Nov 2026 |
| **REPORTED** | From a repository document or an earlier session note; not re-checked. **Everything about the live server is REPORTED**: no session had server access |
| **PROPOSED** | A design or recommendation; not built |
| **UNKNOWN** | Needs server evidence or an owner answer |

## The sixteen deliverables

| Deliverable | File | Kind |
| --- | --- | --- |
| Master architecture | `MUMTAZ_MASTER_ARCHITECTURE.md` | new |
| Current system audit | `MUMTAZ_CURRENT_SYSTEM_AUDIT.md` | reconciliation → `docs/infrastructure-audit/`, `docs/erp/00-AUDIT.md` |
| Product catalogue | `MUMTAZ_PRODUCT_CATALOGUE.md` (+ `mumtaz.product` records in `addons/mumtaz_control_plane/data/product_catalogue.xml`) | new |
| Deployment registry | `MUMTAZ_DEPLOYMENT_REGISTRY.md` | new, built from `sites/` and the audit |
| Module registry review | `MUMTAZ_MODULE_REGISTRY_REVIEW.md` | new |
| Repository consolidation | `MUMTAZ_REPOSITORY_CONSOLIDATION.md` | reconciliation → `REPO_MAP.md`, `sites/README.md`, audit file 12 |
| SaaS control plane | `MUMTAZ_SAAS_CONTROL_PLANE.md` | new |
| Product integration map | `MUMTAZ_PRODUCT_INTEGRATION_MAP.md` | new |
| AI architecture | `MUMTAZ_AI_ARCHITECTURE.md` | new |
| Website implementation | `MUMTAZ_WEBSITE_IMPLEMENTATION.md` | new; module notes stay in `docs/mumtaz-website/` |
| Design system | `MUMTAZ_DESIGN_SYSTEM.md` | new; Jawhar's stays in `docs/jawhar/DESIGN_SYSTEM.md` |
| Security and infrastructure | `MUMTAZ_SECURITY_AND_INFRASTRUCTURE.md` | reconciliation → audit files 04, 05, 09, 13, 15 |
| Development roadmap | `MUMTAZ_DEVELOPMENT_ROADMAP.md` | new; ERP waves stay in `docs/erp/ROADMAP.md` |
| Test and acceptance plan | `MUMTAZ_TEST_AND_ACCEPTANCE_PLAN.md` | new; ERP strategy stays in `docs/erp/quality/` |
| Decision register | **`docs/erp/project/DECISION_REGISTER.md`**, section "Platform decisions" (P-01 … P-17) | appended to the existing register; no second register |
| Progress and handoff | `MUMTAZ_PROGRESS_AND_HANDOFF.md` | new |

## Standing rules (directive §13)

No database is deleted, no installed module is renamed directly, no
production configuration or customer data is changed, no website is
overwritten, C2P and IG2 are never merged, nothing untested is deployed, and
no production change happens without explicit approval. Work goes on a
feature branch, against isolated staging, with a verified backup and a
written rollback.
