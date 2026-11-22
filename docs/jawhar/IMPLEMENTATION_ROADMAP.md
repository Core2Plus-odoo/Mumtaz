# Jawhar — implementation roadmap

Each phase ends at a gate: tests green on a fresh database, screenshots for
UI, documents updated, a human merge, and a staging promotion the user runs.
Production deployment needs a named approval and a production host.

| Phase | Scope | Gate / acceptance | Status |
| --- | --- | --- | --- |
| 0 Audit | this folder; capability register; contradictions found | documents merged | done (this PR) |
| 1 Core hardening | fix W1–W3 on the site; readiness vocabulary; lead capture; check_sudo in CI; company scoping on platform modules | all stale claims gone; demo request creates a tagged lead; CI green | done (this PR + #172–#176) |
| 2a Design system + public home | `site/jawhar.css`; home rebuilt; sub-pages rethemed | screenshots desktop/mobile/dark; no errors; no horizontal scroll | done (this PR) |
| 2b App palette migration | tokens in `apps/jawhar-web/src/styles.css`; kiosk theme unified; dark mode with toggle; serif page titles; focus ring | tsc, vitest, EN/AR × light/dark walks green; screenshots | done (PR 2b); density on Today deferred to Phase 3 |
| 2c Arabic site + module pages | `/ar/` home, Counter/Stores/Compliance module pages, sitemap on production | render in RTL without overflow | after 2b |
| 3 Command centre | `jewellery.event` table, owner command centre with lineage, store scorecards | every number traces to a record; tests | |
| 4 Tenancy + white-label | `jawhar` bundle on the provisioner; brand tokens to the app; tenant console; onboarding replaces the setup prototype | second tenant acceptance in `WHITE_LABEL_SPECIFICATION.md` | needs provisioner host (J-04) |
| 4b Domains + billing | custom domain certificates; plans from the control plane; pricing page driven by plans | plan change end to end on staging | needs J-05 |
| 5 AI orchestration | orchestrator, scheduled and event-triggered runs, per-tenant settings, evaluation corpus; Rayan and Amara specified and built on standard purchase/account | golden set green; levels enforced per tenant | |
| 6 Automation engine | `base_automation` rules on events; outbound webhooks; alert centre | idempotent delivery tests | |
| 7 Procurement, consignment, repairs | standard `purchase`, consignment owner, `repair` with gram-aware lines | configured on a tenant with tests | needs a tenant need |
| 8 E-commerce | `website_sale` storefront priced from the engine | storefront price equals counter price | |
| 9 Localisation + e-invoicing | `l10n_*`, ZATCA/FBR per tenant | finance manager sign-off | needs D-06 |
| 10 Production | separate host, backups with restore drill, MFA, monitoring, pen test | runbook executed with named approval | needs J-07 |
