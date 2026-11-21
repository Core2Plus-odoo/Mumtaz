# Jawhar — decision register

Group-level ADRs live in `docs/erp/project/DECISION_REGISTER.md`; this file
holds Jawhar product decisions. Status: Taken (by evidence or by the owner),
Proposed, Blocked.

| ID | Decision | Evidence / reasoning | Status · owner |
| --- | --- | --- | --- |
| J-01 | Readiness vocabulary on every surface: Built & tested · Device test pending · Specified only · In progress · Planned (mapping to the register's six statuses) | stale labels were the top credibility finding | Taken (this PR) |
| J-02 | Design system v2 "Vibrant Luxury Enterprise" with the directive's palette; site first, app in Phase 2b | audit W7–W8 | Taken (site) · app pending |
| J-03 | Public site stays `noindex` on the staging domain; index only on the production domain | no production domain yet | Taken · revisit with J-07 |
| J-04 | Provisioning and white-label proven on a disposable host before any tenant | real provisioner NOT VERIFIED | Proposed · needs a host |
| J-05 | Prices and editions | placeholders on the site | Blocked · owner |
| J-06 | Analytics and cookies on the site | none today; privacy notice absent | Proposed: none until a notice exists |
| J-07 | Production host separate from the shared VPS | staging shares the host with the C2P CRM | Proposed · owner |
| J-08 | Counter online only | taken in slice 2; copy corrected on the site | Taken |
| J-09 | Lead capture creates `crm.lead` type lead with tag "Jawhar demo", not a boutique opportunity | demo requests are the vendor's pipeline, not a tenant's | Taken (this PR) |
| J-10 | AI-generated imagery allowed for brand photography, always labelled | directive permits; no stock-photo rights | Taken |
| J-11 | Rayan and Amara: specify on standard `purchase`/`account` first; build in Phase 5 or drop from the site | PROTOTYPE today | Proposed |
| J-12 | nginx carve-out for `/jawhar/public/site/` with `limit_req` | form needs a public endpoint | Proposed · needs apply approval |
| J-13 | Agents never produce numbers; restricted data never enters a prompt | existing rule, re-affirmed | Taken |

## Blockers

1. nginx reload on staging (J-12) — the form falls back to e-mail until applied.
2. Staging lags `main` by nine slices — promote (user runs the commands in `DEPLOYMENT_RUNBOOK.md`).
3. Noor's two client tools to register in the ElevenLabs console; device test.
4. Named finance manager (D-06) for VAT/AML/retention values.
5. Prices (J-05), production host (J-07), provisioning host (J-04).
