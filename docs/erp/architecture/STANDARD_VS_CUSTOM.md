# 06. Standard functionality versus customization

Blueprint rule: **standard module → configuration → supported integration → small composable add-on → broader customization only after a signed gap.** A custom add-on is *justified* only if it names the standard capability it does not cover. Verdicts are `[P]` proposed; "to confirm" means the overlap could not be established by reading manifests and models alone.

## 1. Pharma add-ons (evaluated in depth)

| Add-on | Standard capability it touches | What standard does NOT do (the gap) | Verdict | Risks and conditions |
| --- | --- | --- | --- | --- |
| `pharma_core` | `res.groups`, `mail` | Immutable source-event archive with duplicate/conflict states; four pharma roles | **Justified, small** | Roles need an Auditor and an SoD matrix (gap G-6) |
| `pharma_pk_tax_core` | `account.tax`, `sale.order`, `account.move` | Approved-only, effective-dated *tax-rule governance* and SKU classification with maker-checker; blocking confirm/post when unresolved | **Justified as a control layer**; must never become a second source of rates | Linked-tax equality check exists; cross-check at confirm and post. No `l10n_pk` yet, so rates are data, not code `[D-006]` |
| `pharma_reconciliation_hub` | native bank reconciliation, `account.partial.reconcile` | Multi-source runs (courier, gateway, bank vs ledger), exception queue, maker-checker closure | **Justified**, but a second reconciliation notion exists | Keep it a *controls and exceptions* layer; posting must always go through `account.move`. Needs bank import to be complete (gap G-10) |
| `pharma_courier_cod` | none in Community (no courier/COD settlement) | Parcel ledger, ageing, remittance with itemised deductions, statement upload | **Justified gap** | Money as `Float`, no currency/company (G-1, G-2) |
| `pharma_courier_cod_accounting` | `account.move` reversal, receivable reconciliation | Draft collection and settlement entries from a courier process; strict order; Entries to Post queue | **Justified**, thin; uses native entries and native reversal (`_reverse_moves`) | `sudo()` creation of drafts (G-5); reconciliation to invoices unexercised (G-4) |
| `pharma_partner_stock` | `stock.move`, lots | Roll-forward for a distribution partner derived from done moves | **Justified, small**; reads native moves, no parallel ledger | Verify against a real stock location `[P]` |
| `pharma_accounting_hardening` | the third-party accounting kit | Closes two findings in the kit (unguarded export route, vendor call-home) and hides the support UI | **Justified as a patch layer**; temporary by nature | Vendor dependency (ADR-004). Re-assert on every upgrade (module does; `verify` shows it) |
| `pharma_demo_data`, `pharma_website_demo`, `pharma_courier_cod_demo` | demo data/website | Fictional scenarios for demonstration | **Demo only**; must never install on production (manifest says so; `pharma.mode=demo` gate) | Add an install guard test `[P]` |

## 2. Rest of the repository (verdicts are first-pass and need an owner review)

| Add-on / family | Overlaps standard | Gap it claims | Verdict | Action |
| --- | --- | --- | --- | --- |
| `mumtaz_einvoicing` | Odoo e-invoicing localizations (country modules) | ZATCA-style flow for GCC | **To confirm** which standard module covers the jurisdiction; extends `account.move.action_post` via `super()` (verified) | Compare with the localization module for the target country before extending |
| `mumtaz_financial_reports`, `mumtaz_ceo_dashboard`, `c2p_command_center` | standard accounting reports, kit reports, dashboards | Role dashboards | **To confirm**; zero models (financial reports/CEO dashboard are views only) | Rebuild on read models with lineage if kept (UX doc) |
| `mumtaz_crm_starter`, `mumtaz_lead_scraper`, `mumtaz_lead_nurture` | `crm`, `mass_mailing` | Outbound lead sourcing and nurture | Starter is configuration; scraper/nurture are **custom, 18 models** | Compliance review (consent, scraping) `[D]`; keep optional |
| `c2p_project_tracker` | `project`, timesheets | Delivery tracking for the agency | **To confirm** overlap with `project` | Decide whether it is a product or an internal tool |
| `mumtaz_jewellery*` (14) | `sale`, `stock`, `point_of_sale`, `crm` | Piece identity, metal-rate pricing, old gold, VIP, AML, kiosk, AI | **Justified vertical**; design docs exist, including a native-POS audit | Keep independent of pharma; maintain its own CI (exists) |
| `mumtaz_marketplace`, `mumtaz_vendor_portal`, `mumtaz_customer_portal` | `website_sale`, `portal` | B2B marketplace listings and inquiries | Custom product feature | Not part of a tenant ERP baseline `[A]` |
| `mumtaz_tenant_manager`, `_control_plane`, `_billing_stripe`, `_api_gateway`, `_subdomain_routing`, `_portal_routing`, `_sso` | none (SaaS control plane) | Tenancy, feature flags, billing, routing | **Platform product**, not ERP functionality | Must gain tests before it is trusted with billing (G-8) |
| `mumtaz_ai`, `_voice`, `mumtaz_jewellery_ai` | none | AI assistants | Custom | Audit against blueprint §12 (permissions, approval, kill switch) before extending |
| `mumtaz_cfo_*`, `mumtaz_zaki` | accounting reports | AI CFO ingestion and analysis | Custom, read-oriented (verified: no ledger writes) | Add tests and data-boundary review |

## 3. Rules for any new custom work `[P]`

1. **Gap statement first.** Each new add-on/module spec names the standard feature checked, why configuration is insufficient, and the cost of the extension (fit-gap register row).
2. **Extend, never recreate.** `_inherit` standard models; never copy business logic that Odoo owns (posting, reconciliation, stock valuation).
3. **Optional and independent.** A new add-on installs and uninstalls without corrupting the base; no module depends upward on a demo/AI/BI module.
4. **Third-party kit policy.** The accounting kit is used only because Community lacks the accounting depth; its source is pinned and *not* vendored; any patch lives in a hardening module with its own tests. Review the pin and the kit's licence/security at each Odoo minor upgrade.
5. **No hard-coded jurisdiction rules.** Rates, thresholds and statutory behaviour are data governed by approval, reviewed by a local expert, never constants in code.
