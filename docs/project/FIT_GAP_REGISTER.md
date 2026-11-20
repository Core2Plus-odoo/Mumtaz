# Deliverable 6 — Standard functionality versus customization analysis

Blueprint §17's ladder: **standard module → configuration → supported integration →
small composable add-on → broader customization only on a signed gap.**

Each row below asks one question: *was this custom code necessary?*

---

## 1. Verdict summary

| Verdict | Modules | Lines |
|---|---|---|
| **Justified** — no standard equivalent exists | 21 | ~13,100 |
| **Justified but over-built** — standard would cover most of it | 5 | ~4,400 |
| **Questionable** — duplicates or shadows standard functionality | 4 | ~1,300 |
| **Scaffolding** — near-empty, should be merged or removed | 8 | ~250 |
| **Cannot judge without the live instance** | 0 | — |

**Headline: the standard-first discipline largely held.** 21 of 38 modules build
things Odoo genuinely does not have (multi-tenant SaaS control plane, subscription
billing, GCC e-invoicing, lead scraping, AI assistants). That is a better result
than most Odoo projects of this size.

---

## 2. Justified custom development

These have no Odoo Community equivalent. Keep.

| Module | Lines | Why standard cannot do it |
|---|---|---|
| `mumtaz_control_plane` | 1,953 | Multi-tenant SaaS subscription/plan/feature-gating control plane. Odoo has no tenant concept |
| `mumtaz_lead_scraper` | 2,626 | External lead sourcing with dedup against `crm.lead`. No standard equivalent |
| `mumtaz_einvoicing` | 2,208 | UAE Peppol / KSA ZATCA Phase 2 / PK FBR. Community has no localisation for these |
| `mumtaz_tenant_manager` | 909 | Tenant provisioning and DB lifecycle |
| `mumtaz_billing_stripe` | 799 | Stripe subscription billing for C2P's own revenue |
| `mumtaz_portal_routing` | 793 | Host/subdomain-based tenant routing |
| `mumtaz_marketplace` | 674 | B2B marketplace matching — genuinely novel |
| `mumtaz_voice` | 672 | Voice assistant over ElevenLabs |
| `mumtaz_core` | 663 | Platform settings and shared groups |
| `mumtaz_ai` | 461 | LLM provider abstraction |
| `mumtaz_api_gateway` | 355 | API key issuance + usage metering |
| `mumtaz_subdomain_routing` | 300 | Host resolution |
| `mumtaz_org_config` | 321 | Per-org branding/config |
| `mumtaz_sme_profile` | 231 | SME onboarding profile |
| `mumtaz_onboarding` | 176 | Guided onboarding |
| `mumtaz_branding` | 99 | White-label branding |
| `mumtaz_sso` | 112 | SSO |
| `mumtaz_zaki` | 372 | ZAKI AI product surface |
| `mumtaz_organization` | 296 | Organisation hierarchy |
| `mumtaz_cfo_ingestion` | 288 | Bank/statement ingestion staging |
| `mumtaz_cfo_base` | 321 | CFO workspace scoping |

---

## 3. Justified but over-built

Custom code where standard would have carried most of the weight. Not wrong —
but each carries avoidable maintenance cost and upgrade risk.

### 3.1 `mumtaz_lead_nurture` (1,451 lines, 7 models)

Implements campaigns, steps, enrolment, logs and qualification wizards. Odoo
Community has **`mail` mass-mailing-adjacent tooling and, crucially, native
Automation Rules + Server Actions** which cover trigger→wait→act sequences
without code. `c2p-delivery-system/delivery_api/odoo_automation.py` — this
organisation's *own* knowledge module — exists precisely to recommend that ladder.

**[DESIGN]** Not worth rewriting now. But the next nurture feature should be a
configured Automation Rule, not an eighth model. Record as an ADR so the decision
is deliberate rather than drifting.

### 3.2 `mumtaz_media_buying` (984 lines, 6 models)

`media.plan`, `media.plan.line`, `media.rate.card`, `media.rate.card.line`,
`media.outlet`. This is **a parallel quotation and purchase-order system**: a plan
has a budget, lines with unit rates and client amounts, a `sale_order_id` and
`purchase_order_ids`.

Odoo's `sale.order` + `purchase.order` + pricelists model exactly this shape.
The custom layer re-implements pricing, margin and totals — then, as
`ENTITY_RELATIONSHIPS.md` §2.1 shows, cannot reconcile any of it to the ledger
because it never links to `account.move`.

