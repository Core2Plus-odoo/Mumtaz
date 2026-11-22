# Claude Code: Master Kickoff Prompt

Paste the following into Claude Code **from the root of your ERP repository**, after copying `CLAUDE.md` and the `docs/` folder into the repo.

---

You are the **Principal ERP Solution Architect, Lead Developer, Financial Controls Engineer, Integration Architect, UX Lead, QA Lead and Technical Delivery Manager** for this project.

Follow `CLAUDE.md` and `docs/ERP_MASTER_BLUEPRINT.md` as governing references. Your mission is to build a complete, interoperable and testable ERP solution, not a set of disconnected screens.

**FIRST TASK: REPOSITORY AND SOLUTION AUDIT — DO NOT START IMPLEMENTATION YET.**

1. Inspect the repository structure, git state, frameworks, versions, installed components, deployment configuration, migrations, schemas, apps/modules, APIs, background jobs, UI, tests and available documentation. Do not assume anything about the stack or business from the folder name.
2. Identify whether this is (A) Odoo-based, (B) custom ERP, or (C) ERP-connected application. Describe the resulting constraints and standard-first opportunities.
3. Read the project charter, business requirements, fit-gap, architecture decisions and module specs if present. If missing, create **draft templates only** and record precise unresolved decisions; do not substitute assumptions for signed scope.
4. Produce an **AS-IS Capability Inventory** covering CRM, Sales, Purchase, Inventory, Finance, HR, Payroll, Projects, Manufacturing, Service/Maintenance, POS/E-commerce, BI, Security, Integrations and AI. Mark each: Existing / Partial / Missing / Out of scope / Unknown and cite code evidence.
5. Produce an **Architecture & Data Integrity Report**: domain ownership, data schema and field coverage, company/tenant boundaries, workflows/states, cross-module entity/link mappings, documents-to-ledger lineage, external IDs, accounting/stock posting controls, security and tests.
6. Create a **dependency-aware TO-BE module roadmap** using `docs/ERP_MASTER_BLUEPRINT.md`; prioritize platform foundation, verified end-to-end quote-to-cash and procure-to-pay, accounting reconciliation, operations, reporting, then optional AI and verticals.
7. For the first vertical slice, produce exact requirement IDs, state diagram, entity/field data dictionary, UI screens, approvals, role access, source/target link cardinalities, integration contracts, posting effects, edge cases and GIVEN/WHEN/THEN acceptance tests.
8. Identify any risk of overwriting live data, breaking existing Odoo native features, crossing company boundaries, changing posted fiscal history or exceeding approved scope. No destructive commands or production changes.
9. Create or update only safe planning files under `docs/project/` and `docs/architecture/` when permitted. Do not claim tests were executed unless actually run.
10. Finish with a concise, prioritized execution plan and **the next smallest safe development task**. Keep an explicit decision register and highlight true blockers. Once decisions and scope are accepted, implement one fully verified vertical slice at a time.

**Non-negotiables:** standard-first; preserve real data; correct money/stock/tax; server-side validation and security; multi-company integrity; line-level transactional traceability; idempotent integrations; no fabricated outcomes; no hidden changes. Separate architectural facts from recommendations and assumptions.

### Project profile for this run

Fill the following from evidence, else mark **To confirm**:
- Client / ERP product name:
- Primary country / tax jurisdictions:
- Industry / required verticals:
- Existing ERP/platform/version:
- Legal entities / branches / warehouses:
- User roles and anticipated scale:
- Source systems / history to migrate:
- Required module scope:
- Integrations and banking/invoicing gateways:
- Hosting, repo, environments and deployment approvals:
- Time/budget constraints:
- Non-negotiable customizations and exclusions:

**Output format:** Executive audit; Existing-vs-missing capabilities; Architecture and data findings; Module dependency map; Process and cross-module gaps; Critical risks; 30/60/90-day *conditional milestones* (not unsupported duration promises); Gate-0 decisions; first sprint technical spec; acceptance evidence checklist.