**[DESIGN] This is the clearest standard-first violation in the repository.**
The recommended target: keep `media.outlet` and `media.rate.card` (genuinely
media-specific master data, no standard equivalent), and migrate `media.plan` /
`media.plan.line` onto `sale.order` / `sale.order.line` with a pricelist per
outlet. Margin then comes from standard cost fields and reconciles to the ledger
for free. Flagged `ARCH-003`; **needs owner approval** because it touches a
module that may already hold live data (DEC-001).

### 3.3 `mumtaz_financial_reports` (375 lines)

Custom OWL financial reporting beside standard `account` reports. Odoo Community
ships Trial Balance, P&L, Balance Sheet and General Ledger with drill-down.
The custom version has **no lineage**, which is strictly worse than the standard
it replaces.

**[DESIGN]** Prefer standard reports; keep the custom layer only for genuinely
non-standard views, and make every figure drillable.

### 3.4 `mumtaz_cfo_transactions` + `mumtaz_cfo_toolkit` (360 lines)

See `DEC-004`. If these hold balances, they duplicate `account`.

### 3.5 `mumtaz_customer_portal` / `mumtaz_vendor_portal` (506 lines, 0 models)

Pure controller modules — 9 `sudo()` calls, 7 posting references, no models, no
ACL, no record rules. Odoo's standard `portal` already exposes orders, invoices
and deliveries to customers with the access control already solved.

**[DESIGN]** Audit whether each custom portal route serves something standard
`portal` cannot. Every route that duplicates standard should be deleted — each one
is a hand-written `sudo()` path around Odoo's own access control, which is the
exact pattern blueprint §10.1 warns about ("UI hiding alone is not security").

---

## 4. Questionable — duplicates or shadows standard

| Module | Lines | Concern |
|---|---|---|
| `mumtaz_crm_starter` | 35 | Inherits `crm` to do almost nothing. Merge into `mumtaz_core` or delete |
| `mumtaz_ceo_dashboard` | 47 | A shell with one OWL asset and no models. Either build it on a real metric layer or remove it; an empty dashboard module invites someone to fill it with un-lineaged numbers |
| `mumtaz_theme` | 25 | Theming beside `mumtaz_branding` — two modules for one concern |
| `mumtaz_website` | 58 | Website tweaks beside `mumtaz_app_portal` and `mumtaz_portal_routing` — three modules touching page delivery |

## 5. Scaffolding to consolidate

**[FACT]** Eight modules under 60 lines: `mumtaz_base` (50), `mumtaz_portal` (14),
`mumtaz_super_toolkit` (19), `mumtaz_cfo_toolkit` (20), `mumtaz_theme` (25),
`mumtaz_crm_starter` (35), `mumtaz_ceo_dashboard` (47), `mumtaz_website` (58).

Together: ~268 lines across eight installable modules, eight manifests, eight
upgrade paths. `mumtaz_super_toolkit` (19 lines) sits at dependency depth **9**.

**[DESIGN]** Consolidate into two: `mumtaz_core` (platform) and `mumtaz_ui`
(branding + theme + website). Removes six manifests and flattens the deepest
dependency chain in the repository. Low risk, high clarity — but it is an
uninstall/rename operation, so it needs DEC-001 first.

---

## 6. What the ladder says to do next

Blueprint §17's ladder, applied to the gaps found in Deliverables 2 and 5:

| Gap | Correct rung | Not this |
|---|---|---|
| Timesheets / project cost | **Standard**: install `hr_timesheet` | Don't build a timesheet model |
| Approval workflow | **Configuration**: Odoo Automation Rules + activity-based approvals | Don't build an `ApprovalRequest` model first |
| 3-way match | **Standard**: Odoo's purchase bill control policy | Don't build a matcher |
| Budget check | **Standard**: `account_budget` | Don't build a budget model |
| AR ageing / collections | **Standard**: `account` reports + follow-up levels | Don't build dunning |
| Document-to-ledger lineage | **Small add-on**: computed fields reading `account.move` | Don't store derived money |
| Idempotency for webhooks | **Small add-on**: one mixin + unique index | — |
| §7.1 entity contract | **Small add-on**: one abstract mixin | Don't add 5 fields × 62 models |
| Tax-authority submissions | **Justified custom**: already built | — |
| Multi-tenant control plane | **Justified custom**: already built | — |

**Six of the ten biggest gaps close with standard Odoo or configuration.** That is
the single most useful conclusion in this document: the roadmap's first wave is
mostly *installing and configuring what Odoo already has*, not writing code.
